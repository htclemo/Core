"""Tools the local model can call.

Ollama models that advertise the ``tools`` capability can be given a set of
function definitions; the model then asks for them to be executed and the
result is fed back into the conversation.

The tools here give a local model real agency over the project folder:

* ``read_file``      — read a text file
* ``write_file``     — create or overwrite a file
* ``edit_file``      — replace a block of text in a file
* ``list_directory`` — list the files in a folder
* ``run_command``    — run a PowerShell command in the project folder

**Safety.**  Every path is resolved against the project folder and may not
escape it, so a confused model cannot touch the rest of the machine.  Writes
and commands are reported in the chat, so the user sees exactly what happened.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# How much of a file is handed to the model.
_MAX_READ_BYTES = 60_000
_MAX_LIST_ENTRIES = 200
_COMMAND_TIMEOUT = 60


def parse_tool_calls(content: str) -> list[dict[str, Any]]:
    """Recover tool calls a model wrote as plain text.

    Ollama's structured ``tool_calls`` field is the happy path, but smaller
    models often ignore the format and simply print the JSON::

        {"name": "read_file", "arguments": {"path": "hello.py"}}

    This function recognises that (bare object, several objects, a fenced
    ``json`` block or a ``<tool_call>`` block) and returns it in Ollama's
    shape, so the tools still work.
    """
    if not content:
        return []

    text = content.strip()
    if not text:
        return []

    candidates: list[str] = []

    # <tool_call> ... </tool_call> blocks.
    if "<tool_call>" in text:
        import re

        for match in re.findall(r"<tool_call>(.*?)</tool_call>", text, re.S):
            candidates.append(match.strip())
    elif "```" in text:
        import re

        for match in re.findall(r"```(?:json)?\s*(.*?)```", text, re.S):
            candidates.append(match.strip())
    else:
        candidates.append(text)

    calls: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        # A single object, or several objects one after another.
        for raw in _split_json_objects(candidate):
            try:
                import json

                payload = json.loads(raw)
            except Exception:  # noqa: BLE001 — not a tool call after all
                continue
            if not isinstance(payload, dict):
                continue
            name = payload.get("name") or payload.get("function")
            if isinstance(name, dict):
                name = name.get("name")
            if not isinstance(name, str) or not name:
                continue
            arguments = payload.get("arguments")
            if arguments is None:
                arguments = payload.get("parameters") or payload.get("args") or {}
            if isinstance(arguments, str):
                try:
                    import json

                    arguments = json.loads(arguments)
                except Exception:  # noqa: BLE001
                    arguments = {"value": arguments}
            calls.append(
                {
                    "type": "function",
                    "function": {"name": name, "arguments": arguments or {}},
                }
            )
    return calls


def _split_json_objects(text: str) -> list[str]:
    """Split a text into its top-level JSON objects."""
    import json

    decoder = json.JSONDecoder()
    parts: list[str] = []
    index = 0
    while index < len(text):
        start = text.find("{", index)
        if start == -1:
            break
        try:
            _, end = decoder.raw_decode(text[start:])
        except ValueError:
            break
        parts.append(text[start : start + end])
        index = start + end
    return parts


def _looks_like_tool_call(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    name = payload.get("name") or payload.get("function")
    if isinstance(name, dict):
        name = name.get("name")
    return isinstance(name, str) and bool(name)


def strip_tool_calls_from_content(content: str) -> str:
    """Remove tool-call JSON that a model printed as plain text.

    The same models that ignore the structured ``tool_calls`` field also print
    that JSON into the answer, so it has to be taken out again before the
    reply is shown or stored.
    """
    if not content:
        return content

    import json
    import re

    text = content
    # Fenced blocks and <tool_call> blocks go first.
    text = re.sub(r"```(?:json)?\s*\{.*?\}\s*```", "", text, flags=re.S)
    text = re.sub(r"<tool_call>.*?</tool_call>", "", text, flags=re.S)

    # Then any bare JSON object that looks like a tool call.
    decoder = json.JSONDecoder()
    out: list[str] = []
    index = 0
    while index < len(text):
        start = text.find("{", index)
        if start == -1:
            out.append(text[index:])
            break
        out.append(text[index:start])
        try:
            payload, end = decoder.raw_decode(text[start:])
        except ValueError:
            out.append(text[start : start + 1])
            index = start + 1
            continue
        if _looks_like_tool_call(payload):
            index = start + end  # drop it
        else:
            out.append(text[start : start + end])
            index = start + end

    cleaned = "".join(out).strip()
    return cleaned


@dataclass
class ToolResult:
    """The outcome of one tool call."""

    ok: bool
    content: str
    display: str = ""

    def to_message(self) -> str:
        return self.content


@dataclass
class Tool:
    """One callable tool: its Ollama definition and its implementation."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Any
    icon: str = ""

    def definition(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """The tools available to the model, confined to one project folder."""

    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self._tools: dict[str, Tool] = {}
        self._register_defaults()

    # ------------------------------------------------------------------ setup

    def _register_defaults(self) -> None:
        self._tools["read_file"] = Tool(
            name="read_file",
            description=(
                "Read a text file from the project folder. "
                "Returns the content with line numbers."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path of the file, relative to the project folder.",
                    }
                },
                "required": ["path"],
            },
            handler=self._read_file,
        )
        self._tools["write_file"] = Tool(
            name="write_file",
            description=(
                "Create a file or replace its entire content. "
                "Use this for new files and for complete rewrites."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path of the file, relative to the project folder.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The full new content of the file.",
                    },
                },
                "required": ["path", "content"],
            },
            handler=self._write_file,
        )
        self._tools["edit_file"] = Tool(
            name="edit_file",
            description=(
                "Replace an exact piece of text in a file. "
                "The old text must appear exactly once."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path of the file, relative to the project folder.",
                    },
                    "old_text": {
                        "type": "string",
                        "description": "The exact text to replace.",
                    },
                    "new_text": {
                        "type": "string",
                        "description": "The text to put in its place.",
                    },
                },
                "required": ["path", "old_text", "new_text"],
            },
            handler=self._edit_file,
        )
        self._tools["list_directory"] = Tool(
            name="list_directory",
            description=(
                "List the files and folders of a directory in the project folder."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Folder to list, relative to the project folder. Empty for the root.",
                    }
                },
                "required": ["path"],
            },
            handler=self._list_directory,
        )
        self._tools["run_command"] = Tool(
            name="run_command",
            description=(
                "Run a PowerShell command in the project folder and return its output."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The PowerShell command to run.",
                    }
                },
                "required": ["command"],
            },
            handler=self._run_command,
        )

    # ------------------------------------------------------------------ api

    @property
    def tools(self) -> list[Tool]:
        return list(self._tools.values())

    def definitions(self) -> list[dict[str, Any]]:
        """The tool definitions in Ollama's format."""
        return [tool.definition() for tool in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Run a tool by name."""
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                ok=False,
                content=f"Unknown tool '{name}'. Available tools: "
                + ", ".join(sorted(self._tools)),
            )
        try:
            return tool.handler(arguments or {})
        except Exception as exc:  # noqa: BLE001 — a broken tool must not kill the chat
            return ToolResult(
                ok=False, content=f"Tool '{name}' failed: {type(exc).__name__}: {exc}"
            )

    # ------------------------------------------------------------------ paths

    def _resolve(self, relative: str) -> Path:
        """Resolve a path inside the project folder (no escaping allowed)."""
        cleaned = (relative or "").strip().strip('"')
        candidate = Path(cleaned)
        if candidate.is_absolute():
            target = candidate.resolve()
        else:
            target = (self.root / candidate).resolve()
        try:
            target.relative_to(self.root)
        except ValueError:
            raise PermissionError(
                f"'{relative}' is outside the project folder "
                f"({self.root}); that is not allowed."
            )
        return target

    def _relative(self, target: Path) -> str:
        try:
            return str(target.relative_to(self.root)).replace("\\", "/")
        except ValueError:
            return str(target)

    # ------------------------------------------------------------------ handlers

    def _read_file(self, args: dict[str, Any]) -> ToolResult:
        target = self._resolve(str(args.get("path", "")))
        if not target.exists():
            return ToolResult(ok=False, content=f"File not found: {self._relative(target)}")
        if not target.is_file():
            return ToolResult(ok=False, content=f"Not a file: {self._relative(target)}")
        try:
            data = target.read_bytes()[:_MAX_READ_BYTES]
        except OSError as exc:
            return ToolResult(ok=False, content=f"Could not read the file: {exc}")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return ToolResult(
                ok=False,
                content="This file is not text (binary); it cannot be read as text.",
            )
        numbered = "\n".join(
            f"{index:>5}  {line}"
            for index, line in enumerate(text.splitlines(), start=1)
        )
        return ToolResult(
            ok=True,
            content=numbered,
            display=f"read {self._relative(target)} ({len(text)} chars)",
        )

    def _write_file(self, args: dict[str, Any]) -> ToolResult:
        target = self._resolve(str(args.get("path", "")))
        content = str(args.get("content", ""))
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            existed = target.exists()
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            return ToolResult(ok=False, content=f"Could not write the file: {exc}")
        action = "updated" if existed else "created"
        return ToolResult(
            ok=True,
            content=f"{action} {self._relative(target)} ({len(content)} chars)",
            display=f"wrote {self._relative(target)}",
        )

    def _edit_file(self, args: dict[str, Any]) -> ToolResult:
        target = self._resolve(str(args.get("path", "")))
        old_text = str(args.get("old_text", ""))
        new_text = str(args.get("new_text", ""))
        if not target.exists():
            return ToolResult(ok=False, content=f"File not found: {self._relative(target)}")
        try:
            text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return ToolResult(ok=False, content=f"Could not read the file: {exc}")
        count = text.count(old_text)
        if count == 0:
            return ToolResult(
                ok=False,
                content="The text to replace was not found in "
                f"{self._relative(target)}. Read the file first and copy the "
                "text exactly.",
            )
        if count > 1:
            return ToolResult(
                ok=False,
                content=f"The text to replace appears {count} times in "
                f"{self._relative(target)}; include more context so it is unique.",
            )
        try:
            target.write_text(text.replace(old_text, new_text, 1), encoding="utf-8")
        except OSError as exc:
            return ToolResult(ok=False, content=f"Could not write the file: {exc}")
        return ToolResult(
            ok=True,
            content=f"edited {self._relative(target)}",
            display=f"edited {self._relative(target)}",
        )

    def _list_directory(self, args: dict[str, Any]) -> ToolResult:
        target = self._resolve(str(args.get("path", "")))
        if not target.exists():
            return ToolResult(ok=False, content=f"Folder not found: {self._relative(target)}")
        if not target.is_dir():
            return ToolResult(ok=False, content=f"Not a folder: {self._relative(target)}")
        try:
            entries = sorted(
                target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except OSError as exc:
            return ToolResult(ok=False, content=f"Could not list the folder: {exc}")
        lines = []
        for entry in entries[:_MAX_LIST_ENTRIES]:
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"{entry.name}{suffix}")
        if not lines:
            lines = ["(empty)"]
        return ToolResult(
            ok=True,
            content="\n".join(lines),
            display=f"listed {self._relative(target) or '.'} ({len(lines)} entries)",
        )

    def _run_command(self, args: dict[str, Any]) -> ToolResult:
        command = str(args.get("command", "")).strip()
        if not command:
            return ToolResult(ok=False, content="No command given.")
        try:
            completed = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", command],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=_COMMAND_TIMEOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                ok=False,
                content=f"The command timed out after {_COMMAND_TIMEOUT} seconds.",
            )
        except OSError as exc:
            return ToolResult(ok=False, content=f"Could not run the command: {exc}")

        output = (completed.stdout or "").strip()
        errors = (completed.stderr or "").strip()
        parts = []
        if output:
            parts.append(output)
        if errors:
            parts.append(f"[stderr]\n{errors}")
        if not parts:
            parts.append(f"(no output, exit code {completed.returncode})")
        return ToolResult(
            ok=completed.returncode == 0,
            content="\n".join(parts),
            display=f"ran: {command[:60]}",
        )
