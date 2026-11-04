"""Capability icons for the model selector.

Instead of a text badge ("TOOLS · VISION · REASONING") the app shows a row of
icons — an eye for vision, a wrench for tools and a brain for reasoning —
each in the colour of its capability.

Two shapes are available:

* the **pill** with the icon *and* the name next to it, and
* the **compact** disc with the icon only, used next to the model name in the
  bottom-right corner.  The name stays available as a tooltip.

The icons are drawn with ``QPainter`` so they stay crisp at any DPI and
follow the theme.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QSize
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget

# One colour per capability.
_VISION = QColor("#ffe81f")
_TOOLS = QColor("#4de1ff")
_REASONING = QColor("#39ff14")
_OFF = QColor("#3a3a3a")


class CapabilityIcons(QWidget):
    """A row of capability icons."""

    def __init__(
        self, parent: QWidget | None = None, compact: bool = False
    ) -> None:
        super().__init__(parent)
        self.setObjectName("capabilityIcons")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._compact = compact
        self.setFixedHeight(22 if compact else 26)

        self._tools = False
        self._vision = False
        self._reasoning = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4 if compact else 5)
        self._layout = layout
        self._rebuild()

    # ------------------------------------------------------------------ api

    def set_capabilities(
        self, tools: bool = False, vision: bool = False, reasoning: bool = False
    ) -> None:
        """Show the capabilities the model has."""
        if (
            self._tools == tools
            and self._vision == vision
            and self._reasoning == reasoning
        ):
            return
        self._tools = tools
        self._vision = vision
        self._reasoning = reasoning
        self._rebuild()
        self.update()

    @property
    def has_any(self) -> bool:
        return self._tools or self._vision or self._reasoning

    def _rebuild(self) -> None:
        """(Re)create the icon widgets."""
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # Detach it right away — deleteLater() would leave the old
                # icons on screen until the event loop runs.
                widget.setParent(None)
                widget.deleteLater()

        entries = [
            ("tools", self._tools),
            ("vision", self._vision),
            ("reasoning", self._reasoning),
        ]
        for kind, active in entries:
            icon = _CapabilityIcon(kind, active, compact=self._compact)
            self._layout.addWidget(icon)
        self.setVisible(self.has_any)

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt API
        count = sum([self._tools, self._vision, self._reasoning])
        if self._compact:
            if not count:
                return QSize(0, 22)
            return QSize(count * 22 + (count - 1) * 4, 22)
        if not count:
            return QSize(0, 26)
        return QSize(count * 24 + (count - 1) * 5, 26)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 — Qt API
        return self.sizeHint()


class _CapabilityIcon(QWidget):
    """One capability: a coloured disc with the icon, optionally with a label."""

    LABELS = {
        "tools": "Tool Use",
        "vision": "Vision",
        "reasoning": "Reasoning",
    }

    def __init__(
        self,
        kind: str,
        active: bool,
        compact: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._kind = kind
        self._active = active
        self._compact = compact
        self.setObjectName("capabilityPill" if not compact else "capabilityDot")
        self._label = self.LABELS.get(kind, kind)
        self.setToolTip(self._label if active else f"{self._label} — not supported")

        self._font = QFont("Segoe UI")
        self._font.setPointSize(9)
        self._font.setBold(True)
        self.setFont(self._font)
        if compact:
            self.setFixedSize(22, 22)
        else:
            self.setFixedHeight(24)

    def _color(self) -> QColor:
        if not self._active:
            return _OFF
        return {
            "tools": _TOOLS,
            "vision": _VISION,
            "reasoning": _REASONING,
        }.get(self._kind, _OFF)

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt API
        if self._compact:
            return QSize(22, 22)
        text_width = QFontMetrics(self._font).horizontalAdvance(self._label)
        return QSize(text_width + 46, 24)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 — Qt API
        return self.sizeHint()

    def paintEvent(self, event) -> None:  # noqa: N802 — Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        colour = self._color()
        width = self.width()
        height = self.height()

        if self._compact:
            self._paint_disc(painter, colour, width, height)
            return

        # The pill.
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, width - 1, height - 1), height / 2, height / 2)
        if self._active:
            fill = QColor(colour)
            fill.setAlpha(34)
            painter.fillPath(path, fill)
            painter.setPen(QPen(colour, 1))
        else:
            painter.fillPath(path, QColor(255, 255, 255, 8))
            painter.setPen(QPen(QColor(255, 255, 255, 18), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # The icon.
        painter.save()
        painter.translate(13, height / 2)
        self._paint_glyph(painter, colour)
        painter.restore()

        # The label.
        painter.setFont(self._font)
        painter.setPen(colour)
        painter.drawText(
            QRectF(24, 0, width - 26, height),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            self._label,
        )

    def _paint_disc(
        self, painter: QPainter, colour: QColor, width: int, height: int
    ) -> None:
        """The compact shape: a round disc with the icon in the middle."""
        path = QPainterPath()
        path.addEllipse(QRectF(0.5, 0.5, width - 1, height - 1))
        if self._active:
            fill = QColor(colour)
            fill.setAlpha(34)
            painter.fillPath(path, fill)
            painter.setPen(QPen(colour, 1))
        else:
            painter.fillPath(path, QColor(255, 255, 255, 8))
            painter.setPen(QPen(QColor(255, 255, 255, 18), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        painter.save()
        painter.translate(width / 2, height / 2)
        self._paint_glyph(painter, colour, half=4.2)
        painter.restore()

    def _paint_glyph(
        self, painter: QPainter, colour: QColor, half: float = 5.0
    ) -> None:
        """Draw the icon of this capability."""
        pen = QPen(colour)
        pen.setWidthF(1.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if self._kind == "vision":
            self._draw_eye(painter, half)
        elif self._kind == "tools":
            self._draw_wrench(painter, half)
        else:
            self._draw_brain(painter, half)

    @staticmethod
    def _draw_eye(painter: QPainter, half: float) -> None:
        """An eye: a lens shape with a pupil."""
        path = QPainterPath()
        path.moveTo(-half, 0)
        path.quadTo(0, -half * 0.85, half, 0)
        path.quadTo(0, half * 0.85, -half, 0)
        painter.drawPath(path)
        painter.drawEllipse(QPointF(0, 0), half * 0.3, half * 0.3)

    @staticmethod
    def _draw_wrench(painter: QPainter, half: float) -> None:
        """A wrench: a shaft with an open jaw."""
        painter.drawLine(
            QPointF(-half * 0.75, half * 0.75),
            QPointF(half * 0.2, -half * 0.2),
        )
        jaw = QPainterPath()
        jaw.moveTo(half * 0.05, -half * 0.85)
        jaw.lineTo(half * 0.6, -half * 0.3)
        jaw.arcTo(
            QRectF(-half * 0.05, -half * 1.0, half * 1.5, half * 1.5),
            90,
            -180,
        )
        jaw.lineTo(half * 0.6, -half * 0.85)
        painter.drawPath(jaw)

    @staticmethod
    def _draw_brain(painter: QPainter, half: float) -> None:
        """A brain: two lobes split down the middle."""
        path = QPainterPath()
        path.moveTo(0, -half)
        path.cubicTo(
            -half * 0.95, -half * 0.95,
            -half, half * 0.25,
            -half * 0.45, half * 0.85,
        )
        path.cubicTo(
            -half * 0.2, half * 1.05,
            -half * 0.1, half * 0.6,
            0, half * 0.6,
        )
        path.cubicTo(
            half * 0.1, half * 0.6,
            half * 0.2, half * 1.05,
            half * 0.45, half * 0.85,
        )
        path.cubicTo(
            half, half * 0.25,
            half * 0.95, -half * 0.95,
            0, -half,
        )
        painter.drawPath(path)
        painter.drawLine(QPointF(0, -half * 0.92), QPointF(0, half * 0.6))
