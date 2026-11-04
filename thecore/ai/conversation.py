"""Conversation and message domain models used by the AI chat UI."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChatMessage:
    role: str  # "user", "assistant" or "tool"
    content: str
    # Base64-encoded images attached to the message (vision models only).
    images: list[str] = field(default_factory=list)
    # Tool calls the model asked for (assistant messages).
    tool_calls: list[dict] = field(default_factory=list)
    # Which tool produced this message (tool messages).
    tool_name: str = ""


@dataclass
class ConversationView:
    id: int
    project_id: int
    title: str
    model: str
    messages: list[ChatMessage] = field(default_factory=list)
