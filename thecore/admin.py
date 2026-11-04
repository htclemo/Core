"""Windows elevation helpers.

The OpenCode console is meant to behave exactly like an OpenCode session
started from an **administrator PowerShell**.  The only reliable way to get
that is to run TheCore itself elevated, because every process it starts then
inherits the elevated token.
"""

from __future__ import annotations

import ctypes
import os
import sys
from typing import Optional


def is_admin() -> bool:
    """True when this process runs with administrator rights."""
    if os.name != "nt":
        return os.geteuid() == 0  # type: ignore[attr-defined]

    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001 — fall back to the token check
        pass

    try:
        import win32security  # type: ignore

        return bool(win32security.GetTokenInformation(
            win32security.OpenProcessToken(
                win32api.GetCurrentProcess(), win32con.TOKEN_QUERY
            ),
            win32security.TokenElevation,
        ))
    except Exception:  # noqa: BLE001
        return False


def relaunch_as_admin() -> Optional[int]:
    """Restart TheCore with administrator rights.

    Returns the new process id, or ``None`` when the user declined the UAC
    prompt or the relaunch failed.
    """
    if os.name != "nt":
        return None
    if is_admin():
        return os.getpid()

    try:
        executable = sys.executable
    except Exception:  # noqa: BLE001
        return None

    if getattr(sys, "frozen", False):
        # PyInstaller build: re-run the .exe itself.
        args = ""
    else:
        script = os.path.abspath(sys.argv[0])
        args = subprocess_list_quote(script) + " " + " ".join(
            subprocess_list_quote(a) for a in sys.argv[1:]
        )

    try:
        # "runas" triggers the UAC elevation prompt.
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", executable, args, os.getcwd(), 1
        )
    except Exception:  # noqa: BLE001
        return None

    # ShellExecuteW returns > 32 on success.
    return int(result) if result and result > 32 else None


def subprocess_list_quote(value: str) -> str:
    """Quote a single argument for the Windows command line parser."""
    if not value:
        return '""'
    if not any(ch in value for ch in ' \t"'):
        return value
    return '"' + value.replace('\\"', '\\\\"').replace('"', '\\"') + '"'
