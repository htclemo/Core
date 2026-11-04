"""QThread worker for free cloud LLM providers.

Mirrors :class:`thecore.ai.worker.OllamaWorker` so the chat panel can drive a
local Ollama model and a cloud model through the same code path.
"""

from __future__ import annotations

from typing import Iterator, Optional

from PySide6.QtCore import QObject, QThread, Signal

from thecore.ai.cloud_client import (
    CloudClient,
    configured_providers,
    load_key,
    provider_for,
)


class CloudWorker(QObject):
    """Runs a single cloud chat (streaming) on a background thread."""

    # Emitted for each streaming chunk.
    chunk_received = Signal(str)
    # Emitted as soon as the provider accepted the request.
    connected = Signal()
    # Emitted with the final reply when the turn ends.
    finished = Signal(str)
    # Emitted on error.
    error = Signal(str)

    def __init__(
        self,
        client: CloudClient,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
    ) -> None:
        super().__init__()
        self._client = client
        self._model = model
        self._messages = messages
        self._temperature = temperature
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            iterator: Iterator[str] = self._client.chat_stream(
                self._model, self._messages, self._temperature
            )
            full = ""
            first = True
            for piece in iterator:
                if self._cancel:
                    break
                if first:
                    self.connected.emit()
                    first = False
                full += piece
                self.chunk_received.emit(piece)
            if first:
                self.connected.emit()
            self.finished.emit(full)
        except Exception as exc:  # noqa: BLE001 — surface provider errors to the UI
            self.error.emit(str(exc))


class CloudThread(QThread):
    """Convenience QThread wrapper that owns a CloudWorker."""

    def __init__(self, worker: CloudWorker, parent=None) -> None:
        super().__init__(parent)
        self._worker = worker

    def run(self) -> None:
        self._worker.run()

    @property
    def worker(self) -> CloudWorker:
        return self._worker


# ---------------------------------------------------------------------- catalogue


class CloudListWorker(QObject):
    """Reload one provider's live model list."""

    log = Signal(str)
    models = Signal(list)
    failed = Signal(str)

    def __init__(self, client: CloudClient) -> None:
        super().__init__()
        self._client = client

    def run(self) -> None:
        name = self._client.provider.name
        self.log.emit(f"REFRESH  {name}  GET {self._client.provider.base_url}/models")
        try:
            found = self._client.list_models()
        except Exception as exc:  # noqa: BLE001
            self.log.emit(f"REFRESH  {name}  FAILED  {exc}")
            self.failed.emit(str(exc))
            return
        free = sum(1 for model in found if model.free)
        self.log.emit(f"REFRESH  {name}  {len(found)} models, {free} marked free")
        self.models.emit(found)


class CloudListThread(QThread):
    def __init__(self, worker: CloudListWorker, parent=None) -> None:
        super().__init__(parent)
        self._worker = worker

    def run(self) -> None:
        self._worker.run()


class CloudPingWorker(QObject):
    """Ping every model. Keep the ones that answer and are free."""

    log = Signal(str)
    kept = Signal(list)
    finished = Signal()

    def __init__(self, client: CloudClient, models: list) -> None:
        super().__init__()
        self._client = client
        self._models = list(models)

    def run(self) -> None:
        alive = []
        total = len(self._models)
        self.log.emit(f"PING  {total} models on {self._client.provider.name}")
        for index, model in enumerate(self._models, start=1):
            label = getattr(model, "id", str(model))
            if not getattr(model, "free", False):
                self.log.emit(f"PING  {index}/{total}  {label}  removed, not free")
                continue
            self.log.emit(f"PING  {index}/{total}  {label}  …")
            try:
                reply = self._client.ping(label)
            except Exception as exc:  # noqa: BLE001
                self.log.emit(f"PING  {index}/{total}  {label}  removed  {exc}")
                continue
            alive.append(model)
            self.log.emit(f"PING  {index}/{total}  {label}  ok  {reply[:60]}")
        self.log.emit(f"PING  kept {len(alive)} of {total}")
        self.kept.emit(alive)
        self.finished.emit()


class CloudPingThread(QThread):
    def __init__(self, worker: CloudPingWorker, parent=None) -> None:
        super().__init__(parent)
        self._worker = worker

    def run(self) -> None:
        self._worker.run()


class CloudCatalogueWorker(QObject):
    """Fetches the model list of every provider that has a key stored.

    The network call must not run on the GUI thread — a slow provider would
    freeze the whole window.
    """

    # Emitted per provider: (provider id, models)
    provider_models = Signal(str, list)
    # Emitted when every provider has been asked.
    finished = Signal()

    def run(self) -> None:
        for provider in configured_providers():
            resolved = provider_for(provider.id)
            if resolved is None:
                continue
            client = CloudClient(
                provider=resolved,
                api_key=load_key(provider.id),
                timeout_seconds=20.0,
            )
            try:
                models = client.list_models()
            except Exception:  # noqa: BLE001 — one bad provider must not stop the rest
                models = []
            self.provider_models.emit(provider.id, models)
        self.finished.emit()


class CloudCatalogueThread(QThread):
    """A thread that runs a :class:`CloudCatalogueWorker`."""

    def __init__(self, worker: CloudCatalogueWorker, parent=None) -> None:
        super().__init__(parent)
        self._worker = worker

    def run(self) -> None:
        self._worker.run()

    @property
    def worker(self) -> CloudCatalogueWorker:
        return self._worker
