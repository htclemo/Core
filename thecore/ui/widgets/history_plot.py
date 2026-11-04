"""Compact rolling sparkline — holographic grid."""

from __future__ import annotations

from collections import deque

import pyqtgraph as pg
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget


pg.setConfigOptions(antialias=True, background="#020915", foreground="#4de1ff")


class HistoryPlot(QWidget):
    def __init__(
        self,
        series: list[tuple[str, str]] | None = None,
        history: int = 60,
        y_max: float | None = 100.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._history = history
        self._fixed_y_max = y_max
        self._buffers: dict[str, deque[float]] = {}
        self._curves: dict[str, pg.PlotDataItem] = {}

        self._plot = pg.PlotWidget()
        self._plot.setMenuEnabled(False)
        self._plot.hideButtons()
        self._plot.showGrid(x=True, y=True, alpha=0.18)
        self._plot.setXRange(0, history - 1, padding=0)
        if y_max is not None:
            self._plot.setYRange(0, y_max, padding=0.02)
        self._plot.getAxis("bottom").setTicks([])
        self._plot.getAxis("left").setWidth(28)
        self._plot.getAxis("left").setPen(pg.mkPen("#1a4d66"))
        self._plot.getAxis("bottom").setPen(pg.mkPen("#1a4d66"))
        self._plot.getAxis("left").setTextPen(pg.mkPen("#6f92a8"))
        self._plot.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._plot.setMinimumHeight(0)

        default_series = series or [("value", "#ffe81f")]
        for name, color in default_series:
            buf: deque[float] = deque([0.0] * history, maxlen=history)
            self._buffers[name] = buf
            pen = pg.mkPen(color=color, width=2)
            self._curves[name] = self._plot.plot(list(buf), pen=pen, name=name)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._plot)

    def push(self, values: dict[str, float]) -> None:
        for name, value in values.items():
            if name not in self._buffers:
                continue
            self._buffers[name].append(float(value))
            self._curves[name].setData(list(self._buffers[name]))

        if self._fixed_y_max is None:
            peak = 1.0
            for buf in self._buffers.values():
                if buf:
                    peak = max(peak, max(buf))
            self._plot.setYRange(0, peak * 1.15, padding=0.02)
