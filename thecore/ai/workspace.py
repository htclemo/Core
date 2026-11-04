"""Workspace and project domain models used by the AI sidebar."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WorkspaceItem:
    id: int
    name: str
    path: str


@dataclass
class ProjectItem:
    id: int
    workspace_id: int
    name: str
    description: str
