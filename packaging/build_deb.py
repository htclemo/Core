"""Build a .deb of Core that can be sent to another Linux PC.

Run from the project root:

    python packaging/build_deb.py

The package installs the app under /usr/share/thecore and a launcher at
/usr/bin/thecore. PySide6 comes from the distro packages.
"""

from __future__ import annotations

import hashlib
import io
import tarfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.0.1"
PACKAGE = "thecore"
OUT = ROOT / "dist" / f"{PACKAGE}_{VERSION}_all.deb"

SKIP = {".venv", "node_modules", "__pycache__", ".git", "dist", ".cursor", "electron-app"}


def _should_skip(path: Path) -> bool:
    return any(part in SKIP for part in path.parts)


def _tar(files: list[tuple[str, bytes, int]]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, data, mode in files:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = mode
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "root"
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _ar(members: list[tuple[str, bytes]]) -> bytes:
    out = bytearray(b"!<arch>\n")
    for name, data in members:
        header_name = name.encode("ascii")
        if len(header_name) < 16:
            header_name = header_name + b" " * (16 - len(header_name))
        size = str(len(data)).encode("ascii").ljust(10)
        header = header_name + b"0           0     0     100644  " + size + b"`\n"
        if len(header) != 60:
            raise RuntimeError(f"bad ar header length {len(header)}")
        out += header
        out += data
        if len(data) % 2:
            out += b"\n"
    return bytes(out)


def main() -> None:
    data_files: list[tuple[str, bytes, int]] = []
    prefix = "usr/share/thecore"
    for path in ROOT.rglob("*"):
        if not path.is_file() or _should_skip(path.relative_to(ROOT)):
            continue
        if path.suffix in {".pyc", ".deb"}:
            continue
        rel = path.relative_to(ROOT).as_posix()
        data_files.append((f"{prefix}/{rel}", path.read_bytes(), 0o644))

    launcher = textwrap.dedent(
        """\
        #!/bin/sh
        cd /usr/share/thecore
        exec python3 main.py "$@"
        """
    ).encode()
    desktop = textwrap.dedent(
        """\
        [Desktop Entry]
        Type=Application
        Name=Core
        Comment=Local AI workspace
        Exec=/usr/bin/thecore
        Icon=thecore
        Terminal=false
        Categories=Development;
        """
    ).encode()
    icon = (ROOT / "assets" / "thecore_icon.png").read_bytes()
    data_files.append(("usr/bin/thecore", launcher, 0o755))
    data_files.append(("usr/share/applications/thecore.desktop", desktop, 0o644))
    data_files.append(("usr/share/icons/hicolor/256x256/apps/thecore.png", icon, 0o644))

    md5 = hashlib.md5()
    lines = []
    for name, data, _mode in data_files:
        digest = hashlib.md5(data).hexdigest()
        lines.append(f"{digest}  {name}")
        md5.update(data)
    control = textwrap.dedent(
        f"""\
        Package: {PACKAGE}
        Version: {VERSION}
        Architecture: all
        Maintainer: Lemo <lemo@localhost>
        Depends: python3, python3-pyside6.qtwidgets, python3-pyside6.qtgui, python3-pyside6.qtcore, python3-psutil, python3-pil, python3-numpy, python3-pyqtgraph, python3-pyte
        Section: utils
        Priority: optional
        Homepage: https://localhost/thecore
        Description: Core AI workspace
         Chat with Ollama, OpenCode and cloud models.
         Installs Ollama when it is missing, and can install OpenCode from the app.
        """
    ).encode()
    postinst = textwrap.dedent(
        """\
        #!/bin/sh
        set -e
        if ! command -v ollama >/dev/null 2>&1; then
            curl -fsSL https://ollama.com/install.sh | sh || true
        fi
        if ! command -v opencode >/dev/null 2>&1; then
            curl -fsSL https://opencode.ai/install | bash || true
            if [ -x /root/.opencode/bin/opencode ]; then
                cp -a /root/.opencode/bin/opencode /usr/local/bin/opencode
                chmod 755 /usr/local/bin/opencode
            fi
        fi
        chmod 755 /usr/bin/thecore
        exit 0
        """
    ).encode()
    control_tar = _tar(
        [
            ("control", control, 0o644),
            ("postinst", postinst, 0o755),
            ("md5sums", ("\n".join(lines) + "\n").encode(), 0o644),
        ]
    )
    data_tar = _tar(data_files)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(
        _ar(
            [
                ("debian-binary", b"2.0\n"),
                ("control.tar.gz", control_tar),
                ("data.tar.gz", data_tar),
            ]
        )
    )
    print(OUT)
    print(f"{OUT.stat().st_size} bytes")


if __name__ == "__main__":
    main()
