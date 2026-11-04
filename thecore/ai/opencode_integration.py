"""OpenCode integration — use OpenCode as the coding agent inside TheCore.

OpenCode ships several front-ends:

* ``opencode`` / ``opencode mini`` are *interactive TUIs*.  They require a real
  TTY on stdout and refuse to run otherwise (``opencode mini requires a TTY
  stdout``).  Piping them into a GUI therefore yields **no readable characters
  at all** — this is why the console panel gives them a genuine terminal.
* ``opencode run --format json`` is the non-interactive CLI mode.  It prints a
  stream of JSON events and works over a pipe, but it is not OpenCode's real
  interface.

:class:`OpenCodeConsole` (in ``thecore.ai.ui.opencode_console``) therefore
drives the interactive TUI inside a ConPTY pseudo console, emulated by
``thecore.ai.ui.terminal_widget``.  The user gets the genuine OpenCode
console — the same one they would see in a terminal window.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QProcess, Signal, Slot


# Basic ANSI escape sequence stripper so the embedded console output stays
# readable even when OpenCode emits colour / cursor control codes.
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\].*?\x07|\x1b[()][A-B0-9]")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from ``text``."""
    return _ANSI_RE.sub("", text)


# npm global install location — the ``opencode.cmd`` wrapper on PATH simply
# forwards to this binary.
_NPM_CLI_EXE = (
    Path.home()
    / "AppData"
    / "Roaming"
    / "npm"
    / "node_modules"
    / "@opencode"
    / "cli"
    / "bin"
    / "opencode.exe"
)

# How much tool output we keep in the console before truncating.
_MAX_TOOL_LINES = 30
_MAX_TOOL_CHARS = 4000


def resolve_opencode_command() -> Optional[list[str]]:
    """Return the argv prefix that launches the OpenCode CLI.

    The npm ``opencode.cmd`` wrapper is a batch file, so it has to be run
    through ``cmd /c`` — and ``cmd.exe`` mangles prompts that contain ``&``,
    ``|``, ``>`` or ``%``.  Whenever the real ``opencode.exe`` is available we
    therefore call it directly and skip ``cmd.exe`` entirely.
    """
    # 1. npm global install — call the real executable directly.
    if _NPM_CLI_EXE.is_file():
        return [str(_NPM_CLI_EXE)]

    # 2. npm wrapper on PATH — needs cmd.exe.
    wrapper = shutil.which("opencode.cmd") or shutil.which("opencode.bat")
    if wrapper:
        return ["cmd", "/c", wrapper]

    # 3. A plain executable on PATH (winget / scoop / manual install).
    for name in ("opencode.exe", "opencode"):
        found = shutil.which(name)
        if found and not found.lower().endswith((".cmd", ".bat")):
            return [found]

    return None


# Backwards-compatible private alias used elsewhere in this module.
_resolve_opencode_command = resolve_opencode_command


def _find_opencode() -> Optional[str]:
    """Locate the OpenCode CLI on this PC (returns the executable path)."""
    command = _resolve_opencode_command()
    if not command:
        return None
    return command[-1]


def _is_cmd_file(path: str) -> bool:
    return path.lower().endswith(".cmd") or path.lower().endswith(".bat")


def _tool_summary(part: dict) -> str:
    """Build a short, human readable one-liner for a tool call."""
    tool = str(part.get("tool") or "tool")
    state = part.get("state") or {}
    title = state.get("title")
    # OpenCode often titles a tool call with the tool's own name ("shell" ->
    # "shell"), which would render as "shell: shell" — ignore that case and
    # fall through to the actual payload.
    if isinstance(title, str) and title.strip() and title.strip().lower() != tool.lower():
        return f"{tool}: {title.strip()}"
    payload = state.get("input") or {}
    if isinstance(payload, dict):
        for key in ("command", "filePath", "path", "pattern", "query", "url"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return f"{tool}: {' '.join(value.split())[:160]}"
    return tool


class OpenCodeIntegration:
    """Wrapper around the OpenCode CLI so TheCore can use it as a coding agent."""

    def __init__(self) -> None:
        self._command = _resolve_opencode_command()

    def is_available(self) -> bool:
        return self._command is not None

    def command(self) -> Optional[str]:
        """Return the resolved OpenCode executable path, or ``None``."""
        return self._command[-1] if self._command else None

    def run(self, prompt: str, cwd: Optional[str] = None) -> str:
        """Run OpenCode with a prompt and return its plain-text output.

        If OpenCode CLI isn't installed, returns an error message telling the
        user how to install it.
        """
        if not self._command:
            return (
                "[OpenCode] OpenCode CLI not found on this PC.\n"
                "Install it with:  npm install -g @opencode/cli\n"
                "Or download from: https://opencode.ai\n"
                "Then restart TheCore."
            )

        try:
            argv = [*self._command, "run", prompt]
            # stdin must be closed, otherwise OpenCode blocks forever.
            full = subprocess.run(
                argv,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
                stdin=subprocess.DEVNULL,
                env=os.environ.copy(),
            )
            output = full.stdout or ""
            if full.stderr:
                output += f"\n[stderr]\n{strip_ansi(full.stderr)}"
            if full.returncode != 0 and not output.strip():
                output = f"[OpenCode] exited with code {full.returncode}"
            return output
        except subprocess.TimeoutExpired:
            return "[OpenCode] Request timed out (5 minutes)."
        except Exception as exc:  # noqa: BLE001 — surface errors to the user
            return f"[OpenCode ERROR] {exc}"


class OpenCodeConsole(QObject):
    """Embedded OpenCode console driven by ``opencode run --format json``.

    Each message typed by the user starts a fresh CLI run whose JSON event
    stream is translated into readable text.  The session id reported by the
    CLI is kept, so the console behaves like a continuous conversation.
    """

    # Human readable console text (ANSI already stripped).
    output_received = Signal(str)
    # Short status text for the console status line.
    status_received = Signal(str)
    # The console is ready to accept messages.
    started = Signal()
    # A run started (carries the prompt).
    run_started = Signal(str)
    # A run finished (exit code + reason).
    run_finished = Signal(int, str)
    # The console was torn down (exit code + reason).
    stopped = Signal(int, str)
    # Hard error (CLI missing, spawn failed, …).
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: Optional[QProcess] = None
        self._pending_assistant = ""
        self._cwd: Optional[str] = None
        self._command: Optional[list[str]] = None
        self._session_id: Optional[str] = None
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._seen_events = False
        self._cancelled = False
        self._json_format = True
        self._user_stopped = False
        self._last_prompt = ""

    # ------------------------------------------------------------------ lifecycle

    @property
    def is_running(self) -> bool:
        """True while a CLI run is in flight."""
        return (
            self._process is not None
            and self._process.state() == QProcess.ProcessState.Running
        )

    @property
    def session_id(self) -> Optional[str]:
        """The OpenCode session id used for this console (if any)."""
        return self._session_id

    def start(self, cwd: str) -> bool:
        """Prepare the console for use in ``cwd`` (non-blocking).

        The OpenCode CLI is started per message, so this only resolves the
        executable and remembers the working directory.  :attr:`started` fires
        as soon as the console is ready.
        """
        command = _resolve_opencode_command()
        if command is None:
            self.error.emit(
                "OpenCode CLI not found. Install it with: npm install -g @opencode/cli"
            )
            return False

        self._cwd = cwd
        self._command = command
        self._session_id = None
        self._user_stopped = False
        self.started.emit()
        return True

    def stop(self) -> None:
        """Stop the console and any run in flight."""
        self._kill_process()
        self._session_id = None
        self._user_stopped = True
        self.stopped.emit(0, "OpenCode console stopped.")

    def cancel(self) -> bool:
        """Cancel the run in flight (the console stays usable)."""
        if not self.is_running:
            return False
        self._cancelled = True
        self._kill_process()
        return True

    def send(self, prompt: str) -> bool:
        """Send ``prompt`` to OpenCode and stream the answer into the console."""
        if self.is_running:
            self.status_received.emit("OPENCODE: BUSY — WAIT FOR THE CURRENT RUN")
            return False

        if self._command is None:
            self._command = _resolve_opencode_command()
        if not self._command:
            self.error.emit("OpenCode CLI not found on this PC.")
            return False

        args = ["run"]
        if self._json_format:
            args += ["--format", "json"]
        if self._session_id:
            args += ["--session", self._session_id]
        args.append(prompt)

        process = QProcess(self)
        process.setProgram(self._command[0])
        process.setArguments([*self._command[1:], *args])
        process.setWorkingDirectory(self._cwd or str(Path.cwd()))
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        # OpenCode blocks forever when its stdin is an open, idle pipe — hand it
        # the null device so reads return EOF immediately.
        process.setStandardInputFile(QProcess.nullDevice())

        process.readyReadStandardOutput.connect(self._on_stdout)
        process.readyReadStandardError.connect(self._on_stderr)
        process.started.connect(self._on_started)
        process.finished.connect(self._on_finished)
        process.errorOccurred.connect(self._on_error)

        self._process = process
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._seen_events = False
        self._cancelled = False
        self._last_prompt = prompt
        self.run_started.emit(prompt)
        process.start(QProcess.OpenMode.ReadWrite)
        return True

    def _kill_process(self) -> None:
        process = self._process
        if process is None:
            return
        self._process = None
        try:
            if process.state() != QProcess.ProcessState.NotRunning:
                process.kill()
                process.waitForFinished(3000)
        except Exception:  # noqa: BLE001 — best effort shutdown
            pass
        process.deleteLater()

    # ------------------------------------------------------------------ persistence helpers

    def pending_assistant(self) -> str:
        """Return accumulated assistant output not yet persisted."""
        return self._pending_assistant

    def clear_pending(self) -> None:
        self._pending_assistant = ""

    # ------------------------------------------------------------------ slots / internals

    @Slot()
    def _on_started(self) -> None:
        self.status_received.emit("OPENCODE: WORKING…")

    @Slot()
    def _on_stdout(self) -> None:
        process = self._process
        if process is None:
            return
        raw = process.readAllStandardOutput().data()
        if not raw:
            return
        text = bytes(raw).decode("utf-8", errors="replace")
        self._stdout_buffer += text
        while "\n" in self._stdout_buffer:
            line, self._stdout_buffer = self._stdout_buffer.split("\n", 1)
            self._handle_line(line)

    @Slot()
    def _on_stderr(self) -> None:
        process = self._process
        if process is None:
            return
        raw = process.readAllStandardError().data()
        if not raw:
            return
        text = bytes(raw).decode("utf-8", errors="replace")
        self._stderr_buffer += text
        # stderr carries the "> build · model" progress line — keep it out of
        # the console body but surface the last meaningful line as status.
        for chunk in text.splitlines():
            clean = strip_ansi(chunk).strip()
            if clean.startswith(">"):
                self.status_received.emit(f"OPENCODE: {clean.lstrip('> ').upper()}")

    @Slot(int, QProcess.ExitStatus)
    def _on_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        # Flush any trailing partial line.
        if self._stdout_buffer.strip():
            self._handle_line(self._stdout_buffer)
            self._stdout_buffer = ""

        process = self._process
        self._process = None
        if process is not None:
            process.deleteLater()

        if self._cancelled:
            self.run_finished.emit(exit_code, "RUN STOPPED")
            return

        if exit_code != 0 and not self._seen_events:
            stderr = strip_ansi(self._stderr_buffer).strip()
            # An older CLI may not know `--format json` — retry in plain mode.
            if self._json_format and "--format" in stderr:
                self._json_format = False
                self.status_received.emit("OPENCODE: RETRYING WITHOUT JSON OUTPUT")
                self._retry_plain()
                return
            if stderr:
                self._emit_output(f"[OpenCode ERROR] {stderr}")
            else:
                self._emit_output(
                    f"[OpenCode ERROR] process exited with code {exit_code}"
                )
            self.run_finished.emit(exit_code, f"FAILED (CODE {exit_code})")
            return

        if self._seen_events:
            self.status_received.emit("OPENCODE: READY")
        self.run_finished.emit(exit_code, "READY")

    def _retry_plain(self) -> None:
        """Re-run the last prompt without ``--format json``."""
        prompt = self._last_prompt
        if not prompt:
            self.run_finished.emit(-1, "FAILED")
            return
        self._last_prompt = ""
        self.send(prompt)

    @Slot(QProcess.ProcessError)
    def _on_error(self, error: QProcess.ProcessError) -> None:
        if self._process is None:
            return
        self._process = None
        if error == QProcess.ProcessError.FailedToStart:
            self.error.emit(
                "Could not start the OpenCode CLI. Check that it is installed and "
                "on your PATH."
            )
            self.run_finished.emit(-1, "FAILED TO START")

    # ------------------------------------------------------------------ event parsing

    def _handle_line(self, line: str) -> None:
        line = line.strip()
        if not line:
            return
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            # Plain (non-JSON) output — show it verbatim.
            self._seen_events = True
            self._emit_output(strip_ansi(line))
            return
        if isinstance(event, dict):
            self._seen_events = True
            self._handle_event(event)

    def _handle_event(self, event: dict) -> None:
        session_id = event.get("sessionID")
        if isinstance(session_id, str) and session_id and not self._session_id:
            self._session_id = session_id

        kind = event.get("type")
        part = event.get("part") or {}

        if kind == "text":
            text = str(part.get("text") or "").strip()
            if text:
                self._pending_assistant += text + "\n\n"
                self._emit_output(text)
        elif kind == "tool_use":
            self._emit_output(self._render_tool(part))
        elif kind == "step_start":
            self.status_received.emit("OPENCODE: WORKING…")
        elif kind == "step_finish":
            self._report_step_finish(part)

    def _report_step_finish(self, part: dict) -> None:
        tokens = part.get("tokens") or {}
        total = 0
        if isinstance(tokens, dict):
            total = int(tokens.get("input") or 0) + int(tokens.get("output") or 0)
        if total:
            self.status_received.emit(f"OPENCODE: STEP DONE · {total} TOKENS")
        else:
            self.status_received.emit("OPENCODE: STEP DONE")

    def _render_tool(self, part: dict) -> str:
        summary = _tool_summary(part)
        state = part.get("state") or {}
        lines = [f"⚙ {summary}"]
        output = strip_ansi(str(state.get("output") or "")).strip()
        if output:
            if len(output) > _MAX_TOOL_CHARS:
                output = output[:_MAX_TOOL_CHARS] + "…"
            output_lines = output.splitlines()
            hidden = len(output_lines) - _MAX_TOOL_LINES
            for line in output_lines[:_MAX_TOOL_LINES]:
                lines.append(f"   {line}")
            if hidden > 0:
                lines.append(f"   … {hidden} more lines")
        status = state.get("status")
        if status and status not in ("completed", "success"):
            lines.append(f"   ({status})")
        return "\n".join(lines)

    def _emit_output(self, text: str) -> None:
        cleaned = strip_ansi(text).rstrip()
        if cleaned:
            self.output_received.emit(cleaned)
