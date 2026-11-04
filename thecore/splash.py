"""TheCore — the start screen.

Shown while TheCore initialises.  It is a square panel in the CORE theme:
the logo, the tagline, the four pillars of the app and a boot log that types
itself out.  A soft sound accompanies the start-up and another one marks the
moment the system is ready.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

# The panel is square.
_SIZE = 560

_ASSETS = Path(__file__).resolve().parents[1] / "assets"

# Colours
_BG_TOP = QColor("#0d1310")
_BG_BOTTOM = QColor("#070a08")
_BORDER = QColor("#1e2b23")
_CARD = QColor("#151a17")
_CARD_BORDER = QColor("#212a24")
_ACCENT = QColor("#2ee6d0")
_ACCENT_DIM = QColor("#128a86")
_PLATFORM = "Linux" if sys.platform.startswith("linux") else "Windows" if sys.platform == "win32" else "this system"
_TEXT = QColor("#eef4f0")
_MUTED = QColor("#8aa396")
_LOG_BG = QColor("#0c100e")
_LOG_BORDER = QColor("#1a2620")

# The four pillars of the app.
PILLARS: tuple[tuple[str, str, str], ...] = (
    ("AI Intelligence", "Understand and generate code.", "brain"),
    ("Live Coding", "Edit and iterate instantly.", "bolt"),
    ("Smart Debugging", "Find and fix problems.", "bug"),
    ("Execution", "Test code in your workflow.", "terminal"),
)

# The boot log: (left label, right label).  The right side turns green.
_BOOT_LOG: list[tuple[str, str]] = [
    ("core modules", "ready"),
    ("ai backend", "ready"),
    ("ollama bridge", "ready"),
    ("opencode bridge", "ready"),
    ("gpu telemetry", "ready"),
    ("workspace index", "ready"),
    ("interface", "ready"),
]

# The log panel is a small console: it shows the last few lines only, so the
# text always stays inside the border and the older lines scroll off.
_LOG_VISIBLE = 5
_LOG_LINE = 15
_LOG_PANEL_TOP = 358
_LOG_PANEL_HEIGHT = 18 + _LOG_VISIBLE * _LOG_LINE + 12


def _logo_pixmap() -> QPixmap:
    """The app icon, cached so the start screen can draw the same mark."""
    cached = getattr(_logo_pixmap, "image", None)
    if cached is not None:
        return cached
    path = _ASSETS / "core_icon.png"
    image = QPixmap(str(path)) if path.is_file() else QPixmap()
    _logo_pixmap.image = image
    return image


def _play(name: str) -> None:
    """Play a WAV from the assets folder (silently skipped when unavailable)."""
    if os.environ.get("THECORE_NO_SOUND"):
        return
    if os.name != "nt":
        return
    path = _ASSETS / name
    if not path.is_file():
        return
    try:
        import winsound

        winsound.PlaySound(
            str(path),
            winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
        )
    except Exception:  # noqa: BLE001 — no audio device must not break the start-up
        pass


class StartScreen(QWidget):
    """The CORE start screen."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(_SIZE, _SIZE)

        # Animation state
        self._angle = 0.0
        self._log_index = 0
        self._progress = 0.0
        self._status = "Starting"
        self._cursor_on = True
        self._finished = False

        self._title_font = QFont("Segoe UI")
        self._title_font.setPointSize(30)
        self._title_font.setBold(True)
        self._title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)

        self._tag_font = QFont("Segoe UI")
        self._tag_font.setPointSize(10)
        self._tag_font.setBold(True)
        self._tag_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)

        self._mono_font = QFont("Cascadia Code")
        if not QFontMetrics(self._mono_font).horizontalAdvance("M"):
            self._mono_font = QFont("Consolas")
        self._mono_font.setPointSize(9)

        # The emblem turns.
        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._on_spin)
        self._spin_timer.start(50)

        # The boot log grows, the bar fills.
        self._log_timer = QTimer(self)
        self._log_timer.timeout.connect(self._on_log_tick)
        self._log_timer.start(420)

        # The cursor blinks.
        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._on_cursor)
        self._cursor_timer.start(450)

        self._centre()
        _play("loading.wav")

    # ------------------------------------------------------------------ life cycle

    def showEvent(self, event) -> None:  # noqa: N802 — Qt API
        super().showEvent(event)
        self._centre()

    def _centre(self) -> None:
        from PySide6.QtWidgets import QApplication

        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.geometry()
        self.move(
            (geometry.width() - self.width()) // 2,
            (geometry.height() - self.height()) // 2,
        )

    def set_status(self, text: str, progress: float | None = None) -> None:
        """Show the step that is actually running, not a fake boot log."""
        self._status = text
        if progress is not None:
            self._progress = max(0.0, min(1.0, progress))
        self.update()

    def finish_and_accept(self) -> None:
        """Stop the animations and mark the screen as finished."""
        self._finished = True
        self._spin_timer.stop()
        self._log_timer.stop()
        self._cursor_timer.stop()
        self._progress = 1.0
        self.update()
        _play("ready.wav")

    # ------------------------------------------------------------------ animation

    def _on_spin(self) -> None:
        self._angle = (self._angle + 2.4) % 360.0
        self.update()

    def _on_cursor(self) -> None:
        self._cursor_on = not self._cursor_on
        self.update()

    def _on_log_tick(self) -> None:
        if self._log_index < len(_BOOT_LOG):
            self._log_index += 1
        if self._status == "Starting":
            target = min(0.3, self._log_index / len(_BOOT_LOG))
            self._progress += (target - self._progress) * 0.35
        self.update()

    # ------------------------------------------------------------------ painting

    def paintEvent(self, event) -> None:  # noqa: N802 — Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        size = self.size()
        radius = 20.0
        panel = QRectF(0.5, 0.5, size.width() - 1, size.height() - 1)

        # --- the panel ---
        path = QPainterPath()
        path.addRoundedRect(panel, radius, radius)
        painter.setClipPath(path)

        background = QLinearGradient(0, 0, 0, size.height())
        background.setColorAt(0.0, _BG_TOP)
        background.setColorAt(1.0, _BG_BOTTOM)
        painter.fillPath(path, QBrush(background))

        # A soft green glow behind the logo.
        glow = QRadialGradient(QPointF(68, 58), 190)
        glow.setColorAt(0.0, QColor(46, 230, 208, 48))
        glow.setColorAt(0.5, QColor(18, 138, 134, 16))
        glow.setColorAt(1.0, QColor(46, 230, 208, 0))
        painter.fillRect(panel, glow)

        # A faint screen grid.
        painter.setPen(QPen(QColor(255, 255, 255, 6), 1))
        for x in range(0, size.width() + 1, 30):
            painter.drawLine(QPointF(x, 0), QPointF(x, size.height()))
        for y in range(0, size.height() + 1, 30):
            painter.drawLine(QPointF(0, y), QPointF(size.width(), y))

        # --- the logo and the title ---
        self._paint_logo(painter, QPointF(40, 30))
        self._paint_header(painter)
        self._paint_pillars(painter)
        self._paint_log(painter)
        self._paint_progress(painter)

        # --- the border and the corner brackets ---
        painter.setClipPath(QPainterPath())
        painter.setPen(QPen(_BORDER, 1))
        path = QPainterPath()
        path.addRoundedRect(panel, radius, radius)
        painter.drawPath(path)
        self._paint_brackets(painter, panel)

    # ------------------------------------------------------------------ parts

    def _paint_logo(self, painter: QPainter, top_left: QPointF) -> None:
        """The same rounded C mark used as the app icon."""
        tile = QRectF(top_left.x(), top_left.y(), 56, 56)
        pixmap = _logo_pixmap()
        if not pixmap.isNull():
            painter.drawPixmap(tile.toRect(), pixmap)
            return
        path = QPainterPath()
        path.addRoundedRect(tile, 14, 14)
        painter.fillPath(path, QBrush(QColor(8, 16, 18)))
        painter.setPen(QPen(_ACCENT, 1.6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    def _paint_header(self, painter: QPainter) -> None:
        """CORE, the tagline, the LIVE badge and the two lines of copy."""
        painter.setFont(self._title_font)
        painter.setPen(_TEXT)
        painter.drawText(QPointF(112, 68), "CORE")

        painter.setFont(self._tag_font)
        painter.setPen(_ACCENT)
        painter.drawText(
            QPointF(112, 88), "Code Orchestration & Real-time Engineering"
        )

        # The LIVE badge, top right.
        badge = QRectF(size_rect(self).right() - 74, 36, 46, 20)
        path = QPainterPath()
        path.addRoundedRect(badge, 10, 10)
        painter.fillPath(path, QBrush(QColor(61, 220, 132, 38)))
        painter.setPen(_ACCENT)
        painter.setFont(self._tag_font)
        painter.drawText(
            badge, int(Qt.AlignmentFlag.AlignCenter), "LIVE"
        )

        # A hairline under the header.
        painter.setPen(QPen(_BORDER, 1))
        painter.drawLine(QPointF(24, 100), QPointF(size_rect(self).right() - 24, 100))

        # The two lines of copy.
        painter.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        painter.setPen(_TEXT)
        painter.drawText(
            QPointF(24, 128), "Code. Observe. Refine. Execute."
        )
        painter.setFont(QFont("Segoe UI", 11))
        painter.setPen(_MUTED)
        painter.drawText(
            QPointF(24, 148), "Your code. Your AI. Your control."
        )
        painter.setFont(QFont("Segoe UI", 10))
        painter.setPen(_MUTED)
        painter.drawText(
            QPointF(24, 166),
            f"An AI-powered development environment for {_PLATFORM}.",
        )

    def _paint_pillars(self, painter: QPainter) -> None:
        """The four feature cards."""
        left = 24
        right = size_rect(self).right() - 24
        gap = 12
        card_width = (right - left - gap) / 2
        card_height = 74
        top = 182

        for index, (title, description, glyph) in enumerate(PILLARS):
            column = index % 2
            row = index // 2
            x = left + column * (card_width + gap)
            y = top + row * (card_height + gap)

            card = QRectF(x, y, card_width, card_height)
            path = QPainterPath()
            path.addRoundedRect(card, 10, 10)
            painter.fillPath(path, QBrush(_CARD))
            painter.setPen(QPen(_CARD_BORDER, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

            # The glyph.
            painter.save()
            painter.translate(x + 24, y + 26)
            self._paint_glyph(painter, glyph)
            painter.restore()

            # The title and the description.
            painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            painter.setPen(_TEXT)
            painter.drawText(QPointF(x + 16, y + 48), title)
            painter.setFont(QFont("Segoe UI", 10))
            painter.setPen(_MUTED)
            painter.drawText(QPointF(x + 16, y + 64), description)

    def _paint_glyph(self, painter: QPainter, glyph: str) -> None:
        """One small green line icon."""
        pen = QPen(_ACCENT)
        pen.setWidthF(1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if glyph == "brain":
            path = QPainterPath()
            path.moveTo(0, -7)
            path.cubicTo(-6, -7, -7, 2, -3, 6)
            path.cubicTo(-1, 7, 0, 3, 0, 3)
            path.cubicTo(0, 3, 1, 7, 3, 6)
            path.cubicTo(7, 2, 6, -7, 0, -7)
            painter.drawPath(path)
            painter.drawLine(QPointF(0, -6.5), QPointF(0, 4))
        elif glyph == "bolt":
            path = QPainterPath()
            path.moveTo(1, -8)
            path.lineTo(-5, 1)
            path.lineTo(-0.5, 1)
            path.lineTo(-1, 8)
            path.lineTo(5, -1)
            path.lineTo(0.5, -1)
            path.closeSubpath()
            painter.drawPath(path)
        elif glyph == "bug":
            painter.drawEllipse(QPointF(0, 1), 4, 5.5)
            painter.drawEllipse(QPointF(0, -5.5), 3, 2.5)
            painter.drawLine(QPointF(-7, -2), QPointF(-4, -1))
            painter.drawLine(QPointF(7, -2), QPointF(4, -1))
            painter.drawLine(QPointF(-7, 3), QPointF(-4, 2))
            painter.drawLine(QPointF(7, 3), QPointF(4, 2))
        else:  # terminal
            painter.drawRoundedRect(QRectF(-7, -6, 14, 12), 2, 2)
            painter.drawLine(QPointF(-4, -1), QPointF(-1, 2))
            painter.drawLine(QPointF(-1, 2), QPointF(-4, 4))
            painter.drawLine(QPointF(1, 4), QPointF(4, 4))

    def _paint_log(self, painter: QPainter) -> None:
        """The boot log.

        The panel is a small console: it shows the last few lines only, so the
        text always stays inside the border.
        """
        panel = QRectF(
            24,
            _LOG_PANEL_TOP,
            size_rect(self).right() - 48,
            _LOG_PANEL_HEIGHT,
        )
        path = QPainterPath()
        path.addRoundedRect(panel, 10, 10)
        painter.fillPath(path, QBrush(_LOG_BG))
        painter.setPen(QPen(_LOG_BORDER, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        painter.setFont(self._mono_font)
        metrics = QFontMetrics(self._mono_font)

        # The rows: the lines that are done, plus the blinking cursor.
        rows: list[tuple[str, str, bool]] = []
        for index in range(self._log_index):
            label, state = _BOOT_LOG[index]
            rows.append((f"> {label}", f"{state} ✓", False))
        if self._log_index < len(_BOOT_LOG) and self._cursor_on:
            rows.append((f"> {_BOOT_LOG[self._log_index][0]} ", "", True))

        # Only the last few lines fit — the older ones scroll off.
        rows = rows[-_LOG_VISIBLE:]

        y = panel.top() + 18
        for left, right, is_cursor in rows:
            painter.setPen(_MUTED)
            painter.drawText(QPointF(panel.left() + 12, y), left)
            if right:
                painter.setPen(_ACCENT)
                painter.drawText(
                    QPointF(panel.right() - 12 - metrics.horizontalAdvance(right), y),
                    right,
                )
            elif is_cursor:
                painter.setPen(_ACCENT)
                painter.drawText(
                    QPointF(
                        panel.left() + 12 + metrics.horizontalAdvance(left),
                        y,
                    ),
                    "_",
                )
            y += _LOG_LINE

    def _paint_progress(self, painter: QPainter) -> None:
        """The progress bar."""
        left = 24
        right = size_rect(self).right() - 24
        # Below the log panel.
        top = _LOG_PANEL_TOP + _LOG_PANEL_HEIGHT + 12
        height = 5
        width = right - left

        track = QRectF(left, top, width, height)
        path = QPainterPath()
        path.addRoundedRect(track, height / 2, height / 2)
        painter.fillPath(path, QBrush(QColor(255, 255, 255, 14)))

        filled = QRectF(left, top, max(height, width * self._progress), height)
        path = QPainterPath()
        path.addRoundedRect(filled, height / 2, height / 2)
        gradient = QLinearGradient(left, 0, right, 0)
        gradient.setColorAt(0.0, _ACCENT_DIM)
        gradient.setColorAt(1.0, _ACCENT)
        painter.fillPath(path, QBrush(gradient))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.setFont(self._mono_font)
        painter.setPen(_MUTED)
        text = f"{int(self._progress * 100):>3}%"
        metrics = QFontMetrics(self._mono_font)
        painter.drawText(
            QPointF(right - metrics.horizontalAdvance(text), top + 22), text
        )
        painter.setPen(_ACCENT)
        painter.drawText(QPointF(left, top + 22), self._status)

    def _paint_brackets(self, painter: QPainter, panel: QRectF) -> None:
        """HUD-style corner brackets."""
        length = 26.0
        inset = 10.0
        pen = QPen(_ACCENT_DIM, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        left = panel.left() + inset
        right = panel.right() - inset
        top = panel.top() + inset
        bottom = panel.bottom() - inset

        painter.drawLine(QPointF(left, top), QPointF(left + length, top))
        painter.drawLine(QPointF(left, top), QPointF(left, top + length))
        painter.drawLine(QPointF(right - length, top), QPointF(right, top))
        painter.drawLine(QPointF(right, top), QPointF(right, top + length))
        painter.drawLine(QPointF(left, bottom - length), QPointF(left, bottom))
        painter.drawLine(QPointF(left, bottom), QPointF(left + length, bottom))
        painter.drawLine(QPointF(right - length, bottom), QPointF(right, bottom))
        painter.drawLine(QPointF(right, bottom - length), QPointF(right, bottom))


def size_rect(widget: QWidget) -> QRectF:
    """The widget's own rectangle as a float rectangle."""
    return QRectF(widget.rect())


# The old name still works, so older imports keep working.
SplashScreen = StartScreen
