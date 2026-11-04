"""Background worker that loads an Ollama model without freezing the UI.

``ModelTracker.measure_load`` blocks for as long as Ollama takes to pull the
weights into VRAM/RAM (seconds for a 7B model, much longer for 16B).  Running
it on the GUI thread freezes the whole application — the loading indicator
cannot even animate, because its timer never gets to fire.

This worker moves the measurement onto a ``QThread`` so the window stays
responsive and the spinner keeps turning.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QThread, Signal

from thecore.ai.model_tracker import ModelMemoryDelta, ModelTracker


class ModelLoadWorker(QThread):
    """Loads a model on a worker thread and reports the memory delta."""

    # The model was loaded; carries a ModelMemoryDelta.
    loaded = Signal(object)
    # The load failed (reason text).
    failed = Signal(str)

    def __init__(
        self,
        tracker: ModelTracker,
        model_name: str,
        model_size_gb: float,
        load_call: Callable[[], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._tracker = tracker
        self._model_name = model_name
        self._model_size_gb = model_size_gb
        self._load_call = load_call

    def run(self) -> None:  # noqa: D102 — QThread API
        try:
            delta = self._tracker.measure_load(
                self._model_name, self._model_size_gb, self._load_call
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.loaded.emit(delta)
