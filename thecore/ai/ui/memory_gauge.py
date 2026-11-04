"""Pretty VRAM / RAM usage display for the chat header.

Two slim progress bars with a caption and a live value.  The numbers are the
memory used by **TheCore and Ollama only** — not the whole machine — e.g.::

    VRAM [▓░░░░░░]  35%  4,300 MB
    RAM  [▓░░░░░░]   6%  1.9 GB
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class _GaugeRow(QFrame):
    """A single labelled bar: ``LABEL [====----] 42%  value``."""

    def __init__(self, caption: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("memGaugeRow")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        self._caption = QLabel(caption)
        self._caption.setObjectName("memGaugeCaption")
        self._caption.setFixedWidth(34)

        self._bar = QProgressBar()
        self._bar.setObjectName("memGaugeBar")
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(7)
        self._bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._value = QLabel("—")
        self._value.setObjectName("memGaugeValue")
        self._value.setFixedWidth(126)
        self._value.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        layout.addWidget(self._caption)
        layout.addWidget(self._bar, stretch=1)
        layout.addWidget(self._value)

    def set_value(self, percent: Optional[float], text: str, state: str = "normal") -> None:
        if percent is None:
            self._bar.setValue(0)
        else:
            self._bar.setValue(max(0, min(100, int(round(percent)))))
        self._bar.setProperty("state", state)
        self._bar.style().unpolish(self._bar)
        self._bar.style().polish(self._bar)
        self._value.setText(text)


class MemoryGauge(QWidget):
    """VRAM + RAM usage widget shown in the chat header.

    The values are the memory used by TheCore and Ollama.  The percentage is
    relative to the machine's capacity, so the bar stays interpretable while
    the amount shown is only what this application actually uses.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("memGauge")
        self.setToolTip("VRAM and RAM used by TheCore and Ollama")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._vram = _GaugeRow("VRAM")
        self._ram = _GaugeRow("RAM")

        layout.addWidget(self._vram)
        layout.addWidget(self._ram)

    # ------------------------------------------------------------------ api

    def set_gpu(self, used_mb: float, total_mb: float, percent: float) -> None:
        """VRAM used by TheCore + Ollama (percent is of the whole card)."""
        state = "crit" if percent >= 90 else "warn" if percent >= 70 else "normal"
        self._vram.set_value(
            percent,
            f"{percent:3.0f}%  {used_mb:,.0f} MB",
            state,
        )

    def set_gpu_unavailable(self, text: str = "n/a") -> None:
        self._vram.set_value(None, text, "normal")

    def set_ram(self, used_gb: float, total_gb: float, percent: float) -> None:
        """RAM used by TheCore + Ollama (percent is of the whole machine)."""
        state = "crit" if percent >= 90 else "warn" if percent >= 70 else "normal"
        # One decimal: the amounts are small, so "0%" would look broken.
        self._ram.set_value(
            percent,
            f"{percent:4.1f}%  {used_gb:.2f} GB",
            state,
        )

    def set_unknown(self, text: str = "—") -> None:
        self._vram.set_value(None, text, "normal")
        self._ram.set_value(None, text, "normal")
