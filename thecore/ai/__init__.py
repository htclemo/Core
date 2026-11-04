"""TheCore AI — local LLM (Ollama) chat, workspaces, and model memory tracking."""

__version__ = "1.0.0"

from .database import Database, Workspace, Project, Conversation, Message  # noqa: F401
from .ollama_client import OllamaClient, OllamaModel, ChatMessage  # noqa: F401
from .model_tracker import ModelTracker, ModelMemorySnapshot, ModelMemoryDelta  # noqa: F401
from .opencode_integration import OpenCodeIntegration  # noqa: F401
from .worker import OllamaWorker, OllamaThread  # noqa: F401
