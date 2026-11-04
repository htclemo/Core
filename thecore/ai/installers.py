"""Install Ollama and OpenCode on Windows and Linux.

Nothing is installed at startup. The app only checks whether the commands
are already on the machine. The package installer puts them on Linux.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from thecore.ai.ollama_setup import _find_ollama


def ollama_installed() -> bool:
    return _find_ollama() is not None


def opencode_installed() -> bool:
    if shutil.which("opencode") or shutil.which("opencode.exe"):
        return True
    if sys.platform == "win32":
        npm = (
            Path.home()
            / "AppData"
            / "Roaming"
            / "npm"
            / "node_modules"
            / "@opencode"
            / "cli"
            / "bin"
            / "opencode.exe"
        )
        if npm.is_file():
            return True
        return bool(shutil.which("opencode.cmd") or shutil.which("opencode.bat"))
    local = Path.home() / ".opencode" / "bin" / "opencode"
    return local.is_file()


def _run(command: list[str], timeout: int = 900) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0,
    )
    text = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()
    return completed.returncode, text[-1500:]


def install_ollama() -> str:
    """Install Ollama for this operating system. Raises on failure."""
    if ollama_installed():
        return "Ollama is already installed"
    if sys.platform == "win32":
        code, text = _run(
            [
                "winget",
                "install",
                "-e",
                "--id",
                "Ollama.Ollama",
                "--accept-package-agreements",
                "--accept-source-agreements",
                "--disable-interactivity",
            ]
        )
        if code not in (0, -1978335189):
            raise RuntimeError(text or f"winget exited {code}")
        return "Ollama installed. Restart Core if it is not on PATH yet."
    script = "curl -fsSL https://ollama.com/install.sh | sh"
    if os.geteuid() != 0 and shutil.which("pkexec"):
        code, text = _run(["pkexec", "sh", "-c", script])
    else:
        code, text = _run(["sh", "-c", script])
    if code != 0:
        raise RuntimeError(text or f"Ollama installer exited {code}")
    return "Ollama installed"


def install_opencode() -> str:
    """Install the OpenCode CLI. Raises on failure."""
    if opencode_installed():
        return "OpenCode is already installed"
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if npm:
        code, text = _run([npm, "install", "-g", "opencode-ai"])
        if code == 0 or opencode_installed():
            return "OpenCode installed"
        npm_error = text
    else:
        npm_error = "npm is not installed"
    if sys.platform == "win32":
        code, text = _run(
            [
                "winget",
                "install",
                "-e",
                "--id",
                "SST.opencode",
                "--accept-package-agreements",
                "--accept-source-agreements",
                "--disable-interactivity",
            ]
        )
        if code not in (0, -1978335189) and not opencode_installed():
            raise RuntimeError(text or npm_error or f"winget exited {code}")
        return "OpenCode installed. Open a new Core window if the command is not found yet."
    code, text = _run(["sh", "-c", "curl -fsSL https://opencode.ai/install | bash"])
    if code != 0 and not opencode_installed():
        raise RuntimeError(text or npm_error or f"OpenCode installer exited {code}")
    return "OpenCode installed"


class RuntimeInstall(QThread):
    """Install one tool off the UI thread."""

    log = Signal(str)
    finished_with = Signal(str)

    def __init__(self, kind: str, parent=None) -> None:
        super().__init__(parent)
        self._kind = kind

    def run(self) -> None:
        name = "Ollama" if self._kind == "ollama" else "OpenCode"
        self.log.emit(f"Installing {name}…")
        try:
            if self._kind == "ollama":
                message = install_ollama()
            else:
                message = install_opencode()
        except Exception as exc:  # noqa: BLE001
            message = f"{name} install failed: {exc}"
        self.log.emit(message)
        self.finished_with.emit(message)
