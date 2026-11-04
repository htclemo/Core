"""QThread workers for Ollama calls so the UI stays responsive during streaming."""

from __future__ import annotations

import json
from typing import Any, Callable, Iterator, Optional

from PySide6.QtCore import QObject, QThread, Signal

from thecore.ai.ollama_client import ChatMessage, OllamaClient
from thecore.ai.tools import parse_tool_calls, strip_tool_calls_from_content


class OllamaWorker(QObject):
    """Runs a single Ollama chat (streaming or not) on a background thread.

    When the model has the ``tools`` capability it can ask for tools to be
    executed.  The results are fed back into the conversation and the model is
    given another turn, up to ``max_tool_rounds`` times.
    """

    # Emitted for each streaming chunk (content delta) or once for non-streaming
    chunk_received = Signal(str)
    # Emitted when the model produces chain-of-thought (thinking models)
    thinking_received = Signal(str)
    # Emitted as soon as the backend accepted the request and started replying
    connected = Signal()
    # Emitted with final statistics (tokens, durations) when the turn ends
    stats_received = Signal(object)  # dict: eval_count, eval_duration, total_duration, load_duration
    # Emitted when the model calls a tool: (tool name, arguments, display text)
    tool_called = Signal(str, object, str)
    # The answer text changed (tool-call JSON was removed): the new full text
    content_replaced = Signal(str)
    # Emitted when the stream/completion finishes
    finished = Signal(str)
    # Emitted on error
    error = Signal(str)

    def __init__(
        self,
        client: OllamaClient,
        model: str,
        messages: list[ChatMessage],
        stream: bool = True,
        temperature: float = 0.7,
        think: Optional[bool] = None,
        tools: Optional[list[dict]] = None,
        tool_runner: Optional[Callable[[str, dict], Any]] = None,
        max_tool_rounds: int = 8,
    ) -> None:
        super().__init__()
        self._client = client
        self._model = model
        self._messages = messages
        self._stream = stream
        self._temperature = temperature
        self._think = think
        self._tools = tools
        self._tool_runner = tool_runner
        self._max_tool_rounds = max_tool_rounds
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            full = self._run_chat()
            self.finished.emit(full)
        except Exception as exc:  # noqa: BLE001 — surface network/model errors to UI
            self.error.emit(str(exc))

    # ------------------------------------------------------------------ chat

    def _run_chat(self) -> str:
        """One turn, including any tool calls the model asks for."""
        messages = list(self._messages)
        full = ""
        first = True

        for round_index in range(self._max_tool_rounds + 1):
            last_round = round_index >= self._max_tool_rounds
            iterator: Iterator[dict] = self._client.chat(
                model=self._model,
                messages=messages,
                stream=self._stream,
                temperature=self._temperature,
                think=self._think,
                tools=None if last_round else self._tools,
            )

            tool_calls: list[dict] = []
            round_text = ""
            recovered_from_text = False

            if self._stream:
                for chunk in iterator:
                    if self._cancel:
                        break

                    message = chunk.get("message") or {}
                    thinking = message.get("thinking") or ""
                    if thinking:
                        self.thinking_received.emit(thinking)

                    content = message.get("content") or ""
                    if content:
                        round_text += content
                        full += content
                        self.chunk_received.emit(content)

                    calls = message.get("tool_calls") or []
                    if calls:
                        tool_calls.extend(calls)
                    elif not tool_calls:
                        # Some models print the tool call as plain JSON
                        # instead of using the structured field.
                        recovered = parse_tool_calls(round_text)
                        if recovered:
                            tool_calls.extend(recovered)
                            recovered_from_text = True

                    if first:
                        # The backend accepted the request — we are connected.
                        # Emitted last so the reasoning/content of the first
                        # chunk already updated the UI state.
                        self.connected.emit()
                        first = False

                    if chunk.get("done"):
                        self.stats_received.emit(
                            {
                                "eval_count": int(chunk.get("eval_count") or 0),
                                "eval_duration": int(chunk.get("eval_duration") or 0),
                                "total_duration": int(chunk.get("total_duration") or 0),
                                "load_duration": int(chunk.get("load_duration") or 0),
                            }
                        )
                        break
                if first:
                    # Empty response — still report a successful connection.
                    self.connected.emit()
            else:
                self.connected.emit()
                message = iterator.get("message") or {}
                thinking = message.get("thinking") or ""
                if thinking:
                    self.thinking_received.emit(thinking)
                content = message.get("content") or ""
                round_text = content
                tool_calls = message.get("tool_calls") or []
                if not tool_calls:
                    tool_calls = parse_tool_calls(content)
                    recovered_from_text = bool(tool_calls)
                if content:
                    full += content
                    self.chunk_received.emit(content)

            if not tool_calls or self._tool_runner is None or self._cancel:
                break

            # The model printed its tool call as text — take it out of the
            # answer before it is shown or stored.
            if recovered_from_text and round_text:
                cleaned = strip_tool_calls_from_content(round_text)
                full = full[: len(full) - len(round_text)] + cleaned
                self.content_replaced.emit(full)

            # Run the tools the model asked for and feed the results back.
            messages.append(
                ChatMessage(role="assistant", content="", tool_calls=tool_calls)
            )
            for call in tool_calls:
                function = call.get("function") or {}
                name = str(function.get("name") or "")
                arguments = function.get("arguments") or {}
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                result = self._tool_runner(name, arguments)
                display = getattr(result, "display", "") or str(result)
                content = getattr(result, "content", "") or str(result)
                self.tool_called.emit(name, arguments, display)
                messages.append(
                    ChatMessage(role="tool", content=content, tool_name=name)
                )

        return full


class OllamaThread(QThread):
    """Convenience QThread wrapper that owns an OllamaWorker."""

    def __init__(self, worker: OllamaWorker, parent=None) -> None:
        super().__init__(parent)
        self._worker = worker

    def run(self) -> None:
        self._worker.run()

    @property
    def worker(self) -> OllamaWorker:
        return self._worker
