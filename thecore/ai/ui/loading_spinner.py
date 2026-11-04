"""A small green "spinning clock" shown while a model is loading.

The header used to show a ``QLabel`` with a single rotating ASCII character
(``|`` ``/`` ``-`` ``\\``).  In a dark theme that reads as a small black box
rather than as activity, so the loading indicator is now a real widget that
paints a sweeping green dial — and can show the elapsed time next to it.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


class LoadingSpinner(QWidget):
    """A green dial with a sweeping hand, plus an optional caption."""

    def __init__(
        self,
        parent: QWidget | None = None,
        diameter: int = 24,
        color: str = "#39ff14",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("loadingSpinner")

        self._diameter = diameter
        self._color = QColor(color)
        self._angle = 0.0
        self._caption = ""
        self._running = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)

        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(diameter)
        self.hide()

    # ------------------------------------------------------------------ api

    def start(self, caption: str = "LOADING") -> None:
        """Start spinning and show the caption."""
        self._caption = caption
        self._running = True
        self._angle = 0.0
        if not self._timer.isActive():
            self._timer.start(55)
        self.setVisible(True)
        self._update_width()
        self.update()

    def stop(self) -> None:
        """Stop spinning and clear the caption."""
        self._running = False
        self._timer.stop()
        self._caption = ""
        self._update_width()
        self.update()

    def set_caption(self, text: str) -> None:
        """Update the text shown beside the dial."""
        if text == self._caption:
            return
        self._caption = text
        self._update_width()
        self.update()

    def _update_width(self) -> None:
        """Keep the widget exactly as wide as it needs to be."""
        self.setFixedWidth(self.sizeHint().width())
        self.updateGeometry()

    def is_spinning(self) -> bool:
        return self._running

    # ------------------------------------------------------------------ internals

    def _caption_font(self) -> QFont:
        """A font that is guaranteed to exist on the machine."""
        from PySide6.QtGui import QFontDatabase

        font = QFont(self.font())
        families = set(QFontDatabase.families())
        for name in ("Segoe UI", "Cascadia Code", "Consolas", "Arial"):
            if name in families:
                font = QFont(name)
                break
        font.setPointSize(max(8, font.pointSize() or 9))
        font.setBold(True)
        return font

    def _advance(self) -> None:
        self._angle = (self._angle + 14.0) % 360.0
        self.update()

    def _caption_width(self) -> int:
        if not self._caption:
            return 0
        from PySide6.QtGui import QFontMetrics

        return QFontMetrics(self._caption_font()).horizontalAdvance(self._caption) + 10

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt API
        from PySide6.QtCore import QSize

        return QSize(self._diameter + 8 + self._caption_width(), self._diameter + 4)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 — Qt API
        from PySide6.QtCore import QSize

        return QSize(self._diameter + 8, self._diameter + 4)

    def paintEvent(self, event) -> None:  # noqa: N802 — Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        d = self._diameter
        inset = 2.0
        rect = QRectF(inset, inset, d - 2 * inset, d - 2 * inset)

        # Dim track.
        painter.setPen(QPen(QColor("#2a2a2a"), 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(rect)

        if self._running:
            # Sweeping arc — a clock hand chasing its own tail.
            painter.setPen(
                QPen(self._color, 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            )
            painter.drawArc(
                rect,
                int(-self._angle * 16),
                int(100 * 16),
            )

            # The hand itself: from the centre out to the arc.
            tip = self._hand_tip(rect)
            painter.setPen(
                QPen(self._color, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            )
            painter.drawLine(rect.center(), tip)

            # Glowing head of the hand.
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._color)
            painter.drawEllipse(tip, 2.4, 2.4)
        else:
            # Idle: a dim dot in the middle.
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#3a3a3a"))
            painter.drawEllipse(rect.center(), 1.8, 1.8)

        # Caption.
        if self._caption:
            painter.setFont(self._caption_font())
            painter.setPen(self._color)
            painter.drawText(
                QRectF(
                    d + 6,
                    0,
                    self.width() - d - 6,
                    self.height(),
                ),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                self._caption,
            )

    def _hand_tip(self, rect: QRectF):
        """The point the hand points at, on the circle's edge."""
        import math

        angle = math.radians(self._angle - 90.0)
        radius = (rect.width() / 2.0) - 1.4
        cx = rect.center().x() + radius * math.cos(angle)
        cy = rect.center().y() + radius * math.sin(angle)
        from PySide6.QtCore import QPointF

        return QPointF(cx, cy)
