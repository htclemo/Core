"""Make sure Ollama is installed, running, and up to date when Core starts.

The work runs on a background thread. The window only receives status text.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from PySide6.QtCore import QThread, Signal

_API = "http://127.0.0.1:11434/api/version"
_RELEASES = "https://api.github.com/repos/ollama/ollama/releases/latest"


def _version_tuple(text: str) -> tuple[int, ...]:
    numbers: list[int] = []
    for part in (text or "").lstrip("vV").split("."):
        digits = ""
        for char in part:
            if char.isdigit():
                digits += char
            else:
                break
        if not digits:
            break
        numbers.append(int(digits))
    return tuple(numbers)


def _api_version() -> str:
    try:
        with urllib.request.urlopen(_API, timeout=0.8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return str(payload.get("version") or "")
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return ""


def _find_ollama() -> Path | None:
    which = shutil.which("ollama")
    if which:
        return Path(which)
    local = os.environ.get("LOCALAPPDATA", "")
    for relative in (
        ("Programs", "Ollama", "ollama.exe"),
        ("Ollama", "ollama.exe"),
    ):
        path = Path(local, *relative)
        if path.is_file():
            return path
    return None


def _app_exe(ollama_exe: Path) -> Path:
    candidate = ollama_exe.with_name("ollama app.exe")
    return candidate if candidate.is_file() else ollama_exe


def _local_version(ollama_exe: Path | None) -> str:
    running = _api_version()
    if running:
        return running
    if ollama_exe is None:
        return ""
    try:
        completed = subprocess.run(
            [str(ollama_exe), "--version"],
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    text = f"{completed.stdout} {completed.stderr}"
    for token in text.replace(",", " ").split():
        if token[:1].isdigit() or (
            token.lower().startswith("v") and any(char.isdigit() for char in token)
        ):
            return token.lstrip("vV")
    return ""


def _latest_release() -> tuple[str, str]:
    request = urllib.request.Request(
        _RELEASES,
        headers={
            "User-Agent": "Core",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))
    version = str(payload.get("tag_name") or "").lstrip("vV")
    url = ""
    for asset in payload.get("assets") or []:
        if str(asset.get("name") or "").lower() == "ollamasetup.exe":
            url = str(asset.get("browser_download_url") or "")
            break
    return version, url


def _download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Core"})
    with urllib.request.urlopen(request, timeout=30) as response, destination.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            handle.write(chunk)


def _start_ollama(ollama_exe: Path) -> None:
    app = _app_exe(ollama_exe)
    flags = 0
    flags |= getattr(subprocess, "DETACHED_PROCESS", 0)
    flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    if app.name.lower() == "ollama.exe":
        subprocess.Popen(
            [str(app), "serve"],
            creationflags=flags,
            close_fds=True,
        )
    else:
        subprocess.Popen([str(app)], creationflags=flags, close_fds=True)


def _wait_until_up(seconds: float = 20.0) -> str:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        version = _api_version()
        if version:
            return version
        time.sleep(0.5)
    return ""


class OllamaSetup(QThread):
    """Install, start, and update Ollama without blocking the window."""

    status = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._last = ""

    def last_status(self) -> str:
        return self._last

    def _say(self, text: str) -> None:
        self._last = text
        self.status.emit(text)

    def run(self) -> None:  # noqa: D401
        try:
            self._ensure()
        except Exception as exc:  # noqa: BLE001
            self._say(f"OLLAMA: {exc}")

    def _ensure(self) -> None:
        ollama_exe = _find_ollama()
        version = _api_version()
        if not version:
            if ollama_exe is None:
                self._install("OLLAMA: INSTALLING")
                ollama_exe = _find_ollama()
            else:
                self._say("OLLAMA: STARTING")
                _start_ollama(ollama_exe)
            version = _wait_until_up()

        if not version and ollama_exe is None:
            self._say("OLLAMA: INSTALL FAILED")
            return
        if not version:
            self._say("OLLAMA: NOT RESPONDING")
            return

        self._say(f"OLLAMA: ONLINE {version}")
        try:
            latest, url = _latest_release()
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
            return
        if not latest or not url:
            return
        if _version_tuple(latest) <= _version_tuple(version):
            self._say(f"OLLAMA: UP TO DATE {version}")
            return
        self._say(f"OLLAMA: UPDATING {version} → {latest}")
        self._install_from(url)
        self._say(f"OLLAMA: UPDATED {latest}")

    def _install(self, label: str) -> None:
        self._say(label)
        _latest, url = _latest_release()
        if not url:
            raise RuntimeError("NO INSTALLER")
        self._install_from(url)

    def _install_from(self, url: str) -> None:
        destination = Path(os.environ.get("TEMP", ".")) / "OllamaSetup.exe"
        _download(url, destination)
        # Inno Setup: install quietly, then the tray app is started below.
        subprocess.run(
            [str(destination), "/SILENT", "/NORESTART"],
            timeout=600,
        )
        ollama_exe = _find_ollama()
        if ollama_exe is not None and not _api_version():
            _start_ollama(ollama_exe)
            _wait_until_up()
