"""Dense per-core activity strip — hologram bars."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget


class CoreStrip(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._values: list[float] = []
        self.setMinimumHeight(36)
        self.setMaximumHeight(48)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_values(self, values: list[float]) -> None:
        self._values = list(values)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 — Qt API
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w = self.width()
        h = self.height()
        painter.fillRect(0, 0, w, h, QColor("#071525"))
        painter.setPen(QColor("#1a4d66"))
        painter.drawRect(0, 0, w - 1, h - 1)

        if not self._values:
            return

        n = len(self._values)
        gap = 1
        bar_w = max(2.0, (w - gap * (n + 1)) / n)

        for i, val in enumerate(self._values):
            pct = max(0.0, min(100.0, float(val))) / 100.0
            bar_h = max(2.0, (h - 4) * pct)
            x = gap + i * (bar_w + gap)
            y = h - 2 - bar_h
            if pct >= 0.9:
                color = QColor("#ff2a2a")
            elif pct >= 0.75:
                color = QColor("#ff9f1a")
            else:
                color = QColor("#4de1ff")
            painter.fillRect(QRectF(x, y, bar_w, bar_h), color)
