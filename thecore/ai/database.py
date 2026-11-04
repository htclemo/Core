"""SQLite storage for workspaces, projects, conversations, and messages."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Workspace:
    id: Optional[int]
    name: str
    path: str
    created_at: str


@dataclass(frozen=True)
class Project:
    id: Optional[int]
    workspace_id: int
    name: str
    description: str
    created_at: str


@dataclass(frozen=True)
class Conversation:
    id: Optional[int]
    project_id: int
    title: str
    model: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Message:
    id: Optional[int]
    conversation_id: int
    role: str  # "user" or "assistant"
    content: str
    created_at: str


class Database:
    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        # Foreign keys must be enabled per-connection; without this the
        # ON DELETE CASCADE clauses below are silently ignored and deleting a
        # project would leave orphaned conversations and messages behind.
        cur.execute("PRAGMA foreign_keys=ON")
        cur.executescript(
            """
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS workspaces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                path TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                model TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_conversations_project ON conversations(project_id);
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ---- workspaces ----

    def create_workspace(self, name: str, path: str) -> Workspace:
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO workspaces (name, path, created_at) VALUES (?, ?, ?)",
            (name, path, now),
        )
        self._conn.commit()
        return Workspace(id=cur.lastrowid, name=name, path=path, created_at=now)

    def list_workspaces(self) -> list[Workspace]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, name, path, created_at FROM workspaces ORDER BY created_at DESC"
        )
        return [
            Workspace(
                id=row["id"],
                name=row["name"],
                path=row["path"],
                created_at=row["created_at"],
            )
            for row in cur.fetchall()
        ]

    def delete_workspace(self, workspace_id: int) -> None:
        cur = self._conn.cursor()
        cur.execute("DELETE FROM workspaces WHERE id = ?", (workspace_id,))
        self._conn.commit()

    def get_workspace(self, workspace_id: int) -> Optional[Workspace]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, name, path, created_at FROM workspaces WHERE id = ?",
            (workspace_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return Workspace(
            id=row["id"],
            name=row["name"],
            path=row["path"],
            created_at=row["created_at"],
        )

    def get_workspace_for_project(self, project_id: int) -> Optional[Workspace]:
        """Return the workspace that owns the given project."""
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT w.id, w.name, w.path, w.created_at
            FROM workspaces w
            JOIN projects p ON p.workspace_id = w.id
            WHERE p.id = ?
            """,
            (project_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return Workspace(
            id=row["id"],
            name=row["name"],
            path=row["path"],
            created_at=row["created_at"],
        )

    # ---- projects ----

    def create_project(
        self, workspace_id: int, name: str, description: str = ""
    ) -> Project:
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO projects (workspace_id, name, description, created_at) "
            "VALUES (?, ?, ?, ?)",
            (workspace_id, name, description, now),
        )
        self._conn.commit()
        return Project(
            id=cur.lastrowid,
            workspace_id=workspace_id,
            name=name,
            description=description,
            created_at=now,
        )

    def get_project(self, project_id: int) -> Optional[Project]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, workspace_id, name, description, created_at "
            "FROM projects WHERE id = ?",
            (project_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return Project(
            id=row["id"],
            workspace_id=row["workspace_id"],
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
        )

    def list_projects(self, workspace_id: int | None = None) -> list[Project]:
        cur = self._conn.cursor()
        if workspace_id is not None:
            cur.execute(
                "SELECT id, workspace_id, name, description, created_at "
                "FROM projects WHERE workspace_id = ? ORDER BY created_at DESC",
                (workspace_id,),
            )
        else:
            cur.execute(
                "SELECT id, workspace_id, name, description, created_at "
                "FROM projects ORDER BY created_at DESC"
            )
        return [
            Project(
                id=row["id"],
                workspace_id=row["workspace_id"],
                name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
            )
            for row in cur.fetchall()
        ]

    def delete_project(self, project_id: int) -> None:
        """Delete a project together with its conversations and messages."""
        cur = self._conn.cursor()
        cur.execute(
            "DELETE FROM messages WHERE conversation_id IN "
            "(SELECT id FROM conversations WHERE project_id = ?)",
            (project_id,),
        )
        cur.execute("DELETE FROM conversations WHERE project_id = ?", (project_id,))
        cur.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        self._conn.commit()

    # ---- conversations ----

    def create_conversation(
        self, project_id: int, title: str, model: str
    ) -> Conversation:
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO conversations (project_id, title, model, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (project_id, title, model, now, now),
        )
        self._conn.commit()
        return Conversation(
            id=cur.lastrowid,
            project_id=project_id,
            title=title,
            model=model,
            created_at=now,
            updated_at=now,
        )

    def list_conversations(self, project_id: int) -> list[Conversation]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, project_id, title, model, created_at, updated_at "
            "FROM conversations WHERE project_id = ? "
            "ORDER BY updated_at DESC",
            (project_id,),
        )
        return [
            Conversation(
                id=row["id"],
                project_id=row["project_id"],
                title=row["title"],
                model=row["model"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in cur.fetchall()
        ]

    def update_conversation_timestamp(
        self, conversation_id: int, title: str | None = None
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.cursor()
        if title is not None:
            cur.execute(
                "UPDATE conversations SET updated_at = ?, title = ? WHERE id = ?",
                (now, title, conversation_id),
            )
        else:
            cur.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
        self._conn.commit()

    def rename_conversation(self, conversation_id: int, title: str) -> None:
        """Give a conversation its automatic name.

        Only the title changes — ``updated_at`` is left alone so the sidebar
        does not reshuffle while the user is typing.
        """
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE conversations SET title = ? WHERE id = ?",
            (title, conversation_id),
        )
        self._conn.commit()

    def count_messages(self, conversation_id: int) -> int:
        """How many messages a conversation holds (0 = brand new)."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS n FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        )
        return int(cur.fetchone()["n"])

    def delete_conversation(self, conversation_id: int) -> None:
        """Delete a conversation together with all of its messages."""
        cur = self._conn.cursor()
        cur.execute(
            "DELETE FROM messages WHERE conversation_id = ?", (conversation_id,)
        )
        cur.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        self._conn.commit()

    def count_conversations(self, project_id: int) -> int:
        """Number of conversations inside a project (for delete confirmations)."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS n FROM conversations WHERE project_id = ?",
            (project_id,),
        )
        return int(cur.fetchone()["n"])

    # ---- messages ----

    def add_message(
        self, conversation_id: int, role: str, content: str
    ) -> Message:
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, now),
        )
        self._conn.commit()
        return Message(
            id=cur.lastrowid,
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=now,
        )

    def get_messages(self, conversation_id: int) -> list[Message]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, conversation_id, role, content, created_at "
            "FROM messages WHERE conversation_id = ? "
            "ORDER BY created_at ASC",
            (conversation_id,),
        )
        return [
            Message(
                id=row["id"],
                conversation_id=row["conversation_id"],
                role=row["role"],
                content=row["content"],
                created_at=row["created_at"],
            )
            for row in cur.fetchall()
        ]
