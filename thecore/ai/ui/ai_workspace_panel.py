"""Main AI workspace area: left sidebar and the chat.

The sidebar's gear icon (bottom-left) opens the settings page, which slides
in over the chat.  Everything the program can be configured with lives
there.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QWidget,
)

from thecore.ai.database import Database
from thecore.ai.ui.chat_panel import ChatPanel
from thecore.ai.ui.settings_page import SettingsPage
from thecore.ai.ui.sidebar import Sidebar


class AIWorkspacePanel(QFrame):
    """AI panel: sidebar (workspaces and projects) and the main chat."""

    # The settings page was opened or closed.
    settings_visibility_changed = Signal(bool)

    def __init__(
        self,
        database: Database,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("aiWorkspacePanel")

        self._database = database
        self._current_conversation_id: Optional[int] = None

        self._build_ui()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Left sidebar
        self._sidebar = Sidebar(self._database)
        self._sidebar.new_chat_requested.connect(self._on_new_chat)
        self._sidebar.new_project_requested.connect(self._on_new_project)
        self._sidebar.new_workspace_requested.connect(self._on_new_workspace)
        self._sidebar.conversation_selected.connect(self._open_conversation)
        self._sidebar.conversation_deleted.connect(self._on_conversation_deleted)
        self._sidebar.project_deleted.connect(self._on_project_deleted)
        self._sidebar.project_selected.connect(self._on_project_selected)
        self._sidebar.settings_requested.connect(self.show_settings)

        # Right chat
        self._chat = ChatPanel(self._database)
        self._chat.new_project_created.connect(self._sidebar.refresh)
        self._chat.new_workspace_created.connect(self._sidebar.refresh)
        # A new conversation names itself after the first question.
        self._chat.conversation_renamed.connect(self._on_conversation_renamed)
        self._chat.conversation_created.connect(self._on_conversation_created)

        # The settings page — reached through the gear in the sidebar.
        self._settings = SettingsPage()
        self._settings.closed.connect(self.hide_settings)
        self._settings.cloud_changed.connect(self._chat.on_settings_cloud_changed)

        # The sidebar picked its default selection while it was being built,
        # before these signals existed — sync the chat panel to it now.
        current = self._sidebar.current_project_id()
        if current is not None:
            self._on_project_selected(current)

        # The button that brings the sidebar back after it was collapsed.
        self._expand_btn = QPushButton("›")
        self._expand_btn.setObjectName("aiSidebarExpandBtn")
        self._expand_btn.setToolTip("Show the sidebar")
        self._expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._expand_btn.clicked.connect(self._expand_sidebar)
        self._expand_btn.hide()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._sidebar)

        # The chat and the settings page share the right-hand side.
        self._stack = QStackedWidget()
        self._stack.setObjectName("aiStack")
        self._stack.addWidget(self._chat)
        self._stack.addWidget(self._settings)
        splitter.addWidget(self._stack)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 900])
        splitter.setChildrenCollapsible(False)

        root.addWidget(self._expand_btn)
        root.addWidget(splitter)

        self._sidebar.collapse_requested.connect(self._collapse_sidebar)

    # ------------------------------------------------------------------ settings

    def show_settings(self) -> None:
        """Open the settings page (the gear in the sidebar)."""
        self._stack.setCurrentWidget(self._settings)
        self.settings_visibility_changed.emit(True)

    def hide_settings(self) -> None:
        """Go back to the chat."""
        self._stack.setCurrentWidget(self._chat)
        self.settings_visibility_changed.emit(False)

    @property
    def settings_open(self) -> bool:
        return self._stack.currentWidget() is self._settings

    # ------------------------------------------------------------------ sidebar

    def _collapse_sidebar(self) -> None:
        """Hide the sidebar and show the button that brings it back."""
        self._sidebar.hide()
        self._expand_btn.show()

    def _expand_sidebar(self) -> None:
        """Show the sidebar again."""
        self._sidebar.show()
        self._expand_btn.hide()

    # ------------------------------------------------------------------ actions

    def _on_new_chat(self) -> None:
        pr_id = self._sidebar.current_project_id()
        if pr_id is None:
            # Prompt for a project first? For now create a default project.
            from thecore.ai.database import Database

            ws_id = self._sidebar.current_workspace_id()
            if ws_id is None:
                ws = self._database.create_workspace("Default", str(self._default_workspace_path()))
                ws_id = ws.id
            pr = self._database.create_project(ws_id, "General")
            pr_id = pr.id
        self._chat.start_new_conversation(pr_id)

    def _on_new_project(self) -> None:
        ws_id = self._sidebar.current_workspace_id()
        if ws_id is None:
            ws = self._database.create_workspace("Default", str(self._default_workspace_path()))
            ws_id = ws.id
        # ChatPanel will handle the project creation dialog
        self._chat.request_new_project(ws_id)

    def _on_new_workspace(self) -> None:
        self._chat.request_new_workspace()

    def _open_conversation(self, conversation_id: int) -> None:
        self._current_conversation_id = conversation_id
        self._chat.load_conversation(conversation_id)

    def _on_conversation_renamed(self, conversation_id: int, title: str) -> None:
        """The chat named a conversation after its first question."""
        if not self._sidebar.rename_conversation(conversation_id, title):
            # The conversation was not in the list yet — reload it.
            self._sidebar.refresh()

    def _on_conversation_created(self, conversation_id: int) -> None:
        """The chat created a conversation on its own (e.g. on the first send)."""
        self._sidebar.refresh()

    # ------------------------------------------------------------------ menu actions

    def new_chat(self) -> None:
        """Start a new conversation in the current project."""
        self._sidebar.create_conversation()

    def new_workspace(self) -> None:
        """Ask for a new workspace."""
        self._chat.request_new_workspace()

    def new_project(self) -> None:
        """Ask for a new project in the current workspace."""
        workspace_id = self._sidebar.current_workspace_id()
        if workspace_id is None:
            return
        self._chat.request_new_project(workspace_id)

    def toggle_sidebar(self) -> None:
        """Show or hide the sidebar."""
        if self._sidebar.isVisible():
            self._collapse_sidebar()
        else:
            self._expand_sidebar()

    def reload(self) -> None:
        """Reload the sidebar and the model list."""
        self._sidebar.refresh()
        self._chat.reload_models()

    def zoom(self, direction: int) -> None:
        """Change the text size: 1 = bigger, -1 = smaller, 0 = reset."""
        self._chat.zoom(direction)

    def _on_conversation_deleted(self, conversation_id: int) -> None:
        if self._current_conversation_id == conversation_id:
            self._current_conversation_id = None
            self._chat._clear_messages()

    def _on_project_deleted(self, project_id: int) -> None:
        """Clear the chat if the deleted project was the one on screen."""
        if self._chat._current_project_id == project_id:
            self._current_conversation_id = None
            self._chat._current_project_id = None
            self._chat._current_conversation_id = None
            self._chat._clear_messages()

    def _on_project_selected(self, project_id: int) -> None:
        """Keep the chat panel in sync with the highlighted project."""
        self._current_conversation_id = None
        self._chat._current_project_id = project_id
        ws = self._database.get_workspace_for_project(project_id)
        self._chat._current_workspace_id = ws.id if ws is not None else None
        # Show the scope in the composer.
        project = self._database.get_project(project_id)
        self._chat.set_scope(
            ws.name if ws is not None else "",
            project.name if project is not None else "",
        )

    @staticmethod
    def _default_workspace_path() -> str:
        from pathlib import Path
        return str(Path(__file__).resolve().parents[3])

    def closeEvent(self, event) -> None:  # noqa: N802 — Qt API
        """Forward the close to the chat panel so the console is stopped."""
        self._chat.closeEvent(event)
        super().closeEvent(event)
