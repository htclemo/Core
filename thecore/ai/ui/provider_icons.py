"""Provider icons for the model/provider selector.

The icons are drawn with ``QPainter`` instead of shipped as image files: they
stay crisp at any DPI, follow the theme colours and need no assets.

Three providers are distinguished:

* **local** — the LLM runs on this machine (Ollama): a chip on a board.
* **cloud** — the LLM runs somewhere else (Gemini, Groq, OpenRouter…): a cloud.
* **terminal** — OpenCode's own console: a prompt.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

# Theme colours (kept in sync with thecore/styles.py).
_ACCENT = QColor("#4de1ff")
_GREEN = QColor("#39ff14")
_YELLOW = QColor("#ffe81f")
_MUTED = QColor("#6f92a8")
_TEXT = QColor("#e0e0e0")


def _canvas(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    return pixmap


def _painter(pixmap: QPixmap) -> QPainter:
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    return painter


def local_icon(size: int = 18) -> QIcon:
    """A CPU chip — the model runs on this machine."""
    pixmap = _canvas(size)
    painter = _painter(pixmap)
    s = size
    pad = s * 0.22
    pen = QPen(_ACCENT)
    pen.setWidthF(max(1.0, s * 0.07))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    # The chip body.
    body = QRectF(pad, pad, s - 2 * pad, s - 2 * pad)
    painter.drawRoundedRect(body, s * 0.08, s * 0.08)

    # The pins.
    painter.setPen(QPen(_ACCENT, max(1.0, s * 0.06)))
    for i in range(3):
        offset = body.top() + body.height() * (i + 1) / 4.0
        painter.drawLine(
            QPointF(body.left() - pad * 0.7, offset),
            QPointF(body.left(), offset),
        )
        painter.drawLine(
            QPointF(body.right(), offset),
            QPointF(body.right() + pad * 0.7, offset),
        )
        painter.drawLine(
            QPointF(offset, body.top() - pad * 0.7),
            QPointF(offset, body.top()),
        )
        painter.drawLine(
            QPointF(offset, body.bottom()),
            QPointF(offset, body.bottom() + pad * 0.7),
        )

    painter.end()
    return QIcon(pixmap)


def cloud_icon(size: int = 18) -> QIcon:
    """A cloud — the model runs somewhere else."""
    pixmap = _canvas(size)
    painter = _painter(pixmap)
    s = size

    path = QPainterPath()
    path.moveTo(s * 0.20, s * 0.68)
    path.cubicTo(s * 0.08, s * 0.68, s * 0.06, s * 0.50, s * 0.18, s * 0.44)
    path.cubicTo(s * 0.20, s * 0.28, s * 0.42, s * 0.22, s * 0.51, s * 0.34)
    path.cubicTo(s * 0.66, s * 0.26, s * 0.86, s * 0.36, s * 0.84, s * 0.50)
    path.cubicTo(s * 0.94, s * 0.54, s * 0.92, s * 0.68, s * 0.80, s * 0.68)
    path.closeSubpath()

    painter.setPen(QPen(_GREEN, max(1.0, s * 0.07), Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


def terminal_icon(size: int = 18) -> QIcon:
    """A prompt — OpenCode's own console."""
    pixmap = _canvas(size)
    painter = _painter(pixmap)
    s = size

    pen = QPen(_YELLOW)
    pen.setWidthF(max(1.0, s * 0.08))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    frame = QRectF(s * 0.14, s * 0.22, s * 0.72, s * 0.56)
    painter.drawRoundedRect(frame, s * 0.10, s * 0.10)

    # The ">" chevron and the underscore of a shell prompt.
    painter.drawLine(
        QPointF(s * 0.30, s * 0.40), QPointF(s * 0.44, s * 0.50)
    )
    painter.drawLine(
        QPointF(s * 0.44, s * 0.50), QPointF(s * 0.30, s * 0.60)
    )
    painter.drawLine(
        QPointF(s * 0.52, s * 0.62), QPointF(s * 0.70, s * 0.62)
    )
    painter.end()
    return QIcon(pixmap)


def provider_icon(kind: str, size: int = 18) -> QIcon:
    """The icon for a provider kind: ``local``, ``cloud`` or ``terminal``."""
    if kind == "local":
        return local_icon(size)
    if kind == "cloud":
        return cloud_icon(size)
    if kind == "terminal":
        return terminal_icon(size)
    return QIcon()
