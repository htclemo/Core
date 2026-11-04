"""TheCore — the AI coding workbench.

The app is a single screen: a menu bar (File / Edit / View / Help) above the
AI workspace (workspaces → projects → conversations on the left, the chat and
the OpenCode console on the right).

The old PC-monitor tab and its one-second telemetry sweep are gone — that
sweep alone cost 830 ms of CPU every second.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QWidget,
)

from thecore.ai.database import Database
from thecore.ai.ui.ai_workspace_panel import AIWorkspacePanel
from thecore.ui.updates_panel import UpdateProgress, UpdatesPanel
from thecore.updates import ApplyUpdates, UpdateCheck, UpdateItem


class MainWindow(QMainWindow):
    """The single AI workspace window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Core")
        # The header needs the room, otherwise the buttons are squeezed and
        # their labels get clipped.  The window is *maximised* when it is
        # finally shown (see app.py) — calling showMaximized() here would
        # make the window appear right away, behind the splash screen.
        self.resize(1400, 860)
        self.setMinimumSize(1240, 740)

        icon_path = Path(__file__).resolve().parents[2] / "assets" / "thecore.ico"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

        # ---- AI database (stores workspaces, projects, conversations) ----
        db_dir = Path.home() / ".local" / "share" / "thecore"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / "thecore_ai.db"
        self._ai_db = Database(db_path)

        self._build_ui()
        self._build_menu()
        self._updates: list[UpdateItem] = []
        self._update_check: UpdateCheck | None = None
        self._apply: ApplyUpdates | None = None
        self._update_btn = QPushButton("UPDATES")
        self._update_btn.setObjectName("updateButton")
        self._update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_btn.setToolTip("Python, Ollama en de pakketten die Core nodig heeft")
        self._update_btn.clicked.connect(self._show_updates)
        self._updates_panel = UpdatesPanel(self)
        self._updates_panel.update_one.connect(lambda item: self._apply_updates([item]))
        self._updates_panel.update_all.connect(self._apply_updates)
        self._progress = UpdateProgress(self)
        self.menuBar().setCornerWidget(self._update_btn, Qt.Corner.TopRightCorner)
        QTimer.singleShot(400, self._check_updates)

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        # ---- the AI workspace ----
        self._ai_panel = AIWorkspacePanel(self._ai_db)
        self.setCentralWidget(self._ai_panel)

    # ------------------------------------------------------------------ menu

    def _build_menu(self) -> None:
        """The menu bar: File / Edit / View / Help."""
        bar = self.menuBar()
        bar.setObjectName("mainMenuBar")

        # ---- File ----
        file_menu = bar.addMenu("&File")
        self._add_action(
            file_menu, "&New Chat", self._on_new_chat, QKeySequence("Ctrl+N")
        )
        self._add_action(
            file_menu,
            "&New Workspace…",
            self._on_new_workspace,
            QKeySequence("Ctrl+Shift+N"),
        )
        self._add_action(
            file_menu, "&New Project…", self._on_new_project, QKeySequence("Ctrl+Shift+P")
        )
        file_menu.addSeparator()
        self._add_action(file_menu, "&Quit", self.close, QKeySequence("Ctrl+Q"))

        # ---- Edit ----
        edit_menu = bar.addMenu("&Edit")
        self._add_action(
            edit_menu, "&Undo", self._ai_panel._chat.undo, QKeySequence("Ctrl+Z")
        )
        self._add_action(
            edit_menu, "&Redo", self._ai_panel._chat.redo, QKeySequence("Ctrl+Shift+Z")
        )
        edit_menu.addSeparator()
        self._add_action(
            edit_menu, "Cu&t", self._ai_panel._chat.cut, QKeySequence("Ctrl+X")
        )
        self._add_action(
            edit_menu, "&Copy", self._ai_panel._chat.copy, QKeySequence("Ctrl+C")
        )
        self._add_action(
            edit_menu, "&Paste", self._ai_panel._chat.paste, QKeySequence("Ctrl+V")
        )
        edit_menu.addSeparator()
        self._add_action(
            edit_menu,
            "Select &All",
            self._ai_panel._chat.select_all,
            QKeySequence("Ctrl+A"),
        )

        # ---- View ----
        view_menu = bar.addMenu("&View")
        self._toggle_sidebar = QAction("Toggle &Sidebar", self)
        self._toggle_sidebar.setShortcut(QKeySequence("Ctrl+B"))
        self._toggle_sidebar.triggered.connect(self._ai_panel.toggle_sidebar)
        view_menu.addAction(self._toggle_sidebar)

        self._add_action(
            view_menu, "&Reload", self._reload_ui, QKeySequence("Ctrl+R")
        )
        view_menu.addSeparator()
        self._settings_action = QAction("&Settings", self)
        self._settings_action.setShortcut(QKeySequence("Ctrl+,"))
        self._settings_action.triggered.connect(self._toggle_settings)
        view_menu.addAction(self._settings_action)
        view_menu.addSeparator()
        self._add_action(
            view_menu, "Zoom &In", self._zoom_in, QKeySequence("Ctrl+=")
        )
        self._add_action(
            view_menu, "Zoom &Out", self._zoom_out, QKeySequence("Ctrl+-")
        )
        self._add_action(
            view_menu, "Reset &Zoom", self._zoom_reset, QKeySequence("Ctrl+0")
        )

        # ---- Help ----
        help_menu = bar.addMenu("&Help")
        self._add_action(help_menu, "&About Core", self._on_about)

    @staticmethod
    def _add_action(menu: QMenu, text: str, slot, shortcut=None) -> QAction:
        action = QAction(text, menu)
        action.triggered.connect(slot)
        if shortcut is not None:
            action.setShortcut(shortcut)
        menu.addAction(action)
        return action

    # ------------------------------------------------------------------ actions

    def _on_new_chat(self) -> None:
        self._ai_panel.new_chat()

    def _on_new_workspace(self) -> None:
        self._ai_panel.new_workspace()

    def _on_new_project(self) -> None:
        self._ai_panel.new_project()

    def _reload_ui(self) -> None:
        self._ai_panel.reload()

    def _zoom_in(self) -> None:
        self._ai_panel.zoom(1)

    def _zoom_out(self) -> None:
        self._ai_panel.zoom(-1)

    def _zoom_reset(self) -> None:
        self._ai_panel.zoom(0)

    def _check_updates(self) -> None:
        """Look for updates. Nothing is installed until the menu asks for it."""
        if self._update_check is not None and self._update_check.isRunning():
            return
        if self._apply is not None and self._apply.isRunning():
            return
        self._update_btn.setText("CHECKING")
        self._set_update_available(False)
        self._update_check = UpdateCheck(self)
        self._update_check.finished_with.connect(self._on_updates)
        self._update_check.start()

    def _set_update_available(self, available: bool) -> None:
        self._update_btn.setProperty("available", "true" if available else "false")
        self._update_btn.style().unpolish(self._update_btn)
        self._update_btn.style().polish(self._update_btn)

    def _on_updates(self, result) -> None:
        if isinstance(result, Exception):
            self._updates = []
            self._update_btn.setText("UPDATES")
            self._update_btn.setToolTip(str(result))
            return
        self._updates = list(result)
        pending = [item for item in self._updates if item.available]
        self._update_btn.setText(f"UPDATES {len(pending)}" if pending else "UP TO DATE")
        self._set_update_available(bool(pending))
        names = ", ".join(item.name for item in pending) or "Niets nieuwer"
        self._update_btn.setToolTip(names)
        if self._updates_panel.isVisible():
            self._updates_panel.show_items(self._updates)

    def _show_updates(self) -> None:
        if not self._updates:
            self._check_updates()
        self._updates_panel.show_items(self._updates)
        origin = self._update_btn.mapToGlobal(self._update_btn.rect().bottomRight())
        self._updates_panel.move(origin.x() - self._updates_panel.width(), origin.y() + 6)
        self._updates_panel.show()

    def _apply_updates(self, items: list[UpdateItem]) -> None:
        if not items or (self._apply is not None and self._apply.isRunning()):
            return
        self._update_btn.setText("UPDATING")
        self._progress.set_progress(0, f"Updating {items[0].name}")
        self._progress.show()
        self._apply = ApplyUpdates(items, self)
        self._apply.progress.connect(self._progress.set_progress)
        self._apply.finished_with.connect(self._on_applied)
        self._apply.start()

    def _on_applied(self, result) -> None:
        self._progress.set_progress(100, "Done")
        self._progress.hide()
        if isinstance(result, Exception):
            QMessageBox.warning(self, "Updates", str(result))
        else:
            QMessageBox.information(self, "Updates", "\n".join(result) or "Done")
        self._updates = []
        self._check_updates()

    def _on_about(self) -> None:
        QMessageBox.about(
            self,
            "About Core",
            "<h3>CORE</h3>"
            "<p>Code Orchestration &amp; Real-time Engineering</p>"
            "<p>Your code. Your AI. Your control.</p>"
            "<p>An AI-powered development environment for "
            + ("Linux." if sys.platform.startswith("linux") else "Windows.")
            + "</p>"
            "<p>Chat with a local model through Ollama, drive the real "
            "<b>opencode</b> console, or reach a cloud provider.</p>",
        )

    def _toggle_settings(self) -> None:
        """Open or close the settings page."""
        if self._ai_panel.settings_open:
            self._ai_panel.hide_settings()
        else:
            self._ai_panel.show_settings()
