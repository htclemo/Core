"""Async-friendly Ollama REST client (runs in a QThread so the UI stays responsive)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Iterator, Optional

# ChatMessage lives in conversation.py — it carries the images and the tool
# calls as well, so there must be exactly one definition of it.
from thecore.ai.conversation import ChatMessage


@dataclass
class OllamaModel:
    name: str
    size_bytes: int = 0
    digest: str = ""
    modified_at: str = ""

    @property
    def size_gb(self) -> float:
        return self.size_bytes / (1024**3)


@dataclass
class OllamaClient:
    base_url: str = "http://127.0.0.1:11434"
    timeout_seconds: float = 30.0

    def _post(self, path: str, payload: dict, stream: bool = False, timeout: float | None = None):
        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if stream:
            return self._stream_lines(req)
        wait = self.timeout_seconds if timeout is None else timeout
        with urllib.request.urlopen(req, timeout=wait) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _stream_lines(self, req: urllib.request.Request) -> Iterator[dict]:
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    # ---- API calls ----

    def list_models(self, timeout: float | None = None) -> list[OllamaModel]:
        """GET /api/tags — list locally available models."""
        url = f"{self.base_url}/api/tags"
        wait = self.timeout_seconds if timeout is None else timeout
        with urllib.request.urlopen(url, timeout=wait) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        models = []
        for m in payload.get("models", []):
            models.append(
                OllamaModel(
                    name=m.get("name", ""),
                    size_bytes=int(m.get("size", 0) or 0),
                    digest=m.get("digest", ""),
                    modified_at=m.get("modified_at", ""),
                )
            )
        return models

    def is_available(self) -> bool:
        try:
            self.list_models()
            return True
        except Exception:
            return False

    def show_model(self, name: str, timeout: float | None = None) -> dict:
        """POST /api/show — get model details (size, parameters, etc.)."""
        return self._post("/api/show", {"name": name}, timeout=timeout)

    def model_capabilities(self, name: str, timeout: float | None = None) -> list[str]:
        """Return the capability list of a model (e.g. ["completion", "thinking"])."""
        try:
            payload = self.show_model(name, timeout=timeout)
        except Exception:
            return []
        caps = payload.get("capabilities") or []
        if isinstance(caps, list):
            return [str(c).lower() for c in caps]
        return []

    def supports_thinking(self, name: str) -> bool:
        """True when the model can expose chain-of-thought via `message.thinking`."""
        return "thinking" in self.model_capabilities(name)

    def supports_tools(self, name: str) -> bool:
        """True when the model can call tools."""
        return "tools" in self.model_capabilities(name)

    def supports_vision(self, name: str) -> bool:
        """True when the model can look at images."""
        return "vision" in self.model_capabilities(name)

    def chat(
        self,
        model: str,
        messages: list[ChatMessage],
        stream: bool = True,
        temperature: float = 0.7,
        think: Optional[bool] = None,
        tools: Optional[list[dict]] = None,
    ):
        """POST /api/chat — send a chat completion, optionally streaming."""
        payload = {
            "model": model,
            "messages": [self._message_payload(m) for m in messages],
            "stream": stream,
            "options": {"temperature": temperature},
        }
        # Only send "think" when explicitly requested — models without reasoning
        # support reject the request with an error.
        if think is not None:
            payload["think"] = bool(think)
        # Tool definitions let the model ask for tools to be executed.
        if tools:
            payload["tools"] = tools
        return self._post("/api/chat", payload, stream=stream)

    @staticmethod
    def _message_payload(message: ChatMessage) -> dict:
        """One chat message, including any attached images."""
        payload: dict = {"role": message.role, "content": message.content}
        images = getattr(message, "images", None)
        if images:
            # Ollama expects base64-encoded images without a data: prefix.
            payload["images"] = [str(image) for image in images]
        tool_name = getattr(message, "tool_name", "")
        if message.role == "tool" and tool_name:
            payload["tool_name"] = tool_name
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            payload["tool_calls"] = tool_calls
        return payload

    def generate(
        self,
        model: str,
        prompt: str,
        stream: bool = True,
        temperature: float = 0.7,
    ):
        """POST /api/generate — simple completion."""
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "options": {"temperature": temperature},
        }
        return self._post("/api/generate", payload, stream=stream)

    def pull_model(self, name: str):
        """POST /api/pull — download a model (streaming progress)."""
        return self._post("/api/pull", {"name": name}, stream=True)
