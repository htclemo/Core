/**
 * TheCore — SQLite persistence (Electron main process).
 *
 * Mirrors `thecore/ai/database.py` exactly, so the Electron app and the
 * Python app share the same `thecore_ai.db` file.  Both create the schema
 * with `IF NOT EXISTS`, so whichever app starts first sets it up.
 *
 * Note: `PRAGMA foreign_keys=ON` is per connection and must be set on every
 * connection — without it SQLite silently ignores the `ON DELETE CASCADE`
 * clauses and deleting a project leaves orphaned conversations and messages.
 */

import Database from "better-sqlite3";
import * as fs from "fs";
import * as path from "path";

export interface Workspace {
  id: number;
  name: string;
  path: string;
  created_at: string;
}

export interface Project {
  id: number;
  workspace_id: number;
  name: string;
  description: string;
  created_at: string;
}

export interface Conversation {
  id: number;
  project_id: number;
  title: string;
  model: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: number;
  conversation_id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

function now(): string {
  return new Date().toISOString();
}

export class TheCoreDatabase {
  private db: Database.Database;

  constructor(dbPath: string) {
    fs.mkdirSync(path.dirname(dbPath), { recursive: true });
    this.db = new Database(dbPath);
    this.db.pragma("journal_mode = WAL");
    // Required per connection, otherwise the cascades never fire.
    this.db.pragma("foreign_keys = ON");
    this.initSchema();
  }

  private initSchema(): void {
    this.db.exec(`
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
    `);
  }

  close(): void {
    try {
      this.db.close();
    } catch {
      // already closed
    }
  }

  // ---------------------------------------------------------------- workspaces

  createWorkspace(name: string, wsPath: string): Workspace {
    const created = now();
    const info = this.db
      .prepare(
        "INSERT INTO workspaces (name, path, created_at) VALUES (?, ?, ?)"
      )
      .run(name, wsPath, created);
    return {
      id: Number(info.lastInsertRowid),
      name,
      path: wsPath,
      created_at: created,
    };
  }

  listWorkspaces(): Workspace[] {
    return this.db
      .prepare("SELECT * FROM workspaces ORDER BY created_at ASC, id ASC")
      .all() as Workspace[];
  }

  getWorkspace(id: number): Workspace | null {
    const row = this.db
      .prepare("SELECT * FROM workspaces WHERE id = ?")
      .get(id) as Workspace | undefined;
    return row ?? null;
  }

  deleteWorkspace(id: number): void {
    // Delete the children explicitly as well, so the cascade never depends
    // on the foreign_keys pragma alone.
    this.deleteProjectChildren(id);
    this.db.prepare("DELETE FROM workspaces WHERE id = ?").run(id);
  }

  private deleteProjectChildren(workspaceId: number): void {
    const projects = this.db
      .prepare("SELECT id FROM projects WHERE workspace_id = ?")
      .all(workspaceId) as { id: number }[];
    for (const p of projects) {
      this.deleteConversationChildren(p.id);
    }
    this.db
      .prepare("DELETE FROM conversations WHERE project_id IN (SELECT id FROM projects WHERE workspace_id = ?)")
      .run(workspaceId);
    this.db
      .prepare("DELETE FROM projects WHERE workspace_id = ?")
      .run(workspaceId);
  }

  // ------------------------------------------------------------------ projects

  createProject(workspaceId: number, name: string, description = ""): Project {
    const created = now();
    const info = this.db
      .prepare(
        "INSERT INTO projects (workspace_id, name, description, created_at) VALUES (?, ?, ?, ?)"
      )
      .run(workspaceId, name, description, created);
    return {
      id: Number(info.lastInsertRowid),
      workspace_id: workspaceId,
      name,
      description,
      created_at: created,
    };
  }

  listProjects(workspaceId: number): Project[] {
    return this.db
      .prepare(
        "SELECT * FROM projects WHERE workspace_id = ? ORDER BY created_at DESC, id DESC"
      )
      .all(workspaceId) as Project[];
  }

  getProject(id: number): Project | null {
    const row = this.db
      .prepare("SELECT * FROM projects WHERE id = ?")
      .get(id) as Project | undefined;
    return row ?? null;
  }

  getWorkspaceForProject(projectId: number): Workspace | null {
    const row = this.db
      .prepare(
        `SELECT w.* FROM workspaces w
         JOIN projects p ON p.workspace_id = w.id
         WHERE p.id = ?`
      )
      .get(projectId) as Workspace | undefined;
    return row ?? null;
  }

  deleteProject(id: number): void {
    this.deleteConversationChildren(id);
    this.db.prepare("DELETE FROM projects WHERE id = ?").run(id);
  }

  private deleteConversationChildren(projectId: number): void {
    this.db
      .prepare("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE project_id = ?)")
      .run(projectId);
    this.db
      .prepare("DELETE FROM conversations WHERE project_id = ?")
      .run(projectId);
  }

  countConversations(projectId: number): number {
    const row = this.db
      .prepare("SELECT COUNT(*) AS n FROM conversations WHERE project_id = ?")
      .get(projectId) as { n: number };
    return row.n;
  }

  // ------------------------------------------------------------- conversations

  createConversation(projectId: number, title: string, model: string): Conversation {
    const stamp = now();
    const info = this.db
      .prepare(
        `INSERT INTO conversations (project_id, title, model, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?)`
      )
      .run(projectId, title, model, stamp, stamp);
    return {
      id: Number(info.lastInsertRowid),
      project_id: projectId,
      title,
      model,
      created_at: stamp,
      updated_at: stamp,
    };
  }

  listConversations(projectId: number): Conversation[] {
    return this.db
      .prepare(
        "SELECT * FROM conversations WHERE project_id = ? ORDER BY updated_at DESC, id DESC"
      )
      .all(projectId) as Conversation[];
  }

  getConversation(id: number): Conversation | null {
    const row = this.db
      .prepare("SELECT * FROM conversations WHERE id = ?")
      .get(id) as Conversation | undefined;
    return row ?? null;
  }

  deleteConversation(id: number): void {
    this.db
      .prepare("DELETE FROM messages WHERE conversation_id = ?")
      .run(id);
    this.db.prepare("DELETE FROM conversations WHERE id = ?").run(id);
  }

  touchConversation(id: number): void {
    this.db
      .prepare("UPDATE conversations SET updated_at = ? WHERE id = ?")
      .run(now(), id);
  }

  /**
   * Give a conversation its automatic name.
   *
   * Only the title changes — `updated_at` is left alone so the sidebar does
   * not reshuffle while the user is typing.
   */
  renameConversation(id: number, title: string): void {
    this.db.prepare("UPDATE conversations SET title = ? WHERE id = ?").run(title, id);
  }

  countMessages(conversationId: number): number {
    const row = this.db
      .prepare("SELECT COUNT(*) AS n FROM messages WHERE conversation_id = ?")
      .get(conversationId) as { n: number };
    return row.n;
  }

  // ------------------------------------------------------------------ messages

  addMessage(conversationId: number, role: string, content: string): Message {
    const created = now();
    const info = this.db
      .prepare(
        "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)"
      )
      .run(conversationId, role, content, created);
    return {
      id: Number(info.lastInsertRowid),
      conversation_id: conversationId,
      role: role as "user" | "assistant",
      content,
      created_at: created,
    };
  }

  listMessages(conversationId: number): Message[] {
    return this.db
      .prepare(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id ASC"
      )
      .all(conversationId) as Message[];
  }
}
