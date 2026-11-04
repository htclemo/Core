"""The OpenCode console — the *real* ``opencode`` CLI running in a terminal.

OpenCode's interactive TUI only works when it is attached to a genuine
terminal: it queries the terminal's capabilities and draws nothing sensible
without the answers.  Piping it into a GUI produces no output at all, so the
console panel hosts it the only way that works:

* a ConPTY pseudo console gives the child process a real TTY, and
* :class:`~thecore.ai.ui.terminal_widget.TerminalWidget` (pyte) emulates the
  terminal and paints the result.

The panel can also host a plain **PowerShell** session, so the user gets the
same environment they would have by opening an administrator PowerShell.

Elevation matters here: OpenCode's tools run shell commands, and those must
be able to do administrator work.  TheCore therefore reports whether it runs
elevated and can relaunch itself with administrator rights.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from thecore.admin import is_admin, relaunch_as_admin
from thecore.ai.opencode_integration import resolve_opencode_command
from thecore.ai.ui.terminal_widget import TerminalWidget

# Console modes offered in the header.
MODE_OPENCODE = "OPENCODE"
MODE_POWERSHELL = "POWERSHELL"


class OpenCodeConsole(QFrame):
    """Console panel hosting the genuine OpenCode CLI in a real terminal."""

    # The console is up and interactive.
    ready = Signal()
    # The console could not be shown (reason text).
    failed = Signal(str)
    # Short status text for the panel header.
    status_received = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("opencodeConsole")

        self._mode = MODE_OPENCODE
        self._admin = is_admin()
        self._started = False
        self._cwd = os.getcwd()

        # Closing the window does not deliver a close event to child
        # widgets, so make sure the console (and the opencode process) is
        # stopped when the application quits.
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.stop)

        self._build_ui()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- header ------------------------------------------------------
        header = QFrame()
        header.setObjectName("opencodeConsoleHeader")
        head = QHBoxLayout(header)
        head.setContentsMargins(10, 6, 8, 6)
        head.setSpacing(8)

        label = QLabel("CONSOLE")
        label.setObjectName("opencodeConsoleLabel")
        head.addWidget(label)

        self._mode_btn = QPushButton(MODE_OPENCODE)
        self._mode_btn.setObjectName("opencodeConsoleHeaderBtn")
        self._mode_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mode_btn.setToolTip(
            "Switch between the OpenCode CLI and a plain PowerShell session"
        )
        self._mode_btn.clicked.connect(self._toggle_mode)
        head.addWidget(self._mode_btn)

        self._admin_label = QLabel("ADMIN" if self._admin else "NOT ADMIN")
        self._admin_label.setObjectName("opencodeAdminBadge")
        self._admin_label.setProperty("admin", "true" if self._admin else "false")
        self._admin_label.setToolTip(
            "The console inherits TheCore's privileges.\n"
            "Administrator rights are required for privileged shell commands."
        )
        head.addWidget(self._admin_label)

        head.addStretch(1)

        self._admin_btn = QPushButton("RUN AS ADMIN")
        self._admin_btn.setObjectName("opencodeConsoleHeaderBtn")
        self._admin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._admin_btn.setToolTip("Restart TheCore with administrator rights")
        self._admin_btn.clicked.connect(self._on_run_as_admin)
        self._admin_btn.setVisible(not self._admin)
        head.addWidget(self._admin_btn)

        self._stop_btn = QPushButton("STOP")
        self._stop_btn.setObjectName("opencodeConsoleHeaderBtn")
        self._stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_btn.setToolTip("Terminate the console session")
        self._stop_btn.clicked.connect(self.stop)
        self._stop_btn.setEnabled(False)
        head.addWidget(self._stop_btn)

        self._start_btn = QPushButton("START")
        self._start_btn.setObjectName("opencodeConsoleHeaderBtn")
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.setToolTip("Start the console session")
        self._start_btn.clicked.connect(self._start_current)
        head.addWidget(self._start_btn)

        root.addWidget(header)

        # ---- body --------------------------------------------------------
        self._stack = QStackedWidget()
        self._stack.setObjectName("opencodeStack")

        placeholder = QFrame()
        placeholder.setObjectName("opencodePlaceholder")
        ph = QVBoxLayout(placeholder)
        ph.setContentsMargins(24, 24, 24, 24)
        ph.addStretch(1)

        self._hint = QLabel("The console is not running.")
        self._hint.setObjectName("opencodeHint")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setWordWrap(True)
        ph.addWidget(self._hint)
        ph.addStretch(1)

        self._stack.addWidget(placeholder)

        self._terminal = TerminalWidget()
        self._terminal.started.connect(self._on_terminal_started)
        self._terminal.finished.connect(self._on_terminal_finished)
        self._terminal.failed.connect(self._on_failed)
        self._stack.addWidget(self._terminal)

        root.addWidget(self._stack, stretch=1)

    # ------------------------------------------------------------------ lifecycle

    def start(self, cwd: str) -> bool:
        """Start the console session in ``cwd``."""
        return self._start_current(cwd)

    def _start_current(self, cwd: Optional[str] = None) -> bool:
        if self._terminal.is_running():
            return True

        if cwd is None:
            cwd = self._cwd
        else:
            self._cwd = cwd

        if self._mode == MODE_POWERSHELL:
            argv = self._powershell_argv()
            title = "PowerShell"
        else:
            argv = resolve_opencode_command()
            title = "OpenCode"
            if argv is None:
                self._on_failed(
                    "The OpenCode CLI was not found.\n\n"
                    "Install it with:  npm install -g @opencode/cli"
                )
                return False

        self._stack.setCurrentIndex(1)
        self._set_hint("")
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self.status_received.emit(f"OPENCODE: STARTING {title.upper()}…")

        ok = self._terminal.start(argv, cwd=cwd)
        if not ok:
            self._stack.setCurrentIndex(0)
            self._start_btn.setEnabled(True)
            self._stop_btn.setEnabled(False)
            return False

        self._started = True
        return True

    def _powershell_argv(self) -> list[str]:
        """A shell that behaves like the one the user would open."""
        if sys.platform != "win32":
            shell = os.environ.get("SHELL") or "/bin/bash"
            return [shell, "-i"]
        # -NoLogo keeps the banner out; the prompt is drawn by PowerShell itself.
        return [
            "powershell.exe",
            "-NoLogo",
            "-NoExit",
            "-Command",
            "$Host.UI.RawUI.WindowTitle='Core Console'; "
            "if (-not ([Security.Principal.WindowsPrincipal]"
            "[Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole("
            "[Security.Principal.WindowsBuiltInRole]::Administrator)) "
            "{ Write-Host 'NOT running as Administrator' -ForegroundColor Yellow } "
            "else { Write-Host 'Running as Administrator' -ForegroundColor Green }",
        ]

    def stop(self) -> None:
        """Terminate the console session."""
        self._terminal.stop()
        self._started = False
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._stack.setCurrentIndex(0)
        self._set_hint("The console is not running.")
        self.status_received.emit("OPENCODE: CONSOLE NOT LOADED")

    def reload(self) -> None:
        """Restart the session (fresh terminal state)."""
        was_running = self._terminal.is_running()
        if was_running:
            self._terminal.stop()
        self._start_current()

    @property
    def url(self) -> Optional[str]:
        """Kept for API compatibility — the console is a local terminal now."""
        return None

    @property
    def is_running(self) -> bool:
        return self._terminal.is_running()

    # ------------------------------------------------------------------ internals

    def _set_hint(self, text: str) -> None:
        if self._hint is not None:
            self._hint.setText(text)

    def _toggle_mode(self) -> None:
        """Switch between OpenCode and PowerShell."""
        was_running = self._terminal.is_running()
        if was_running:
            self._terminal.stop()

        self._mode = (
            MODE_POWERSHELL if self._mode == MODE_OPENCODE else MODE_OPENCODE
        )
        self._mode_btn.setText(self._mode)
        label = "CONSOLE"
        self.findChild(QLabel, "opencodeConsoleLabel").setText(label)

        if was_running:
            self._start_current()

    def _on_run_as_admin(self) -> None:
        """Relaunch TheCore elevated so the console gets admin rights."""
        self._set_hint("Requesting administrator rights…")
        pid = relaunch_as_admin()
        if pid is None:
            self._set_hint(
                "Could not restart with administrator rights.\n\n"
                "The UAC prompt may have been declined. You can also right-click\n"
                "the TheCore shortcut and choose \"Run as administrator\"."
            )
            return
        # The elevated instance is up — close this one.
        from PySide6.QtWidgets import QApplication

        QApplication.instance().quit()

    def _on_failed(self, reason: str) -> None:
        self._stack.setCurrentIndex(0)
        self._set_hint(reason)
        self.failed.emit(reason)

    def _on_terminal_started(self) -> None:
        """The child process is up and the terminal is live."""
        self._stack.setCurrentIndex(1)
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        title = "OPENCODE" if self._mode == MODE_OPENCODE else "POWERSHELL"
        self.status_received.emit(f"OPENCODE: {title} RUNNING")
        self.ready.emit()

    def _on_terminal_finished(self, exit_code: int) -> None:
        """The child process exited."""
        self._started = False
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self.status_received.emit(f"OPENCODE: SESSION ENDED (CODE {exit_code})")

    def closeEvent(self, event) -> None:  # noqa: N802 — Qt API
        self._terminal.stop()
        super().closeEvent(event)
