"""Debug logging to a rotating log file.

The app writes a log file when debugging is switched on, either with the
``--debug`` command line flag or with the ``THECORE_DEBUG=1`` environment
variable.  The file lives next to the database so it is easy to find::

    %APPDATA%\\TheCore\\thecore.log    (Windows)
    ~/.thecore/thecore.log              (other platforms)

The log records the start-up steps with their durations, every periodic
timer, the database and console activity, and any unhandled exception.  That is
what you need to answer "why is the app slow?".
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import time
from pathlib import Path
from typing import Optional

LOGGER_NAME = "thecore"

# Set by enable_debugging(); every part of the app uses this logger.
logger = logging.getLogger(LOGGER_NAME)
logger.setLevel(logging.INFO)
logger.propagate = False

_log_file: Optional[Path] = None
_enabled = False


def _log_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        path = Path(base) / "TheCore"
    else:
        path = Path.home() / ".thecore"
    path.mkdir(parents=True, exist_ok=True)
    return path


def debug_requested(argv: Optional[list[str]] = None) -> bool:
    """True when the user asked for debugging."""
    if os.environ.get("THECORE_DEBUG", "").strip().lower() in ("1", "true", "yes"):
        return True
    args = argv if argv is not None else sys.argv
    return any(a in ("--debug", "-d") for a in args)


def enable_debugging(argv: Optional[list[str]] = None) -> Optional[Path]:
    """Switch the log file on.  Returns the path, or None when off."""
    global _log_file, _enabled

    if not debug_requested(argv):
        logger.setLevel(logging.CRITICAL)
        return None

    if _enabled and _log_file is not None:
        return _log_file

    path = _log_dir() / "thecore.log"
    handler = logging.handlers.RotatingFileHandler(
        str(path), maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s.%(msecs)03d  %(levelname)-7s  %(name)s  %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    _log_file = path
    _enabled = True
    logger.info("=" * 68)
    logger.info("TheCore debug log started (pid %d)", os.getpid())
    logger.info("=" * 68)
    return path


def log_file_path() -> Optional[Path]:
    """The path of the active log file (None when debugging is off)."""
    return _log_file


def is_debugging() -> bool:
    return _enabled


def log_timing(label: str, started: float) -> None:
    """Log how long something took."""
    if not _enabled:
        return
    logger.info("%-34s %8.1f ms", label, (time.monotonic() - started) * 1000)


def install_exception_hook() -> None:
    """Report unhandled exceptions to the log instead of losing them."""

    def hook(exc_type, value, tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, value, tb)
            return
        logger.critical("Unhandled exception", exc_info=(exc_type, value, tb))

    sys.excepthook = hook
