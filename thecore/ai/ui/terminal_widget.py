"""A real terminal emulator widget for Windows.

The OpenCode TUI only works when it is attached to a genuine terminal: it
queries the terminal's capabilities (DA1, ``?1016$p``, bracketed paste, …) and
refuses to draw anything sensible when the answers never come.  Piping it into
a GUI therefore produces *no* output at all.

This widget provides the missing half of that arrangement:

* a **ConPTY** pseudo console (via ``pywinpty``) so the child process sees a
  real TTY, and
* a **terminal emulator** (via ``pyte``) that interprets the VT sequences the
  child emits and paints the resulting screen.

The result is the genuine OpenCode console running inside TheCore.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from typing import Optional

import pyte
from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QKeyEvent,
    QPainter,
    QTextCursor,
)
from PySide6.QtWidgets import QWidget

try:
    from winpty import PtyProcess
except ImportError:  # pragma: no cover - Windows only
    PtyProcess = None  # type: ignore[assignment]


class _PosixPty:
    """A pywinpty-shaped PTY for Linux, so OpenCode gets a real terminal."""

    def __init__(self, argv: list[str], cwd: str, env: dict[str, str], dimensions: tuple[int, int]) -> None:
        import fcntl
        import pty
        import struct
        import termios

        rows, cols = dimensions
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        self._proc = subprocess.Popen(
            argv,
            stdin=slave,
            stdout=slave,
            stderr=slave,
            cwd=cwd,
            env=env,
            start_new_session=True,
        )
        os.close(slave)
        self._fd = master

    def read(self, size: int = 4096) -> str:
        data = os.read(self._fd, size)
        return data.decode("utf-8", "replace")

    def write(self, text: str) -> None:
        os.write(self._fd, text.encode("utf-8"))

    def isalive(self) -> bool:
        return self._proc.poll() is None

    def setwinsize(self, rows: int, cols: int) -> None:
        import fcntl
        import struct
        import termios

        fcntl.ioctl(self._fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    def close(self, force: bool = True) -> None:
        if self._proc.poll() is None:
            self._proc.terminate()
        try:
            os.close(self._fd)
        except OSError:
            pass


def _spawn_pty(argv: list[str], cwd: str, env: dict[str, str], dimensions: tuple[int, int]):
    if PtyProcess is not None:
        return PtyProcess.spawn(argv, cwd=cwd, env=env, dimensions=dimensions)
    if os.name != "nt":
        return _PosixPty(argv, cwd, env, dimensions)
    raise RuntimeError("pywinpty is not installed (pip install pywinpty).")


# --------------------------------------------------------------------------- palette

_ANSI_COLORS = {
    "black": "#1c1c1c",
    "red": "#e5484d",
    "green": "#39ff14",
    "brown": "#c99500",
    "yellow": "#ffe81f",
    "blue": "#4de1ff",
    "magenta": "#c77dff",
    "cyan": "#00d7c3",
    "white": "#d4d4d4",
    "brightblack": "#6b6b6b",
    "brightred": "#ff6b6b",
    "brightgreen": "#7cff7c",
    "brightbrown": "#ffd75f",
    "brightyellow": "#fff58a",
    "brightblue": "#7fe4ff",
    "brightmagenta": "#e0a3ff",
    "brightcyan": "#66fff2",
    "brightwhite": "#ffffff",
}

_DEFAULT_FG = QColor("#e0e0e0")
_DEFAULT_BG = QColor("#0d0d0d")


def _color(name: str, default: QColor) -> QColor:
    if not name or name == "default":
        return default
    hexcode = _ANSI_COLORS.get(name)
    if hexcode:
        return QColor(hexcode)
    if len(name) == 6:
        try:
            return QColor(f"#{name}")
        except Exception:  # noqa: BLE001
            return default
    return default


# --------------------------------------------------------------------------- widget


class TerminalWidget(QWidget):
    """A VT100/xterm-style terminal that hosts a child process on a ConPTY."""

    # The child process started.
    started = Signal()
    # The child process exited (exit code).
    finished = Signal(int)
    # A chunk of raw output arrived (for logging / status).
    output_received = Signal(str)
    # The child could not be started (reason text).
    failed = Signal(str)
    # Internal: marshals the child's exit onto the GUI thread.
    _exit_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("terminalWidget")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        self.setMinimumSize(320, 160)

        self._columns = 100
        self._lines = 30
        self._screen = pyte.HistoryScreen(self._columns, self._lines, history=5000)
        # ``proc.read()`` already returns decoded text, so the str-based
        # ``Stream`` is the right one here (``ByteStream`` would expect bytes).
        self._stream = pyte.Stream(self._screen)
        self._feed_errors = 0

        self._proc = None
        self._proc_lock = threading.Lock()
        self._reader: Optional[threading.Thread] = None
        self._stopping = False

        self._pending: "queue.Queue[str]" = queue.Queue()
        self._drain_timer = QTimer(self)
        self._drain_timer.timeout.connect(self._drain)
        self._drain_timer.start(16)  # ~60 fps

        self._font = QFont("Cascadia Mono")
        if not QFontMetrics(self._font).horizontalAdvance("M"):
            self._font = QFont("Consolas")
        self._font.setStyleHint(QFont.StyleHint.Monospace)
        self._font.setPixelSize(14)
        self._metrics = QFontMetrics(self._font)
        self._cell_w = max(1, self._metrics.horizontalAdvance("M"))
        self._cell_h = max(1, self._metrics.height())

        # Scrollback: how many lines the user has scrolled up.
        self._scroll_offset = 0
        self._max_scrollback = 0

        self._sel_anchor: Optional[tuple[int, int]] = None
        self._sel_cursor: Optional[tuple[int, int]] = None
        self._selected_text = ""

        self.setCursor(Qt.CursorShape.IBeamCursor)

    # ------------------------------------------------------------------ geometry

    def _recalc_size(self) -> None:
        """Fit the grid to the widget size and tell the child process."""
        width = max(1, self.width())
        height = max(1, self.height())
        cols = max(20, width // self._cell_w)
        lines = max(5, height // self._cell_h)
        if cols == self._columns and lines == self._lines:
            return
        self._columns = cols
        self._lines = lines
        self._screen.resize(lines, cols)
        self._proc_lock.acquire()
        proc = self._proc
        self._proc_lock.release()
        if proc is not None:
            try:
                proc.setwinsize(lines, cols)
            except Exception:  # noqa: BLE001
                pass
        self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802 — Qt API
        super().resizeEvent(event)
        self._recalc_size()

    # ------------------------------------------------------------------ lifecycle

    def is_running(self) -> bool:
        with self._proc_lock:
            proc = self._proc
        if proc is None:
            return False
        try:
            return bool(proc.isalive())
        except Exception:  # noqa: BLE001
            return False

    def start(
        self,
        argv: list[str],
        cwd: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
    ) -> bool:
        """Launch ``argv`` inside a ConPTY and show its output."""
        if PtyProcess is None and os.name == "nt":
            self.failed.emit("pywinpty is not installed (pip install pywinpty).")
            return False
        if self.is_running():
            return True

        self._stopping = False
        self._screen.reset()
        self._stream = pyte.Stream(self._screen)
        self._scroll_offset = 0

        # The child must start with the size of the widget, otherwise it
        # draws for the wrong number of columns and mouse coordinates are
        # off.  The widget may not be laid out yet, so a second sync follows
        # once the event loop has run.
        self._recalc_size()

        run_env = dict(env or os.environ)
        run_env.setdefault("TERM", "xterm-256color")
        run_env.setdefault("COLORTERM", "truecolor")
        run_env["COLUMNS"] = str(self._columns)
        run_env["LINES"] = str(self._lines)

        try:
            proc = _spawn_pty(
                argv,
                cwd or os.getcwd(),
                run_env,
                (self._lines, self._columns),
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Could not start {argv[0]}: {exc}")
            return False

        with self._proc_lock:
            self._proc = proc

        self._reader = threading.Thread(
            target=self._read_loop, args=(proc,), daemon=True
        )
        self._reader.start()
        self._exit_requested.connect(self._on_child_exit)
        self.started.emit()
        self.setFocus()
        # Re-sync the size once Qt has laid the widget out.
        QTimer.singleShot(250, self._recalc_size)
        return True

    def stop(self) -> None:
        """Terminate the child process and its console."""
        self._stopping = True
        with self._proc_lock:
            proc = self._proc
            self._proc = None
        if proc is not None:
            try:
                proc.close(force=True)
            except Exception:  # noqa: BLE001
                pass
        # Let the reader thread finish so it cannot outlive this widget.
        reader = self._reader
        if reader is not None and reader.is_alive():
            reader.join(timeout=1.5)
        self._reader = None

    def _read_loop(self, proc) -> None:
        """Pump the child's output into the queue (background thread)."""
        while not self._stopping:
            try:
                data = proc.read(4096)
            except EOFError:
                break
            except Exception:  # noqa: BLE001 — connection aborted on exit
                break
            if not data:
                break
            self._pending.put(data)
            # The widget can be destroyed while this thread is still reading
            # (the window closes first), so the signal may no longer exist.
            if self._stopping:
                break
            try:
                self.output_received.emit(data)
            except RuntimeError:
                break
        # Marshal the exit onto the GUI thread (a queued signal, not a
        # QTimer created on this worker thread).
        try:
            self._exit_requested.emit()
        except RuntimeError:
            pass

    def _on_child_exit(self) -> None:
        with self._proc_lock:
            proc = self._proc
        code = 0
        if proc is not None:
            try:
                code = int(proc.exitstatus or 0)
            except Exception:  # noqa: BLE001
                code = 0
        self.finished.emit(code)

    # ------------------------------------------------------------------ output

    def _drain(self) -> None:
        """Feed queued output into the emulator and repaint."""
        changed = False
        while True:
            try:
                data = self._pending.get_nowait()
            except queue.Empty:
                break
            try:
                self._stream.feed(data)
                changed = True
            except Exception as exc:  # noqa: BLE001
                # Never swallow this silently — a broken stream means a blank
                # terminal, which is exactly the bug we are trying to avoid.
                self._feed_errors += 1
                if self._feed_errors <= 3:
                    print(f"[terminal] feed error: {type(exc).__name__}: {exc}")
        if not changed:
            return
        self._max_scrollback = len(self._screen.history.top)
        if self._scroll_offset:
            # Keep the view pinned to the same content while scrolled up.
            self._scroll_offset = min(self._scroll_offset, self._max_scrollback)
        self.update()

    # ------------------------------------------------------------------ rendering

    def paintEvent(self, event) -> None:  # noqa: N802 — Qt API
        painter = QPainter(self)
        painter.fillRect(self.rect(), _DEFAULT_BG)

        font = self._font
        painter.setFont(font)
        metrics = self._metrics

        screen = self._screen
        cols = screen.columns
        lines = screen.lines

        # Work out which lines to paint: either the live screen, or history
        # lines above it when the user has scrolled up.
        history = list(screen.history.top)
        offset = self._scroll_offset

        if offset > 0 and history:
            start = max(0, len(history) - offset)
            visible = history[start : start + lines]
            for row, line in enumerate(visible):
                self._paint_line(painter, row, line, cols, metrics)
            # Blank out any remaining rows.
            for row in range(len(visible), lines):
                painter.fillRect(
                    QRect(0, row * self._cell_h, cols * self._cell_w, self._cell_h),
                    _DEFAULT_BG,
                )
        else:
            buffer = screen.buffer
            for row in range(lines):
                line = buffer.get(row, {})
                self._paint_line(painter, row, line, cols, metrics)

        # Cursor.
        if offset == 0 and not screen.cursor.hidden:
            cx = screen.cursor.x
            cy = screen.cursor.y
            if 0 <= cx < cols and 0 <= cy < lines:
                painter.setBrush(_DEFAULT_FG)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(
                    QRect(cx * self._cell_w, cy * self._cell_h, self._cell_w, self._cell_h)
                )

        # Selection highlight.
        self._paint_selection(painter)

    def _paint_line(self, painter: QPainter, row: int, line: dict, cols: int, metrics) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_DEFAULT_BG)
        painter.drawRect(
            QRect(0, row * self._cell_h, cols * self._cell_w, self._cell_h)
        )

        x = 0
        while x < cols:
            char = line.get(x)
            if char is None:
                x += 1
                continue
            data = char.data or " "
            fg = _color(char.fg, _DEFAULT_FG)
            bg = _color(char.bg, _DEFAULT_BG)
            if char.reverse:
                fg, bg = bg, fg
            if char.bold and char.fg not in ("default", ""):
                fg = fg.lighter(130)

            width = max(1, len(data))
            if bg != _DEFAULT_BG:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(bg)
                painter.drawRect(
                    QRect(x * self._cell_w, row * self._cell_h, width * self._cell_w, self._cell_h)
                )

            painter.setPen(fg)
            painter.drawText(
                QRect(
                    x * self._cell_w,
                    row * self._cell_h,
                    width * self._cell_w,
                    self._cell_h,
                ),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                data,
            )
            x += width

    # ------------------------------------------------------------------ selection

    def _selection_rects(self) -> list[tuple[int, int, int]]:
        """The selected cell ranges as (row, start_col, end_col) tuples."""
        if not self._sel_anchor or not self._sel_cursor:
            return []
        (r1, c1), (r2, c2) = self._sel_anchor, self._sel_cursor
        if r1 == r2:
            lo, hi = sorted((c1, c2))
            return [(r1, lo, hi + 1)]
        rects = []
        if c2 < c1:
            (r1, c1), (r2, c2) = (r2, c2), (r1, c1)
        rects.append((r1, c1, self._screen.columns))
        for row in range(r1 + 1, r2):
            rects.append((row, 0, self._screen.columns))
        rects.append((r2, 0, c2 + 1))
        return rects

    def _get_selected_text(self) -> str:
        """The selected text, joined the way a terminal would."""
        if self._scroll_offset:
            return ""
        rects = self._selection_rects()
        if not rects:
            return ""
        screen = self._screen
        out = []
        for row, start, end in rects:
            line = screen.buffer.get(row, {})
            text = "".join(
                (line.get(x).data if line.get(x) else " ") for x in range(start, end)
            )
            out.append(text)
        return "\n".join(out).strip("\n")

    def _paint_selection(self, painter: QPainter) -> None:
        rects = self._selection_rects()
        if not rects or self._scroll_offset:
            return
        # Highlight only the selected cells — filling the whole widget would
        # tint the entire terminal.
        for row, start, end in rects:
            painter.fillRect(
                QRect(
                    start * self._cell_w,
                    row * self._cell_h,
                    (end - start) * self._cell_w,
                    self._cell_h,
                ),
                QColor(77, 225, 255, 90),
            )
        # Redraw the characters on top of the highlight.
        for row, start, end in rects:
            line = self._screen.buffer.get(row, {})
            for x in range(start, min(end, self._screen.columns)):
                char = line.get(x)
                if char is None:
                    continue
                data = char.data or " "
                fg = _color(char.fg, _DEFAULT_FG)
                if char.reverse:
                    fg = _color(char.bg, _DEFAULT_FG)
                painter.setPen(fg)
                painter.drawText(
                    QRect(
                        x * self._cell_w,
                        row * self._cell_h,
                        self._cell_w,
                        self._cell_h,
                    ),
                    int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                    data,
                )

    # ------------------------------------------------------------------ scrolling

    def scroll_to_bottom(self) -> None:
        self._scroll_offset = 0
        self.update()

    # ------------------------------------------------------------------ input

    def focusInEvent(self, event) -> None:  # noqa: N802 — Qt API
        super().focusInEvent(event)
        self.setCursor(Qt.CursorShape.IBeamCursor)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 — Qt API
        data = self._key_to_bytes(event)
        if data:
            self._write(data)
            event.accept()
            return
        super().keyPressEvent(event)

    def _write(self, text: str) -> None:
        with self._proc_lock:
            proc = self._proc
        if proc is None:
            return
        try:
            proc.write(text)
        except Exception:  # noqa: BLE001
            pass
        self.scroll_to_bottom()

    # -- key translation ---------------------------------------------------

    _SPECIAL = {
        Qt.Key.Key_Return: "\r",
        Qt.Key.Key_Enter: "\r",
        Qt.Key.Key_Backspace: "\x7f",
        Qt.Key.Key_Tab: "\t",
        Qt.Key.Key_Backtab: "\x1b[Z",
        Qt.Key.Key_Escape: "\x1b",
        Qt.Key.Key_Up: "\x1b[A",
        Qt.Key.Key_Down: "\x1b[B",
        Qt.Key.Key_Right: "\x1b[C",
        Qt.Key.Key_Left: "\x1b[D",
        Qt.Key.Key_Home: "\x1b[H",
        Qt.Key.Key_End: "\x1b[F",
        Qt.Key.Key_PageUp: "\x1b[5~",
        Qt.Key.Key_PageDown: "\x1b[6~",
        Qt.Key.Key_Insert: "\x1b[2~",
        Qt.Key.Key_Delete: "\x1b[3~",
    }

    _F_KEYS = {
        Qt.Key.Key_F1: "\x1bOP",
        Qt.Key.Key_F2: "\x1bOQ",
        Qt.Key.Key_F3: "\x1bOR",
        Qt.Key.Key_F4: "\x1bOS",
        Qt.Key.Key_F5: "\x1b[15~",
        Qt.Key.Key_F6: "\x1b[17~",
        Qt.Key.Key_F7: "\x1b[18~",
        Qt.Key.Key_F8: "\x1b[19~",
        Qt.Key.Key_F9: "\x1b[20~",
        Qt.Key.Key_F10: "\x1b[21~",
        Qt.Key.Key_F11: "\x1b[23~",
        Qt.Key.Key_F12: "\x1b[24~",
    }

    def _key_to_bytes(self, event: QKeyEvent) -> str:
        key = event.key()
        modifiers = event.modifiers()

        # Copy / paste shortcuts.
        if modifiers & Qt.KeyboardModifier.ControlModifier and modifiers & (
            Qt.KeyboardModifier.ShiftModifier
        ):
            if key == Qt.Key.Key_C:
                self._copy_selection()
                return ""
            if key == Qt.Key.Key_V:
                self._paste()
                return ""

        if modifiers & Qt.KeyboardModifier.ControlModifier:
            if key in self._SPECIAL:
                return self._SPECIAL[key]
            if key in self._F_KEYS:
                return self._F_KEYS[key]
            if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
                return chr(key - Qt.Key.Key_A + 1)
            if key == Qt.Key.Key_Space:
                return "\x00"
            if key == Qt.Key.Key_At:
                return "\x00"

        if key in self._SPECIAL:
            return self._SPECIAL[key]
        if key in self._F_KEYS:
            return self._F_KEYS[key]

        text = event.text()
        if text and text.isprintable():
            return text
        return ""

    # -- clipboard ---------------------------------------------------------

    def _copy_selection(self) -> None:
        text = self._get_selected_text()
        if text:
            QGuiApplication.clipboard().setText(text)

    def _paste(self) -> None:
        text = QGuiApplication.clipboard().text()
        if text:
            self._write(text)

    # -- mouse -------------------------------------------------------------

    def _mouse_tracking_enabled(self) -> bool:
        """True when the child app asked for mouse reporting (DECSET 1000/2/3).

        pyte stores *private* modes shifted left by five bits, so DECSET 1002
        lands in ``screen.mode`` as ``1002 << 5``.
        """
        mode = getattr(self._screen, "mode", None) or set()
        try:
            wanted = {1000 << 5, 1002 << 5, 1003 << 5}
            return bool(wanted & set(mode))
        except TypeError:
            return False

    def _cell_at(self, event) -> tuple[int, int]:
        pos = event.position()
        col = int(pos.x() // self._cell_w)
        row = int(pos.y() // self._cell_h)
        return row, col

    def _sgr_mouse(self, button: int, col: int, row: int, press: bool) -> str:
        """Build an SGR (1006) mouse report — 1-based cell coordinates."""
        code = button
        if not press:
            code = button
        return f"\x1b[<{code};{col + 1};{row + 1}{'M' if press else 'm'}"

    def _selection_override(self, event) -> bool:
        """True when the user wants to select text instead of driving the app.

        While a TUI has mouse tracking enabled the terminal hands every click
        to the application, which makes text selection impossible.  Real
        terminals solve this by letting the user hold Shift, and so does this
        one.
        """
        return bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

    def mousePressEvent(self, event) -> None:  # noqa: N802 — Qt API
        self.setFocus()
        row, col = self._cell_at(event)

        if self._mouse_tracking_enabled() and not self._selection_override(event):
            self._write(self._sgr_mouse(0, col, row, True))
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._sel_anchor = (row, col)
            self._sel_cursor = (row, col)
            self._selected_text = ""
            self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 — Qt API
        row, col = self._cell_at(event)

        if self._mouse_tracking_enabled() and not self._selection_override(event):
            buttons = event.buttons()
            if buttons & Qt.MouseButton.LeftButton:
                self._write(self._sgr_mouse(32, col, row, True))
            return

        if self._sel_anchor is not None and (
            event.buttons() & Qt.MouseButton.LeftButton
        ):
            self._sel_cursor = (row, col)
            self._selected_text = self._get_selected_text()
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 — Qt API
        row, col = self._cell_at(event)
        if self._mouse_tracking_enabled() and not self._selection_override(event):
            self._write(self._sgr_mouse(0, col, row, False))
            return
        if self._sel_anchor is not None:
            self._selected_text = self._get_selected_text()
            self.update()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 — Qt API
        row, col = self._cell_at(event)
        # Select the word under the cursor.
        screen = self._screen
        line = screen.buffer.get(row, {})
        start = col
        end = col
        while start > 0:
            char = line.get(start - 1)
            if char is None or char.data in (" ", ""):
                break
            start -= 1
        while end < screen.columns - 1:
            char = line.get(end + 1)
            if char is None or char.data in (" ", ""):
                break
            end += 1
        self._sel_anchor = (row, start)
        self._sel_cursor = (row, end)
        self._selected_text = self._get_selected_text()
        self.update()

    def wheelEvent(self, event) -> None:  # noqa: N802 — Qt API
        if self._mouse_tracking_enabled():
            row, col = self._cell_at(event)
            button = 64 if event.angleDelta().y() > 0 else 65
            self._write(self._sgr_mouse(button, col, row, True))
            return
        delta = event.angleDelta().y()
        if delta > 0:
            self._scroll_offset = min(self._max_scrollback, self._scroll_offset + 3)
        else:
            self._scroll_offset = max(0, self._scroll_offset - 3)
        self.update()

    def contextMenuEvent(self, event) -> None:  # noqa: N802 — Qt API
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        copy_action = menu.addAction("Copy")
        paste_action = menu.addAction("Paste")
        clear_action = menu.addAction("Clear")
        chosen = menu.exec(event.globalPos())
        if chosen is copy_action:
            self._copy_selection()
        elif chosen is paste_action:
            self._paste()
        elif chosen is clear_action:
            self._screen.reset()
            self.update()

    # ------------------------------------------------------------------ helpers

    def current_text(self) -> str:
        """The visible screen as plain text (used for logging)."""
        screen = self._screen
        lines = []
        for row in range(screen.lines):
            line = screen.buffer.get(row, {})
            text = "".join((line.get(x).data if line.get(x) else " ") for x in range(screen.columns))
            lines.append(text.rstrip())
        return "\n".join(lines)
