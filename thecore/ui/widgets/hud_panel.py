"""Panel frame with Star Wars–style corner brackets."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget


class HudPanel(QFrame):
    def __init__(self, cool: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panelCool" if cool else "panel")
        self._accent = QColor("#4de1ff" if cool else "#ffe81f")
        self._body = QVBoxLayout(self)
        self._body.setContentsMargins(10, 8, 10, 8)
        self._body.setSpacing(4)

    @property
    def body(self) -> QVBoxLayout:
        return self._body

    def paintEvent(self, event) -> None:  # noqa: N802 — Qt API
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        pen = QPen(self._accent, 2)
        painter.setPen(pen)

        w = self.width() - 1
        h = self.height() - 1
        arm = 14

        # Top-left
        painter.drawLine(QPoint(0, arm), QPoint(0, 0))
        painter.drawLine(QPoint(0, 0), QPoint(arm, 0))
        # Top-right
        painter.drawLine(QPoint(w - arm, 0), QPoint(w, 0))
        painter.drawLine(QPoint(w, 0), QPoint(w, arm))
        # Bottom-left
        painter.drawLine(QPoint(0, h - arm), QPoint(0, h))
        painter.drawLine(QPoint(0, h), QPoint(arm, h))
        # Bottom-right
        painter.drawLine(QPoint(w - arm, h), QPoint(w, h))
        painter.drawLine(QPoint(w, h), QPoint(w, h - arm))

        # Inner scan line
        glow = QPen(QColor(self._accent.red(), self._accent.green(), self._accent.blue(), 60), 1)
        painter.setPen(glow)
        painter.drawLine(QPoint(8, 1), QPoint(w - 8, 1))
