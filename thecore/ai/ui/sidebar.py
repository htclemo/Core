"""Cursor-style left sidebar: a flat tree of projects, workspaces and chats.

Rows are real widgets (not ``QListWidget`` overlays). Overlay widgets get
painted over by the item delegate, which collapsed titles and hid the delete
button.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from thecore.ai.database import Database


def _ago(stamp: str) -> str:
    """Turn an ISO timestamp into a short age such as ``1m`` or ``3d``."""
    text = (stamp or "").strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    seconds = max(0, int((datetime.now(timezone.utc) - parsed).total_seconds()))
    if seconds < 60:
        return "now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    days = hours // 24
    if days < 7:
        return f"{days}d"
    return f"{days // 7}w"


class _RowBase(QFrame):
    """A clickable, hover-aware row used by every sidebar section."""

    clicked = Signal()
    delete_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("aiRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(30)
        self._selected = False

    # ---- selection ------------------------------------------------------

    def set_selected(self, selected: bool) -> None:
        if self._selected == selected:
            return
        self._selected = selected
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    @property
    def is_selected(self) -> bool:
        return self._selected

    # ---- interaction ----------------------------------------------------

    def mousePressEvent(self, event) -> None:  # noqa: N802 — Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def enterEvent(self, event) -> None:  # noqa: N802 — Qt API
        self.setProperty("hovered", "true")
        self.style().unpolish(self)
        self.style().polish(self)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 — Qt API
        self.setProperty("hovered", "false")
        self.style().unpolish(self)
        self.style().polish(self)
        super().leaveEvent(event)


class _DeleteButton(QPushButton):
    """Red trash-bin button shown on row hover."""

    def __init__(self, tooltip: str, parent: QWidget | None = None) -> None:
        super().__init__("\U0001f5d1\ufe0f", parent)  # 🗑️
        self.setObjectName("rowDeleteBtn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(22, 22)
        self.setToolTip(tooltip)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)


class _Row(_RowBase):
    """A flat tree row: optional mark, title, age, and a hover delete button."""

    def __init__(
        self,
        title: str,
        tooltip: str,
        *,
        indent: int = 0,
        mark: str = "",
        meta: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8 + indent, 0, 6, 0)
        layout.setSpacing(6)

        self._mark = QLabel(mark)
        self._mark.setObjectName("aiRowMark")
        self._mark.setFixedWidth(14)
        self._mark.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._mark.setVisible(bool(mark))

        self._label = QLabel(title)
        self._label.setObjectName("aiRowTitle")
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._meta = QLabel(meta)
        self._meta.setObjectName("aiRowMeta")
        self._meta.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._meta.setVisible(bool(meta))

        self._delete = _DeleteButton(tooltip)
        self._delete.clicked.connect(self.delete_requested.emit)

        layout.addWidget(self._mark)
        layout.addWidget(self._label, stretch=1)
        layout.addWidget(self._meta)
        layout.addWidget(self._delete)

    def set_title(self, title: str) -> None:
        self._label.setText(title)

    def matches(self, needle: str) -> bool:
        """True when the row's title contains the search text."""
        return needle in self._label.text().lower()


class _SectionHeader(QWidget):
    """A muted section title with a small action on the right."""

    action = Signal()

    def __init__(self, title: str, action_tip: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("aiSectionHeader")
        self.setFixedHeight(28)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 4, 0)
        layout.setSpacing(4)

        label = QLabel(title)
        label.setObjectName("aiSectionLabel")
        layout.addWidget(label)
        layout.addStretch(1)

        button = QPushButton("+")
        button.setObjectName("aiSectionAction")
        button.setToolTip(action_tip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedSize(22, 22)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(self.action.emit)
        layout.addWidget(button)


class Sidebar(QFrame):
    """Left navigation panel for workspaces / projects / conversations."""

    conversation_selected = Signal(int)
    conversation_deleted = Signal(int)
    project_selected = Signal(int)
    project_deleted = Signal(int)
    workspace_selected = Signal(int)
    new_chat_requested = Signal()
    new_project_requested = Signal()
    new_workspace_requested = Signal()
    # The user asked to hide the sidebar.
    collapse_requested = Signal()
    # The gear in the bottom-left corner was clicked.
    settings_requested = Signal()

    def __init__(self, database: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("aiSidebar")
        self.setFixedWidth(280)
        self._database = database
        self._current_workspace_id: Optional[int] = None
        self._current_project_id: Optional[int] = None

        self._workspace_rows: list[tuple[int, _Row]] = []
        self._project_rows: list[tuple[int, _Row]] = []
        self._conv_rows: list[tuple[int, _Row]] = []
        self._filter = ""
        self._reloading = False

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(2)
        top.setContentsMargins(2, 0, 2, 0)

        self._search_btn = QPushButton("⌕")
        self._search_btn.setObjectName("aiSidebarIconBtn")
        self._search_btn.setToolTip("Search")
        self._search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._search_btn.clicked.connect(self._toggle_search)
        top.addWidget(self._search_btn)

        top.addStretch(1)

        self._collapse_btn = QPushButton("⟨")
        self._collapse_btn.setObjectName("aiSidebarIconBtn")
        self._collapse_btn.setToolTip("Hide the sidebar")
        self._collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._collapse_btn.clicked.connect(self.collapse_requested.emit)
        top.addWidget(self._collapse_btn)
        root.addLayout(top)

        self._search = QLineEdit()
        self._search.setObjectName("aiSidebarSearch")
        self._search.setPlaceholderText("Search")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search_changed)
        self._search.hide()
        root.addWidget(self._search)

        new_chat = QPushButton("  New Chat")
        new_chat.setObjectName("aiNavItem")
        new_chat.setCursor(Qt.CursorShape.PointingHandCursor)
        new_chat.clicked.connect(self.new_chat_requested.emit)
        root.addWidget(new_chat)

        self._tree_host = QWidget()
        self._tree_host.setObjectName("aiSectionBody")
        self._tree = QVBoxLayout(self._tree_host)
        self._tree.setContentsMargins(0, 4, 0, 0)
        self._tree.setSpacing(0)
        self._tree.addStretch(1)

        scroll = QScrollArea()
        scroll.setObjectName("aiSectionScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self._tree_host)
        root.addWidget(scroll, stretch=1)

        self._projects_header = _SectionHeader("Projects", "New project")
        self._projects_header.action.connect(self.new_project_requested.emit)
        self._workspaces_header = _SectionHeader("Workspaces", "New workspace")
        self._workspaces_header.action.connect(self.new_workspace_requested.emit)

        self._settings_btn = QPushButton("⚙")
        self._settings_btn.setObjectName("aiSidebarSettingsBtn")
        self._settings_btn.setToolTip("Settings")
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.setFixedSize(28, 28)
        self._settings_btn.clicked.connect(self.settings_requested.emit)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(4, 4, 4, 2)
        bottom.addStretch(1)
        bottom.addWidget(self._settings_btn)
        root.addLayout(bottom)

    def _toggle_search(self) -> None:
        self._search.setVisible(not self._search.isVisible())
        if self._search.isVisible():
            self._search.setFocus()
        else:
            self._search.clear()

    def _clear_tree(self) -> None:
        headers = {self._projects_header, self._workspaces_header}
        while self._tree.count() > 1:
            item = self._tree.takeAt(0)
            widget = item.widget()
            if widget is None:
                continue
            widget.setParent(None)
            if widget not in headers:
                widget.deleteLater()

    def _add(self, widget: QWidget) -> None:
        self._tree.insertWidget(self._tree.count() - 1, widget)

    # ------------------------------------------------------------------ loading

    def refresh(self) -> None:
        """Reload the tree, preserving the current selection."""
        self._reload()

    def _reload(self) -> None:
        """Rebuild the single tree from the database."""
        if self._reloading:
            return
        self._reloading = True
        try:
            workspaces = self._database.list_workspaces()
            ws_ids = [int(w.id) for w in workspaces]
            if self._current_workspace_id not in ws_ids:
                self._current_workspace_id = ws_ids[0] if ws_ids else None
                self._current_project_id = None

            projects = []
            if self._current_workspace_id is not None:
                projects = self._database.list_projects(self._current_workspace_id)
            pr_ids = [int(p.id) for p in projects]
            if self._current_project_id not in pr_ids:
                self._current_project_id = pr_ids[0] if pr_ids else None

            conversations = []
            if self._current_project_id is not None:
                conversations = self._database.list_conversations(self._current_project_id)

            self._clear_tree()
            self._workspace_rows = []
            self._project_rows = []
            self._conv_rows = []

            self._add(self._projects_header)
            for pr in projects:
                count = self._database.count_conversations(int(pr.id))
                row = _Row(
                    pr.name,
                    f"Delete project '{pr.name}' and its {count} chat(s)",
                    indent=6,
                )
                row.set_selected(int(pr.id) == self._current_project_id)
                row.clicked.connect(lambda pid=pr.id: self._select_project(pid))
                row.delete_requested.connect(
                    lambda pid=pr.id, name=pr.name: self._delete_project(pid, name)
                )
                self._add(row)
                self._project_rows.append((int(pr.id), row))

            self._add(self._workspaces_header)
            for ws in workspaces:
                open_ws = int(ws.id) == self._current_workspace_id
                row = _Row(
                    ws.name,
                    f"Delete workspace '{ws.name}'",
                    mark="▾" if open_ws else "▸",
                )
                row.set_selected(open_ws)
                row.clicked.connect(lambda wid=ws.id: self._select_workspace(wid))
                row.delete_requested.connect(
                    lambda wid=ws.id, name=ws.name: self._delete_workspace(wid, name)
                )
                self._add(row)
                self._workspace_rows.append((int(ws.id), row))

                if not open_ws:
                    continue
                for conv in conversations:
                    chat = _Row(
                        conv.title,
                        f"Delete chat '{conv.title}'",
                        indent=22,
                        mark="•",
                        meta=_ago(conv.updated_at),
                    )
                    chat.clicked.connect(lambda cid=conv.id: self._select_conversation(cid))
                    chat.delete_requested.connect(
                        lambda cid=conv.id, title=conv.title: self._delete_conversation(
                            cid, title
                        )
                    )
                    self._add(chat)
                    self._conv_rows.append((int(conv.id), chat))

            self._on_search_changed(self._filter)
        finally:
            self._reloading = False

    def _on_search_changed(self, text: str) -> None:
        """Filter the rows by name. Headers stay; empty matches hide their rows."""
        needle = text.strip().lower()
        self._filter = needle
        for rows in (self._workspace_rows, self._project_rows, self._conv_rows):
            for _id, row in rows:
                row.setVisible(not needle or row.matches(needle))

    # ------------------------------------------------------------------ selection

    def _apply_selection(
        self, rows: list[tuple[int, _Row]], selected_id: Optional[int]
    ) -> None:
        for row_id, row in rows:
            row.set_selected(row_id == selected_id)

    def _select_workspace(self, workspace_id: int) -> None:
        workspace_id = int(workspace_id)
        if workspace_id != self._current_workspace_id:
            self._current_project_id = None
        self._current_workspace_id = workspace_id
        self._reload()
        self.workspace_selected.emit(self._current_workspace_id)
        if self._current_project_id is not None:
            self.project_selected.emit(self._current_project_id)

    def _select_project(self, project_id: int) -> None:
        self._current_project_id = int(project_id)
        self._reload()
        self.project_selected.emit(self._current_project_id)

    def _select_conversation(self, conversation_id: int) -> None:
        self._apply_selection(self._conv_rows, int(conversation_id))
        self.conversation_selected.emit(int(conversation_id))

    # ------------------------------------------------------------------ deletion

    def _confirm(self, title: str, message: str, confirm_label: str) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes
        )
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        yes = box.button(QMessageBox.StandardButton.Yes)
        if yes is not None:
            yes.setText(confirm_label)
        box.exec()
        return box.standardButton(box.clickedButton()) == QMessageBox.StandardButton.Yes

    def _delete_conversation(self, conversation_id: int, title: str) -> None:
        if not self._confirm(
            "Delete Conversation",
            f"Are you sure you want to delete the conversation “{title}”?\n\n"
            "All of its messages will be removed. This cannot be undone.",
            "Delete",
        ):
            return
        self._database.delete_conversation(conversation_id)
        self._reload()
        self.conversation_deleted.emit(int(conversation_id))

    def _delete_project(self, project_id: int, name: str) -> None:
        count = self._database.count_conversations(project_id)
        extra = (
            f"\n\nThis will also delete {count} conversation(s) and all of their messages."
            if count
            else ""
        )
        if not self._confirm(
            "Delete Project",
            f"Are you sure you want to delete the project “{name}”?{extra}\n\n"
            "This cannot be undone.",
            "Delete",
        ):
            return
        # Tell the panel *before* reloading: reloading auto-selects a surviving
        # project and would otherwise overwrite the chat's current project.
        self._database.delete_project(project_id)
        self.project_deleted.emit(int(project_id))
        self._current_project_id = None
        self._reload()

    def _delete_workspace(self, workspace_id: int, name: str) -> None:
        projects = self._database.list_projects(workspace_id)
        total_chats = sum(self._database.count_conversations(int(p.id)) for p in projects)
        extra = (
            f"\n\nThis will also delete {len(projects)} project(s) and "
            f"{total_chats} conversation(s)."
            if projects
            else ""
        )
        if not self._confirm(
            "Delete Workspace",
            f"Are you sure you want to delete the workspace “{name}”?{extra}\n\n"
            "This cannot be undone.",
            "Delete",
        ):
            return
        self._database.delete_workspace(workspace_id)
        self._current_workspace_id = None
        self._current_project_id = None
        self._reload()

    # ------------------------------------------------------------------ public API

    def current_project_id(self) -> Optional[int]:
        return self._current_project_id

    def current_workspace_id(self) -> Optional[int]:
        return self._current_workspace_id

    def select_conversation(self, conversation_id: int) -> None:
        self._select_conversation(conversation_id)

    def rename_conversation(self, conversation_id: int, title: str) -> bool:
        """Update a conversation's row in place after it was named automatically.

        Returns False when the conversation is not in the list yet (the caller
        should then reload the list).
        """
        for conv_id, row in self._conv_rows:
            if conv_id == int(conversation_id):
                row.set_title(title)
                return True
        return False
