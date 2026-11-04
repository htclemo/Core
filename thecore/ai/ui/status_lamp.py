"""Compact status lamp shown in the chat header.

A small LED-style indicator (green / red / yellow) next to a short label such
as ``OLLAMA``.  The detailed state (model name, load time, …) stays available
as a tooltip.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget


class StatusLamp(QWidget):
    """LED dot + caption, e.g. ``● OLLAMA``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusLampBox")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._dot = QFrame()
        self._dot.setObjectName("statusLamp")
        self._dot.setFixedSize(13, 13)
        self._dot.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._dot.setProperty("state", "offline")

        self._label = QLabel("OLLAMA")
        self._label.setObjectName("statusLampText")
        self._label.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(self._dot)
        layout.addWidget(self._label)

    # ------------------------------------------------------------------ api

    def set_status(self, text: str, state: str, tooltip: Optional[str] = None) -> None:
        """Update the caption, the lamp colour and the tooltip."""
        self._label.setText(text)
        self._dot.setProperty("state", state)
        self._dot.style().unpolish(self._dot)
        self._dot.style().polish(self._dot)
        self._label.setProperty("state", state)
        self._label.style().unpolish(self._label)
        self._label.style().polish(self._label)
        if tooltip is not None:
            self.setToolTip(tooltip)
            self._dot.setToolTip(tooltip)

    def set_text(self, text: str) -> None:
        self._label.setText(text)
