"""Application bootstrap for TheCore."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from thecore.debug_log import enable_debugging, install_exception_hook, logger
from thecore.styles import APP_STYLESHEET
from thecore.splash import SplashScreen
from thecore.ui.main_window import MainWindow

# Minimum splash-screen display time (ms) so the animation is actually seen.
_MIN_SPLASH_MS = 1200


def _use_core_taskbar_icon() -> None:
    """Make the taskbar use the Core icon instead of Python's.

    Core is started with pythonw.exe. Windows then pins the Python icon to
    the taskbar, even when the window's own icon (top left) is the Core one.
    An explicit app id, set before any window exists, breaks that link.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TheCore.Core")
    except (AttributeError, OSError):
        pass


def run() -> int:
    started = time.monotonic()
    _use_core_taskbar_icon()

    log_path = enable_debugging()
    if log_path is not None:
        logger.info("Debug logging is on — writing to %s", log_path)
    install_exception_hook()

    app = QApplication(sys.argv)
    app.setApplicationName("Core")
    app.setOrganizationName("TheCore")
    app.setStyleSheet(APP_STYLESHEET)

    icon_path = Path(__file__).resolve().parents[1] / "assets" / "thecore.ico"
    if not icon_path.is_file():
        icon_path = Path(__file__).resolve().parents[1] / "assets" / "thecore_icon.png"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    # --- splash screen while the app loads ---
    splash = SplashScreen()
    splash.show()
    app.processEvents()
    splash_start = time.monotonic()
    logger.info("Splash shown (%.1f ms in)", (time.monotonic() - started) * 1000)

    window: MainWindow | None = None
    window_ready = False

    def _try_show_main() -> None:
        """Show the main window once it is built and the splash minimum time
        has elapsed."""
        if window is None or not window_ready:
            return
        elapsed_ms = (time.monotonic() - splash_start) * 1000.0
        remaining_ms = max(0, _MIN_SPLASH_MS - elapsed_ms)
        QTimer.singleShot(int(remaining_ms), _switch_to_main)

    def _switch_to_main() -> None:
        splash.finish_and_accept()
        splash.close()
        # Maximise *now*: doing it in the constructor would show the window
        # straight away, behind the splash screen.
        window.showMaximized()
        window.raise_()
        window.activateWindow()
        logger.info(
            "Main window shown after %.1f s",
            (time.monotonic() - splash_start),
        )

    def _build_main_window() -> None:
        nonlocal window, window_ready
        build_started = time.monotonic()
        try:
            from thecore.ai.installers import ollama_installed, opencode_installed

            splash.set_status("Checking Ollama", 0.35)
            app.processEvents()
            ollama_state = "installed" if ollama_installed() else "not installed"
            splash.set_status(f"Ollama: {ollama_state}", 0.5)
            app.processEvents()
            splash.set_status("Checking OpenCode", 0.65)
            app.processEvents()
            opencode_state = "installed" if opencode_installed() else "not installed"
            splash.set_status(f"OpenCode: {opencode_state}", 0.8)
            app.processEvents()
            splash.set_status("Opening workspace", 0.9)
            app.processEvents()
            window = MainWindow()
        except Exception as exc:
            logger.exception("Startup failed")
            splash.set_status(f"Startup failed: {exc}", 0.9)
            return
        window_ready = True
        splash.set_status("Ready", 1.0)
        logger.info("Main window built in %.1f ms", (time.monotonic() - build_started) * 1000)
        _try_show_main()

    # Build the main window on the next event loop iteration so the splash
    # has already been painted to the screen.
    QTimer.singleShot(0, _build_main_window)

    return app.exec()
