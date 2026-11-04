"""Voice helpers: dictation and speaking the answer.

Two small Windows features that the chat composer offers:

* **Dictation** — presses Win+H, which is the Windows voice-typing shortcut.
  The keystrokes are sent with ``keybd_event`` because ``SendKeys`` cannot
  press the Windows key.
* **Speaking** — reads a text out loud with the built-in SAPI voice through
  PowerShell.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Optional

# Windows virtual key codes.
_VK_LWIN = 0x5B
_VK_H = 0x48
_KEYEVENTF_KEYUP = 0x0002


def dictation_supported() -> bool:
    """True when this is Windows (the only platform with Win+H)."""
    return sys.platform == "win32"


def start_dictation() -> bool:
    """Start Windows voice typing (Win+H).

    Returns True when the shortcut was sent.
    """
    if not dictation_supported():
        return False
    try:
        import ctypes

        user32 = ctypes.windll.user32
        user32.keybd_event(_VK_LWIN, 0, 0, 0)
        user32.keybd_event(_VK_H, 0, 0, 0)
        user32.keybd_event(_VK_H, 0, _KEYEVENTF_KEYUP, 0)
        user32.keybd_event(_VK_LWIN, 0, _KEYEVENTF_KEYUP, 0)
        return True
    except Exception:  # noqa: BLE001
        return False


def speak(text: str) -> bool:
    """Read a text out loud with the Windows speech voice."""
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    if sys.platform != "win32":
        return False
    # Keep it short — a long answer would talk for minutes.
    excerpt = cleaned[:600]
    escaped = excerpt.replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.Speak('{escaped}')"
    )
    try:
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-Command", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except Exception:  # noqa: BLE001
        return False


def stop_speaking() -> bool:
    """Stop the speech that is currently playing."""
    if sys.platform != "win32":
        return False
    try:
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "Get-Process System.Speech* -ErrorAction SilentlyContinue | "
                "Stop-Process -Force -ErrorAction SilentlyContinue; "
                "Stop-Process -Name powershell -ErrorAction SilentlyContinue",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except Exception:  # noqa: BLE001
        return False
