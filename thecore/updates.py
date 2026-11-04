"""Look for newer Python, Ollama, and Core packages, and install only on request."""

from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from thecore.ai.ollama_setup import (
    _download,
    _find_ollama,
    _latest_release,
    _local_version,
    _start_ollama,
    _version_tuple,
    _wait_until_up,
    _api_version,
)

_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class UpdateItem:
    name: str
    current: str
    latest: str
    available: bool
    kind: str  # "python", "ollama", or "package"
    detail: str = ""
    size: str = ""
    package_id: str = ""


def _get_json(url: str, timeout: float = 8.0):
    request = urllib.request.Request(url, headers={"User-Agent": "Core"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _newer(left: str, right: str) -> bool:
    return _version_tuple(left) > _version_tuple(right)


def _python_allows(spec: str) -> bool:
    """True when the running interpreter matches a requires-python marker."""
    spec = (spec or "").strip()
    if not spec:
        return True
    current = _version_tuple(".".join(str(part) for part in sys.version_info[:3]))

    def cmp(ver: tuple[int, ...]) -> int:
        width = max(len(current), len(ver))
        a = current + (0,) * (width - len(current))
        b = ver + (0,) * (width - len(ver))
        return (a > b) - (a < b)

    for part in spec.split(","):
        part = part.strip()
        op = next((item for item in (">=", "<=", "!=", "==", "~=", ">", "<") if part.startswith(item)), "")
        if not op:
            continue
        ver = _version_tuple(part[len(op):])
        order = cmp(ver)
        if op == ">=" and order < 0:
            return False
        if op == "<=" and order > 0:
            return False
        if op == ">" and order <= 0:
            return False
        if op == "<" and order >= 0:
            return False
        if op == "==" and order != 0:
            return False
        if op == "!=" and order == 0:
            return False
        if op == "~=" and (order < 0 or current[: len(ver) - 1] != ver[:-1]):
            return False
    return True


def _winget_python() -> tuple[str, str]:
    """Newest Python.Python.* package winget can actually install."""
    completed = _run(
        [
            "winget",
            "search",
            "Python.Python.",
            "--source",
            "winget",
            "--accept-source-agreements",
            "--disable-interactivity",
        ],
        90,
    )
    best_version = ""
    best_id = ""
    for line in (completed.stdout or "").splitlines():
        if "Embeddable" in line or "Install Manager" in line:
            continue
        match = re.search(r"(Python\.Python\.\d+\.\d+)\s+(\d+\.\d+\.\d+)", line)
        if match is None:
            continue
        package_id, found = match.group(1), match.group(2)
        if not best_version or _newer(found, best_version):
            best_version, best_id = found, package_id
    if not best_id:
        raise RuntimeError("winget has no Python package")
    return best_version, best_id


def _installed_python_versions() -> list[str]:
    """Every Python on this PC, not only the one Core is running."""
    found = {".".join(str(part) for part in sys.version_info[:3])}
    roots = []
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        roots.append(Path(local) / "Programs" / "Python")
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env_name, "")
        if base:
            roots.append(Path(base) / "Python")
    for root in roots:
        if not root.is_dir():
            continue
        for exe in root.glob("Python*/python.exe"):
            try:
                completed = subprocess.run(
                    [str(exe), "--version"],
                    capture_output=True,
                    text=True,
                    timeout=8,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except (OSError, subprocess.TimeoutExpired):
                continue
            text = f"{completed.stdout} {completed.stderr}"
            match = re.search(r"(\d+\.\d+\.\d+)", text)
            if match:
                found.add(match.group(1))
    return sorted(found, key=_version_tuple)


def _python_update() -> UpdateItem:
    """The newest Python winget can install, unless that build is already on the PC."""
    running = ".".join(str(part) for part in sys.version_info[:3])
    installed = _installed_python_versions()
    newest_here = installed[-1] if installed else running
    try:
        latest, package_id = _winget_python()
    except (OSError, subprocess.TimeoutExpired, RuntimeError):
        return UpdateItem("Python", running, "unknown", False, "python")
    available = _newer(latest, newest_here)
    if available:
        detail = "wordt naast de huidige Python geïnstalleerd"
        shown = running
    else:
        detail = f"Core draait op {running}" if newest_here != running else "intern  ·  bij"
        shown = newest_here
    return UpdateItem(
        "Python",
        shown,
        latest,
        available,
        "python",
        detail,
        "",
        package_id,
    )


def _bytes(size: int) -> str:
    if size >= 1_000_000_000:
        return f"{size / 1_000_000_000:.1f} GB"
    if size >= 1_000_000:
        return f"{size / 1_000_000:.0f} MB"
    if size <= 0:
        return ""
    return f"{size / 1_000:.0f} KB"


def _ollama_notes() -> tuple[str, str, str]:
    """Latest version, a short release note, and the installer size."""
    payload = _get_json(
        "https://api.github.com/repos/ollama/ollama/releases/latest",
        timeout=12,
    )
    latest = str(payload.get("tag_name") or "").lstrip("vV")
    body = str(payload.get("body") or "")
    line = ""
    for raw in body.splitlines():
        text = raw.strip().lstrip("-*#> ").strip()
        if len(text) > 40:
            line = text
            break
    size = ""
    for asset in payload.get("assets") or []:
        if str(asset.get("name") or "").lower() == "ollamasetup.exe":
            size = _bytes(int(asset.get("size") or 0))
            break
    return latest, line[:220], size


def _ollama_update() -> UpdateItem:
    current = _local_version(_find_ollama()) or "niet geïnstalleerd"
    try:
        latest, detail, size = _ollama_notes()
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError, TypeError):
        return UpdateItem("Ollama", current, "unknown", False, "ollama")
    available = bool(latest) and (
        current == "niet geïnstalleerd" or _version_tuple(latest) > _version_tuple(current)
    )
    return UpdateItem("Ollama", current, latest or "unknown", available, "ollama", detail, size)


def _requirement_names() -> list[str]:
    path = _ROOT / "requirements.txt"
    if not path.is_file():
        return []
    names: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if ";" in line:
            marker = line.split(";", 1)[1]
            if "Windows" in marker and sys.platform != "win32":
                continue
            line = line.split(";", 1)[0].strip()
        name = re.split(r"[<>=!\[]", line, maxsplit=1)[0].strip()
        if name:
            names.append(name)
    return names


def _package_update(name: str) -> UpdateItem:
    try:
        current = version(name)
    except PackageNotFoundError:
        current = "not installed"
    try:
        payload = _get_json(f"https://pypi.org/pypi/{name}/json", timeout=6)
        latest = _compatible_release(payload)
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return UpdateItem(name, current, "unknown", False, "package")
    available = bool(latest) and (
        current == "not installed" or _newer(latest, current)
    )
    return UpdateItem(name, current, latest or "unknown", available, "package")


def _compatible_release(payload: dict) -> str:
    """Newest PyPI release this Python can install. The plain latest often cannot."""
    best = ""
    for release, files in (payload.get("releases") or {}).items():
        usable = [item for item in files or [] if not item.get("yanked")]
        if not usable:
            continue
        spec = str(usable[0].get("requires_python") or "")
        if not _python_allows(spec):
            continue
        if not best or _newer(str(release), best):
            best = str(release)
    return best


def check_updates() -> list[UpdateItem]:
    """Python, Ollama, and the packages listed in requirements.txt."""
    items = [_python_update(), _ollama_update()]
    items.extend(_package_update(name) for name in _requirement_names())
    return items


class UpdateCheck(QThread):
    """Run the check off the UI thread. Nothing is downloaded or installed."""

    finished_with = Signal(object)

    def run(self) -> None:
        try:
            self.finished_with.emit(check_updates())
        except Exception as exc:  # noqa: BLE001
            self.finished_with.emit(exc)


def _run(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _last_line(completed: subprocess.CompletedProcess[str], fallback: str) -> str:
    detail = (completed.stderr or completed.stdout or fallback).strip()
    return detail.splitlines()[-1][:220]


_PERCENT = re.compile(r"(?<!\d)(100|\d{1,2})\s*%")


def _stream(command: list[str], timeout: int, on_fraction) -> subprocess.CompletedProcess[str]:
    """Run a command and report 0..1 from any percent it prints."""
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    started = time.monotonic()
    chunks: list[str] = []
    fraction = 0.04
    assert proc.stdout is not None
    incoming: queue.Queue[str | None] = queue.Queue()

    def _read() -> None:
        while True:
            block = proc.stdout.read(160) if proc.stdout is not None else ""
            if not block:
                incoming.put(None)
                return
            incoming.put(block)

    threading.Thread(target=_read, daemon=True).start()
    while True:
        if time.monotonic() - started > timeout:
            proc.kill()
            raise subprocess.TimeoutExpired(command, timeout)
        try:
            block = incoming.get(timeout=0.4)
        except queue.Empty:
            fraction = min(0.9, fraction + 0.015)
            if on_fraction is not None:
                on_fraction(fraction)
            continue
        if block is None:
            break
        chunks.append(block)
        found = _PERCENT.findall(block)
        if found:
            fraction = min(0.98, int(found[-1]) / 100)
        else:
            fraction = min(0.9, fraction + 0.03)
        if on_fraction is not None:
            on_fraction(fraction)
    code = proc.wait(timeout=30)
    if on_fraction is not None:
        on_fraction(1.0)
    output = "".join(chunks)
    return subprocess.CompletedProcess(command, code, output, "")


def apply_update(item: UpdateItem, on_fraction=None) -> str:
    """Install one update. Returns a short status line."""
    if item.kind == "package":
        completed = _stream(
            [sys.executable, "-m", "pip", "install", "--upgrade", item.name],
            600,
            on_fraction,
        )
        if completed.returncode != 0:
            raise RuntimeError(_last_line(completed, "pip failed"))
        shown = _run([sys.executable, "-m", "pip", "show", item.name], 60)
        installed = item.current
        for line in (shown.stdout or "").splitlines():
            if line.lower().startswith("version:"):
                installed = line.split(":", 1)[1].strip()
                break
        if item.current not in ("not installed", "") and not _newer(installed, item.current):
            raise RuntimeError(f"{item.name} stayed at {installed}")
        return f"{item.name} updated to {installed}"
    if item.kind == "ollama":
        _latest, url = _latest_release()
        if not url:
            raise RuntimeError("Ollama installer not found")
        destination = Path(os.environ.get("TEMP", ".")) / "OllamaSetup.exe"
        if on_fraction is not None:
            on_fraction(0.08)
        _download(url, destination)
        if on_fraction is not None:
            on_fraction(0.45)
        completed = _stream([str(destination), "/SILENT", "/NORESTART"], 600, on_fraction)
        if completed.returncode not in (0, 3010):
            raise RuntimeError(f"Ollama installer exited {completed.returncode}")
        ollama_exe = _find_ollama()
        if ollama_exe is not None and not _api_version():
            _start_ollama(ollama_exe)
            _wait_until_up()
        return f"Ollama updated to {item.latest}"
    if item.kind == "python":
        package_id = item.package_id or (
            f"Python.Python.{sys.version_info[0]}.{sys.version_info[1]}"
        )
        same_line = package_id == (
            f"Python.Python.{sys.version_info[0]}.{sys.version_info[1]}"
        )
        completed = _stream(
            [
                "winget",
                "upgrade" if same_line else "install",
                "--id",
                package_id,
                "-e",
                "--scope",
                "user",
                "--accept-package-agreements",
                "--accept-source-agreements",
                "--disable-interactivity",
            ],
            900,
            on_fraction,
        )
        # winget uses 0 for success and -1978335189 when the package is already current.
        if completed.returncode not in (0, -1978335189):
            raise RuntimeError(_last_line(completed, "winget failed"))
        if same_line:
            return f"Python updated to {item.latest}. Restart Core."
        return (
            f"Python {item.latest} is installed next to {item.current}. "
            "Core keeps running on the current Python until its environment is recreated."
        )
    raise RuntimeError(f"Cannot update {item.name}")


class ApplyUpdates(QThread):
    """Install the chosen updates. Started only from the dropdown."""

    progress = Signal(int, str)
    finished_with = Signal(object)

    def __init__(self, items: list[UpdateItem], parent=None) -> None:
        super().__init__(parent)
        self._items = list(items)

    def run(self) -> None:
        lines: list[str] = []
        count = max(1, len(self._items))
        try:
            for index, item in enumerate(self._items):
                label = f"Updating {item.name}   {index + 1}/{count}"

                def report(fraction: float, start=index, text=label) -> None:
                    percent = int((start + max(0.0, min(1.0, fraction))) / count * 100)
                    self.progress.emit(min(100, percent), text)

                report(0.0)
                try:
                    lines.append(apply_update(item, report))
                except Exception as exc:  # noqa: BLE001
                    lines.append(f"{item.name}: {exc}")
                report(1.0)
            self.progress.emit(100, "Done")
            self.finished_with.emit(lines)
        except Exception as exc:  # noqa: BLE001
            self.finished_with.emit(exc)
