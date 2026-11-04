"""Compact single-line meter."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget


class Meter(QWidget):
    def __init__(
        self,
        label: str = "",
        cool: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._cool = cool

        self._label = QLabel(label)
        self._label.setObjectName("metricSecondary")
        self._label.setFixedWidth(42)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        if cool:
            self._bar.setObjectName("cool")

        self._value = QLabel("—")
        self._value.setObjectName("metricInline")
        self._value.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._value.setMinimumWidth(120)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._label)
        layout.addWidget(self._bar, stretch=1)
        layout.addWidget(self._value)

    def set_label(self, text: str) -> None:
        self._label.setText(text)

    def set_value(self, percent: float, detail: str | None = None) -> None:
        pct = max(0, min(100, int(round(percent))))
        self._bar.setValue(pct)
        self._value.setText(detail if detail is not None else f"{percent:.0f}%")

        if self._cool and percent < 75:
            name = "cool"
        elif percent >= 90:
            name = "crit"
        elif percent >= 75:
            name = "warn"
        else:
            name = "cool" if self._cool else ""
        self._bar.setObjectName(name)
        self._bar.style().unpolish(self._bar)
        self._bar.style().polish(self._bar)
