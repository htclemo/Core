"""Persistent program settings for TheCore.

These are the settings that must survive a restart — the text size and the
model the user last picked.  They live next to the cloud API keys in
``%APPDATA%\\TheCore`` (never in the database, never in the repository).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _settings_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    folder = Path(base) / "TheCore"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "settings.json"


def load_settings() -> dict[str, Any]:
    """Read the stored settings (an empty dict when there are none)."""
    path = _settings_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_settings(settings: dict[str, Any]) -> None:
    """Write the settings, keeping the file readable."""
    try:
        _settings_path().write_text(
            json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


def get_setting(key: str, default: Any = None) -> Any:
    return load_settings().get(key, default)


def set_setting(key: str, value: Any) -> None:
    """Store one setting and keep the rest."""
    settings = load_settings()
    settings[key] = value
    save_settings(settings)
