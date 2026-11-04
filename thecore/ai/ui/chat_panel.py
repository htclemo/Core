"""Main AI chat panel: Cursor-style layout with OpenCode console at bottom.

Header: provider + model + load/unload + status + memory
Left sidebar: workspaces / projects / conversations (in AIWorkspacePanel)
Center: message area
Bottom: OpenCode console (when active) + chat input
"""

from __future__ import annotations

import base64
import time
from dataclasses import replace
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QEvent, QThread, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from thecore.ai.conversation import ChatMessage
from thecore.ai.conversation_title import title_from_question
from thecore.ai.cloud_client import (
    CloudClient,
    CloudModel,
    PROVIDERS,
    PROVIDERS_BY_ID,
    catalogue_models,
    cloud_capabilities,
    configured_providers,
    load_base_url,
    load_key,
)
from thecore.ai.tools import ToolRegistry
from thecore.ai.cloud_worker import (
    CloudListThread,
    CloudListWorker,
    CloudPingThread,
    CloudPingWorker,
    CloudCatalogueThread,
    CloudCatalogueWorker,
    CloudThread,
    CloudWorker,
)
from thecore.ai.database import Database
from thecore.ai.model_catalogue import ModelEntry, build_entries
from thecore.ai.model_tracker import ModelTracker
from thecore.collectors.ai_memory import AiMemoryCollector
from thecore.ai.ollama_client import OllamaClient
from thecore.ai.model_load_worker import ModelLoadWorker
from thecore.ai.installers import RuntimeInstall, ollama_installed, opencode_installed
from thecore.ai.opencode_integration import OpenCodeIntegration
from thecore.ai.ui.capability_icons import CapabilityIcons
from thecore.ai.ui.chat_composer import ChatComposer
from thecore.ai.voice import speak, start_dictation
from thecore.debug_log import log_timing, logger
from thecore.ai.ui.loading_spinner import LoadingSpinner
from thecore.ai.ui.opencode_console import OpenCodeConsole
from thecore.ai.ui.memory_gauge import MemoryGauge
from thecore.ai.ui.message_widget import MessageWidget, _COLLAPSED_LINES
from thecore.ai.ui.provider_icons import provider_icon
from thecore.ai.ui.status_lamp import StatusLamp
from thecore.ai.ui.thinking_indicator import ThinkingIndicator
from thecore.ai.worker import OllamaThread, OllamaWorker


# Nudges the model into actually calling the tools instead of only talking
# about doing it.  Kept deliberately narrow: tools are for file/project work
# inside the workspace, NOT for looking up general facts on the web.  A
# question like "hoe hoog is de toren van Pisa" must be answered from the
# model's own knowledge, not by running Invoke-RestMethod.
_TOOL_SYSTEM_PROMPT = (
    "You are a helpful coding assistant working inside the project folder. "
    "You have tools to read, write and edit files and run commands in the "
    "project folder. ONLY use them when the user explicitly asks you to work "
    "with files or run commands in the project.\n\n"
    "For general questions — history, facts, explanations, code advice — "
    "answer directly from your own knowledge. Do NOT try to look things up "
    "by running commands or calling web APIs unless the user asks you to. "
    "Never output PowerShell or shell commands as plain text; if you need to "
    "do something, use the structured tool call instead."
)


class _BgCall(QThread):
    """Run one blocking call off the UI thread and return its result."""

    done = Signal(object)

    def __init__(self, fn, parent=None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            self.done.emit(self._fn())
        except Exception as exc:  # noqa: BLE001
            self.done.emit(exc)


class ChatPanel(QFrame):
    """Cursor-style chat panel wired to Ollama + an embedded OpenCode console."""

    new_project_created = Signal()
    new_workspace_created = Signal()
    # A conversation got its automatic name: (conversation id, title)
    conversation_renamed = Signal(int, str)
    # A conversation was created: (conversation id)
    conversation_created = Signal(int)

    def __init__(
        self,
        database: Database,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("chatPanel")

        self._database = database
        self._client = OllamaClient()
        self._tracker = ModelTracker()
        # Shares the tracker's GPU collector — NVML must be initialised once.
        self._ai_memory = AiMemoryCollector(self._tracker.gpu)
        self._opencode = OpenCodeIntegration()
        self._thread: Optional[OllamaThread] = None
        self._accumulated = ""
        self._current_project_id: Optional[int] = None
        self._current_workspace_id: Optional[int] = None
        self._current_conversation_id: Optional[int] = None
        self._scroll_area: Optional[QScrollArea] = None

        # Provider / backend state
        self._use_opencode = self._opencode.is_available()
        self._use_cloud = False
        self._model_supports_tools = False
        self._model_supports_vision = False
        self._tool_registry_obj: Optional[ToolRegistry] = None
        self._tool_root = ""
        self._pending_images: list[str] = []
        self._pending_image_paths: list[str] = []
        self._image_strip: Optional[QWidget] = None
        self._auto_scroll = True
        self._font_size = 14
        self._opencode_loaded = False
        self._opencode_load_failed = False
        self._opencode_console: Optional[OpenCodeConsole] = None
        self._ollama_loading = False
        self._ollama_model_loaded = False
        self._ollama_loaded_model: Optional[str] = None
        self._ollama_load_start: Optional[float] = None
        self._thinking_enabled = True
        self._model_supports_thinking = False
        self._checked_thinking_model = ""

        # UI refs
        self._provider_combo: Optional[QComboBox] = None
        self._model_combo: Optional[QComboBox] = None
        self._load_btn: Optional[QPushButton] = None
        self._think_btn: Optional[QPushButton] = None
        self._ollama_status: Optional[QLabel] = None
        self._status_lamp: Optional[StatusLamp] = None
        self._mem_label: Optional[QLabel] = None
        self._mem_gauge: Optional[MemoryGauge] = None
        self._splitter: Optional[QSplitter] = None
        self._load_spinner: Optional[LoadingSpinner] = None
        self._input_frame: Optional[QFrame] = None
        self._console_frame: Optional[OpenCodeConsole] = None
        self._load_timer: Optional[QTimer] = None
        self._load_worker: Optional[ModelLoadWorker] = None
        self._indicator: Optional[ThinkingIndicator] = None
        self._cloud_provider_id: str = "groq"
        self._settings_btn: Optional[QPushButton] = None
        self._model_indicator: Optional[QLabel] = None

        # ---- the model catalogue ----
        # The dropdown holds the local models *and* the models of every cloud
        # provider that has a key in the settings.
        self._local_models: list = []
        self._cloud_models: list[CloudModel] = []
        self._selected_entry: Optional[ModelEntry] = None
        self._catalogue_thread: Optional[CloudCatalogueThread] = None
        self._list_thread: Optional[CloudListThread] = None
        self._ping_thread: Optional[CloudPingThread] = None
        self._live_providers: set[str] = set()
        self._catalogue_at: float = 0.0

        self._build_ui()

        # Refresh available models every few seconds
        self._model_probe: Optional[_BgCall] = None
        self._mem_probe: Optional[_BgCall] = None
        self._health_probe: Optional[_BgCall] = None
        self._caps_probe: Optional[_BgCall] = None

        self._model_timer = QTimer(self)
        self._model_timer.timeout.connect(self._refresh_models)
        self._model_timer.start(5000)

        # Continuous memory monitoring (VRAM/RAM) every 2 seconds.
        # The sample itself runs on a worker so a slow Ollama call cannot
        # freeze clicks.
        self._mem_timer = QTimer(self)
        self._mem_timer.timeout.connect(self._refresh_memory)
        self._mem_timer.start(2000)

        # Keeps the OLLAMA lamp truthful while OpenCode is the active provider
        self._health_timer = QTimer(self)
        self._health_timer.timeout.connect(self._check_backend_health)
        self._health_timer.start(5000)

        # Fill the VRAM/RAM gauges right away instead of after the first tick.
        QTimer.singleShot(0, self._refresh_memory)

        # Load timer for elapsed-time display during model load
        self._load_timer = QTimer(self)
        self._load_timer.timeout.connect(self._tick_load_timer)

        # Initial provider selection.  The index is looked up by id — the
        # dropdown carries icons and its order is not fixed.
        try:
            wanted = "opencode" if self._use_opencode else "ollama"
            self._provider_combo.blockSignals(True)
            index = self._provider_combo.findData(wanted)
            self._provider_combo.setCurrentIndex(index if index >= 0 else 0)
            self._provider_combo.blockSignals(False)
            self._configure_provider(
                "OpenCode" if self._use_opencode else "Ollama"
            )
            self._use_cloud = False
            self._rebuild_catalogue(kind="local")
            self._refresh_models()
        except Exception as e:
            try:
                from thecore.debug_log import logger
                logger.exception("Error during initial provider selection: %s", e)
            except Exception:
                pass

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- the composer (the input area) ----
        # The provider and model pickers live inside it, like in the reference
        # design, so the header only carries the actions and the meters.
        self._composer = ChatComposer()
        self._provider_combo = self._composer.provider_combo
        self._model_combo = self._composer.model_combo
        self._attach_btn = self._composer.attach_button
        self._stop_btn = self._composer.stop_button
        self._input = self._composer.input

        try:
            self._composer.sendRequested.connect(self._on_send)
            self._composer.attachRequested.connect(self._on_attach_image)
            self._composer.micRequested.connect(self._on_dictate)
            self._composer.speakRequested.connect(self._on_speak)
            self._composer.stopRequested.connect(self._on_stop)
            try:
                self._composer.providerChanged.connect(self._on_provider_id)
                self._composer.cloudProviderChanged.connect(self._on_cloud_provider_picked)
            except Exception as e:
                try:
                    from thecore.debug_log import logger
                    logger.exception("Failed to connect providerChanged: %s", e)
                except Exception:
                    pass
            self._composer.refreshListRequested.connect(self._on_refresh_list)
            self._composer.pingListRequested.connect(self._on_ping_list)
            self._composer.installOpencodeRequested.connect(lambda: self._install_runtime("opencode"))
            self._composer.installOllamaRequested.connect(lambda: self._install_runtime("ollama"))
            self._composer.prefillRequested.connect(self._on_prefill)
            try:
                self._composer.modelSelected.connect(self._on_model_selected)
            except Exception as e:
                try:
                    from thecore.debug_log import logger
                    logger.exception("Failed to connect modelSelected: %s", e)
                except Exception:
                    pass
        except Exception as e:
            try:
                from thecore.debug_log import logger
                logger.exception("Failed to connect composer signals: %s", e)
            except Exception:
                pass

        # ---- header: load + capabilities + status + memory ----
        header = QFrame()
        header.setObjectName("chatHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 10, 14, 10)
        header_layout.setSpacing(12)

        # The capability icons live in the bottom bar, next to the model name.
        self._load_btn = self._composer.load_button
        self._load_btn.clicked.connect(self._on_load_clicked)

        # Reasoning (chain-of-thought) visibility toggle — only useful for
        # models that expose `message.thinking`.
        self._think_btn = QPushButton("REASONING")
        self._think_btn.setObjectName("chatThinkButton")
        self._think_btn.setCheckable(True)
        self._think_btn.setChecked(True)
        self._think_btn.setToolTip(
            "Show the model's chain-of-thought while it answers"
        )
        self._think_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._think_btn.clicked.connect(self._on_think_toggled)
        self._think_btn.hide()

        # Loading spinner shown while Ollama loads a model
        self._load_spinner = LoadingSpinner()

        self._ollama_status = QLabel("OLLAMA: CHECKING…")
        self._ollama_status.setObjectName("chatStatus")
        self._ollama_status.hide()

        # Green/red LED + short caption (e.g. "● OLLAMA").
        self._status_lamp = StatusLamp()
        self._status_lamp.set_status("OLLAMA", "loading", "Checking the local backend…")

        self._mem_label = QLabel("GPU/PC MEM: —")
        self._mem_label.setObjectName("chatMemLabel")
        self._mem_label.hide()

        self._mem_gauge = MemoryGauge()
        # The gauges give way first when the header runs out of room — the
        # buttons must keep their labels.
        self._mem_gauge.setMinimumWidth(120)
        self._mem_gauge.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        header_layout.addWidget(self._think_btn)
        header_layout.addWidget(self._load_spinner)
        header_layout.addStretch(1)
        header_layout.addWidget(self._status_lamp)
        header_layout.addSpacing(16)
        header_layout.addWidget(self._mem_gauge)

        root.addWidget(header)

        # ---- message area ----
        scroll = QScrollArea()
        scroll.setObjectName("chatScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._message_container = QWidget()
        self._message_layout = QVBoxLayout(self._message_container)
        self._message_layout.setContentsMargins(0, 0, 0, 0)
        self._message_layout.setSpacing(10)
        self._message_layout.addStretch(1)

        scroll.setWidget(self._message_container)
        self._scroll_area = scroll
        self._setup_auto_scroll()

        # OpenCode fills the main area (the chat viewport), not a strip
        # underneath it.
        self._console_frame = OpenCodeConsole()
        self._console_frame.hide()
        self._console_frame.ready.connect(self._on_opencode_started)
        self._console_frame.failed.connect(self._on_opencode_load_failed)
        self._console_frame.status_received.connect(self._on_opencode_status)

        stage = QWidget()
        stage_layout = QVBoxLayout(stage)
        stage_layout.setContentsMargins(0, 0, 0, 0)
        stage_layout.setSpacing(0)
        stage_layout.addWidget(scroll, stretch=1)
        stage_layout.addWidget(self._console_frame, stretch=1)
        self._list_log = None
        self._runtime_install = None
        QTimer.singleShot(1500, self._ensure_runtimes)
        root.addWidget(stage, stretch=1)

        # ---- the composer (input area, provider picker, action chips) ----
        # The composer was created at the top of this method; it takes the
        # place of the old input row.
        self._input_frame = self._composer

        # Thumbnails of the images waiting to be sent (vision models).
        self._image_strip = QWidget()
        self._image_strip.setObjectName("chatImageStrip")
        image_strip_layout = QHBoxLayout(self._image_strip)
        image_strip_layout.setContentsMargins(0, 0, 0, 4)
        image_strip_layout.setSpacing(6)
        self._image_strip.hide()

        # The send button is gone: Enter sends, and the composer shows a
        # STOP button while a turn is running.
        self._send_btn = None

        root.addWidget(self._input_frame)

        # ---- the model indicator (bottom right) ----
        # The settings live in the sidebar's gear icon, so there is no
        # settings button here any more.
        bottom_bar = QFrame()
        bottom_bar.setObjectName("settingsBottomBar")
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(14, 6, 14, 6)
        bottom_layout.setSpacing(10)

        bottom_layout.addStretch(1)

        # What the model can do: Vision · Tool Use · Reasoning — as icons
        # only, right next to the model name.
        self._capability_icons = CapabilityIcons(compact=True)
        bottom_layout.addWidget(self._capability_icons)

        self._model_indicator = QLabel("—")
        self._model_indicator.setObjectName("chatModelIndicator")
        bottom_layout.addWidget(self._model_indicator)

        root.addWidget(bottom_bar)

        # Initial visibility
        self._set_console_visible(False)

    # ------------------------------------------------------------------ status

    def _set_status(self, text: str, state: str) -> None:
        """Update the backend status.

        The visible part of the header is the LED lamp (``● OLLAMA``); the full
        text is kept in the tooltip so no information is lost.
        """
        if self._ollama_status is not None:
            self._ollama_status.setText(text)
            self._ollama_status.setProperty("state", state)
            self._ollama_status.style().unpolish(self._ollama_status)
            self._ollama_status.style().polish(self._ollama_status)
        self._set_lamp(state, text)

    def _set_lamp(self, state: str, tooltip: str) -> None:
        """Drive the header LED lamp (always captioned ``OLLAMA``)."""
        if self._status_lamp is not None:
            self._status_lamp.set_status("OLLAMA", state, tooltip)

    def _set_console_status(self, text: str, state: str = "online") -> None:
        """Reflect OpenCode console state in the header lamp and status label.

        The embedded console is the real OpenCode UI, so this only reports the
        server's lifecycle (starting / ready / failed) in TheCore's own header.
        """
        if self._ollama_status is not None:
            self._ollama_status.setText(text)
            self._ollama_status.setProperty("state", state)
            self._ollama_status.style().unpolish(self._ollama_status)
            self._ollama_status.style().polish(self._ollama_status)
        self._set_lamp(state, text)

    # ------------------------------------------------------------------ splitter

    def eventFilter(self, obj, event):  # noqa: N802 — Qt API
        """Double-clicking the grip restores the default split."""
        if (
            obj is getattr(self, "_splitter_handle", None)
            and event.type() == QEvent.Type.MouseButtonDblClick
        ):
            self._on_splitter_reset()
            return True
        return super().eventFilter(obj, event)

    def _on_splitter_reset(self) -> None:
        """Restore the default chat/console split."""
        if self._splitter is None:
            return
        total = max(400, self._splitter.height())
        self._splitter.setSizes([int(total * 0.68), int(total * 0.32)])

    # ------------------------------------------------------------------ spinner

    def _start_spinner(self) -> None:
        self._ollama_loading = True
        if self._load_spinner is not None:
            self._load_spinner.start("LOADING")
        if self._load_btn is not None:
            self._load_btn.setEnabled(False)

    def _stop_spinner(self) -> None:
        self._ollama_loading = False
        if self._load_spinner is not None:
            self._load_spinner.stop()
            self._load_spinner.hide()
        if self._load_btn is not None:
            self._load_btn.setEnabled(True)

    # ------------------------------------------------------------------ provider / model

    def _on_provider_index(self, _index: int) -> None:
        """The provider combo was changed (it carries icons, not just text)."""
        provider_id = str(self._provider_combo.currentData() or "")
        self._on_provider_id(provider_id)

    def _on_provider_id(self, provider_id: str) -> None:
        """The provider changed, by id."""
        try:
            from thecore.debug_log import logger
            logger.debug("Provider changed to: %s", provider_id)
        except Exception:
            pass
        try:
            if provider_id == "opencode":
                self._configure_provider("OpenCode")
            elif provider_id == "cloud":
                self._configure_provider("Cloud LLM")
            else:
                self._configure_provider("Ollama")
        except Exception as e:
            try:
                from thecore.debug_log import logger
                logger.exception("Error in _on_provider_id: %s", e)
            except Exception:
                pass

    def _sync_provider_combo(self) -> None:
        """Move the provider picker to match the model that was picked.

        Picking a cloud model in the dropdown switches the provider picker to
        "Cloud LLM" (and back to "Local-LLM" for a local model), so the two
        controls never disagree.
        """
        if self._provider_combo is None:
            return
        entry = self._selected_entry
        if entry is None:
            return
        wanted = "cloud" if entry.kind == "cloud" else "ollama"
        index = self._provider_combo.findData(wanted)
        if index < 0 or index == self._provider_combo.currentIndex():
            return
        # The signals are blocked on purpose: the catalogue must not be
        # rebuilt while the user is picking a model from it.
        self._provider_combo.blockSignals(True)
        self._provider_combo.setCurrentIndex(index)
        self._provider_combo.blockSignals(False)

    def _on_prefill(self, text: str) -> None:
        """A chip put a starter text in the input."""
        self._composer.set_text(text)

    def set_scope(self, workspace_name: str, project_name: str) -> None:
        """Remember which workspace and project the turn belongs to.

        The picker itself is hidden — the model is picked in the composer, so
        a dead button in the header only gets in the way.
        """
        if workspace_name and project_name:
            text = f"{workspace_name} ▸ {project_name}"
        elif project_name:
            text = project_name
        else:
            text = "This PC"
        self._composer.set_scope(text)

    def _on_dictate(self) -> None:
        """Start Windows voice typing."""
        if start_dictation():
            self._set_status("DICTATING…", "loading")
        else:
            self._set_status("DICTATION NOT AVAILABLE", "offline")

    def _on_speak(self) -> None:
        """Read the last answer out loud."""
        last = ""
        for i in range(self._message_layout.count() - 1, -1, -1):
            widget = self._message_layout.itemAt(i).widget()
            if isinstance(widget, MessageWidget) and widget.role == "assistant":
                last = widget.content
                break
        if not last:
            self._set_status("NOTHING TO READ OUT", "offline")
            return
        if speak(last):
            self._set_status("READING OUT LOUD", "online")
        else:
            self._set_status("SPEECH NOT AVAILABLE", "offline")

    def _configure_provider(self, name: str) -> None:
        """Reconfigure header controls for the selected provider."""
        try:
            from thecore.debug_log import logger
            logger.debug("Configuring provider: %s", name)
        except Exception:
            pass
        self._use_opencode = name.startswith("OpenCode")
        self._use_cloud = name.startswith("Cloud")

        if self._use_cloud:
            if self._model_combo is not None:
                self._model_combo.setEnabled(True)
            if self._load_btn is not None:
                # There is no model to load in the cloud — the key is enough.
                self._load_btn.setText("REFRESH MODELS")
                self._load_btn.setEnabled(True)
                self._load_btn.show()
            if self._think_btn is not None:
                self._think_btn.hide()
            self._composer.set_picker_mode("cloud")
            self._fill_cloud_provider_combo()
            self._refresh_cloud_models()
            self._show_models_for_cloud_provider()
            self._set_console_visible(False)
            self._update_model_indicator()
            return

        if self._use_opencode:
            # Show OpenCode as the active model (it is not user-selectable).
            self._composer.set_picker_mode("opencode")

            if self._opencode.is_available():
                self._set_console_status("OPENCODE: ONLINE", "online")
            else:
                self._set_console_status("OPENCODE: NOT FOUND", "offline")

            if self._load_btn is not None:
                self._load_btn.setText("LOAD OPENCODE")
                self._load_btn.setEnabled(self._opencode.is_available())
                self._load_btn.show()
            if self._think_btn is not None:
                self._think_btn.hide()
            if self._mem_label is not None:
                self._mem_label.setText("GPU/PC MEM: — (OpenCode handles its own)")
        else:
            self._composer.set_picker_mode("ollama")
            if self._model_combo is not None:
                self._model_combo.setEnabled(True)
            if self._load_btn is not None:
                if self._ollama_model_loaded:
                    self._load_btn.setText("UNLOAD")
                    self._load_btn.setProperty("loaded", "true")
                else:
                    self._load_btn.setText("LOAD MODEL")
                    self._load_btn.setProperty("loaded", "false")
                self._load_btn.setEnabled(True)
                self._load_btn.show()
                self._load_btn.style().unpolish(self._load_btn)
                self._load_btn.style().polish(self._load_btn)
            if self._think_btn is not None:
                # Reasoning is only offered by models that expose it.
                self._think_btn.setVisible(self._model_supports_thinking)
                self._think_btn.setText(
                    "REASONING ON" if self._thinking_enabled else "REASONING OFF"
                )
            try:
                self._refresh_models()
            except Exception:
                pass
            try:
                self._select_first_of("local")
            except Exception:
                pass

        # Console / input visibility: the console panel (and its grip) is shown
        # as soon as the OpenCode provider is selected, so the user can always
        # resize it — even while the console is still starting up.
        self._update_model_indicator()
        self._set_console_visible(self._use_opencode)

    # ------------------------------------------------------------------ catalogue

    def _apply_catalogue(self, rows) -> None:
        """Show the given catalogue rows in the model dropdown."""
        if self._composer is None:
            return
        self._composer.set_catalogue(rows)

    def _rebuild_catalogue(self, kind: Optional[str] = None) -> None:
        """Show the model catalogue.
        
        If ``kind`` is ``"local"`` or ``"cloud"``, only models of that kind
        are shown.  When ``kind`` is ``None`` (the default) the full combined
        catalogue is displayed — this preserves the original behaviour.
        """
        try:
            from thecore.debug_log import logger
            logger.debug("Rebuilding catalogue with kind: %s", kind)
        except Exception:
            pass
        try:
            local_models = getattr(self, '_local_models', []) or []
            cloud_models = getattr(self, '_cloud_models', []) or []
            if kind is None:
                rows = build_entries(local_models, cloud_models)
            elif kind == "local":
                rows = build_entries(local_models=local_models, cloud_models=[])
            else:  # kind == "cloud"
                rows = build_entries(local_models=[], cloud_models=cloud_models)
            self._apply_catalogue(rows)
        except Exception as e:
            try:
                from thecore.debug_log import logger
                logger.exception("Error in _rebuild_catalogue: %s", e)
            except Exception:
                pass
            try:
                self._apply_catalogue([])
            except Exception:
                pass

    def _select_first_of(self, kind: str) -> None:
        """Pick the first model of a family (local or cloud)."""
        try:
            if self._composer is None:
                return
            if kind == "local":
                for entry in getattr(self, '_local_models', []) or []:
                    try:
                        self._composer.select_model(
                            ModelEntry(kind="local", model_id=getattr(entry, 'name', ''), label=getattr(entry, 'name', ''))
                        )
                        return
                    except Exception:
                        continue
            elif kind == "cloud":
                for model in getattr(self, '_cloud_models', []) or []:
                    try:
                        self._composer.select_model(
                            ModelEntry(
                                kind="cloud",
                                model_id=getattr(model, 'id', ''),
                                provider_id=getattr(model, 'provider_id', ''),
                                provider_name=getattr(model, 'provider_name', ''),
                                free=getattr(model, 'free', False),
                            )
                        )
                        return
                    except Exception:
                        continue
        except Exception:
            pass

    def _refresh_models(self) -> None:
        """Re-read the local Ollama models and show them in the dropdown."""
        if self._use_opencode or self._use_cloud:
            return
        if self._model_probe is not None and self._model_probe.isRunning():
            return
        client = self._client
        self._model_probe = _BgCall(lambda: client.list_models(timeout=1.0), self)
        self._model_probe.done.connect(self._apply_model_list)
        self._model_probe.start()

    def _apply_model_list(self, result) -> None:
        if isinstance(result, Exception):
            self._set_status("OLLAMA: OFFLINE", "offline")
            return
        self._set_status("OLLAMA: ONLINE", "online")
        self._local_models = list(result)
        self._rebuild_catalogue(kind="local")
        if not self._local_models:
            self._set_status("OLLAMA: NO MODELS", "offline")
        active = self._current_local_model()
        if active and active != self._checked_thinking_model:
            self._queue_capabilities(active)

    def _current_local_model(self) -> str:
        """The name of the local model that is picked (empty when it is a cloud one)."""
        entry = self._selected_entry
        if entry is not None and entry.kind == "local":
            return entry.model_id
        return ""

    def _on_model_selected(self, entry) -> None:
        """A model was picked in the dropdown."""
        try:
            from thecore.debug_log import logger
            logger.debug("Model selected: %s", entry)
        except Exception:
            pass
        try:
            if entry is None:
                return
            self._selected_entry = entry

            if getattr(entry, 'kind', None) == "local":
                self._use_cloud = False
                self._use_opencode = False
                self._queue_capabilities(getattr(entry, "model_id", "") or "")
                self._set_status(f"OLLAMA: {entry.model_id}", "online")
            elif getattr(entry, 'kind', None) == "cloud":
                self._use_cloud = True
                self._use_opencode = False
                self._cloud_provider_id = getattr(entry, "provider_id", "")
                self._set_status(
                    f"CLOUD: {getattr(entry, 'provider_name', '').upper()}: {entry.model_id}", "online"
                )
                caps = cloud_capabilities(getattr(entry, "model_id", "") or "")
                self._model_supports_tools = "tools" in caps
                self._model_supports_vision = "vision" in caps
                self._model_supports_thinking = "thinking" in caps
                if self._think_btn is not None:
                    self._think_btn.setVisible(self._model_supports_thinking)
                    self._think_btn.setText(
                        "REASONING ON" if self._thinking_enabled else "REASONING OFF"
                    )
                self._update_capability_label()
            else:
                return

            self._sync_provider_combo()
            try:
                # A cloud pick must keep the third list on that provider.
                # Rebuilding the whole cloud catalogue mixed every provider in.
                if not self._use_cloud:
                    self._rebuild_catalogue(kind="local")
            except Exception as e:
                try:
                    from thecore.debug_log import logger
                    logger.exception("Error rebuilding catalogue: %s", e)
                except Exception:
                    pass
            try:
                self._update_load_button_visibility()
            except Exception as e:
                try:
                    from thecore.debug_log import logger
                    logger.exception("Error updating load button: %s", e)
                except Exception:
                    pass
            self._update_model_indicator()
        except Exception as e:
            try:
                from thecore.debug_log import logger
                logger.exception("Error in _on_model_selected: %s", e)
            except Exception:
                pass
            # Avoid crashing the UI on unexpected selection errors
            pass

    def _on_think_toggled(self) -> None:
        """Toggle whether the model's chain-of-thought is requested/shown."""
        self._thinking_enabled = bool(self._think_btn and self._think_btn.isChecked())
        if self._think_btn is not None:
            self._think_btn.setText("REASONING ON" if self._thinking_enabled else "REASONING OFF")

    def _queue_capabilities(self, model_name: str) -> None:
        """Ask Ollama what a model can do, without blocking the window."""
        if not model_name or model_name == self._checked_thinking_model:
            return
        if self._caps_probe is not None and self._caps_probe.isRunning():
            self._caps_pending = model_name
            return
        self._caps_pending = ""
        self._checked_thinking_model = model_name
        client = self._client
        self._caps_probe = _BgCall(
            lambda: client.model_capabilities(model_name, timeout=1.0), self
        )
        self._caps_probe.done.connect(
            lambda caps, name=model_name: self._apply_capabilities(name, caps)
        )
        self._caps_probe.start()

    def _apply_capabilities(self, model_name: str, capabilities) -> None:
        pending = getattr(self, "_caps_pending", "")
        if pending and pending != model_name:
            self._caps_pending = ""
            self._checked_thinking_model = ""
            self._queue_capabilities(pending)
            return
        if model_name != self._checked_thinking_model:
            return
        if isinstance(capabilities, Exception):
            capabilities = []
        self._model_supports_tools = "tools" in capabilities
        self._model_supports_vision = "vision" in capabilities
        self._model_supports_thinking = "thinking" in capabilities
        if self._think_btn is not None:
            self._think_btn.setVisible(self._model_supports_thinking and not self._use_opencode)
            self._think_btn.setText(
                "REASONING ON" if self._thinking_enabled else "REASONING OFF"
            )
        self._update_capability_label()

    def _detect_thinking_support(self, model_name: str) -> bool:
        """Ask Ollama whether the given model exposes chain-of-thought."""
        supported = False
        if model_name:
            try:
                supported = self._client.supports_thinking(model_name)
            except Exception:  # noqa: BLE001
                supported = False
        self._model_supports_thinking = supported
        if self._think_btn is not None:
            self._think_btn.setVisible(supported and not self._use_opencode)
            self._think_btn.setText("REASONING ON" if self._thinking_enabled else "REASONING OFF")
        return supported

    def _detect_capabilities(self, model_name: str) -> None:
        """Find out what the selected model can do: tools, vision, reasoning.

        Ollama reports this per model, so the UI can show it and the chat can
        offer exactly the right features.
        """
        if not model_name:
            self._model_supports_tools = False
            self._model_supports_vision = False
            self._update_capability_label()
            return
        try:
            capabilities = self._client.model_capabilities(model_name)
        except Exception:  # noqa: BLE001
            capabilities = []
        self._model_supports_tools = "tools" in capabilities
        self._model_supports_vision = "vision" in capabilities
        if "thinking" in capabilities:
            self._model_supports_thinking = True
        self._update_capability_label()

    def _update_capability_label(self) -> None:
        """Show the capabilities of the selected model as icons."""
        self._capability_icons.set_capabilities(
            tools=self._model_supports_tools,
            vision=self._model_supports_vision,
            reasoning=self._model_supports_thinking,
        )
        if self._attach_btn is not None:
            # Only a vision model can look at an image.
            self._attach_btn.setEnabled(self._model_supports_vision)
            self._attach_btn.setToolTip(
                "Attach an image"
                if self._model_supports_vision
                else "This model has no vision — pick one that has"
            )

    def _on_load_clicked(self) -> None:
        if self._use_opencode:
            if self._opencode_loaded:
                self._stop_opencode_console()
            else:
                self._start_opencode_console()
        elif self._use_cloud:
            # There is nothing to load — just ask the provider for its models.
            self._refresh_cloud_models()
        else:
            if self._ollama_model_loaded:
                self._unload_ollama_model()
            else:
                name = self._current_local_model()
                if name:
                    self._load_model_and_track(name)

    # ------------------------------------------------------------------ Ollama model load + VRAM/RAM

    def _load_model_and_track(self, model_name: str) -> None:
        """Force Ollama to load the model and measure VRAM/RAM delta."""
        size_gb = 0.0
        for model in self._local_models:
            if getattr(model, "name", "") == model_name:
                size_gb = float(getattr(model, "size_gb", 0.0) or 0.0)
                break

        # Record load start time and start elapsed timer
        import time as _time
        self._ollama_load_start = _time.monotonic()
        self._ollama_model_loaded = False
        if self._load_timer is not None:
            self._load_timer.start(500)

        # Start loading spinner so user sees something happening
        self._start_spinner()
        self._set_status(f"OLLAMA: LOADING {model_name}…", "loading")

        def load_call() -> None:
            # A minimal generate forces Ollama to load the model into VRAM/RAM
            try:
                self._client.generate(model=model_name, prompt=" ", stream=False)
            except Exception:
                pass

        # The measurement blocks for as long as Ollama takes to pull the
        # weights in, so it runs on a worker thread — otherwise the whole
        # window (and the spinner) would freeze.
        self._cancel_load_worker()
        self._load_worker = ModelLoadWorker(
            self._tracker, model_name, size_gb, load_call, self
        )
        self._load_worker.loaded.connect(self._on_model_load_finished)
        self._load_worker.failed.connect(self._on_model_load_failed)
        self._load_worker.finished.connect(self._on_load_worker_finished)
        self._load_worker.start()

    def _on_model_load_finished(self, delta) -> None:
        """The model finished loading (worker thread result)."""
        used = delta.gpu_vram_delta_mb
        ram = delta.system_ram_delta_mb
        vram_total = delta.gpu_vram_total_mb
        size_gb = delta.model_size_gb
        model_name = delta.model_name

        if delta.gpu_available:
            if self._mem_label is not None:
                self._mem_label.setText(
                    f"GPU VRAM: {used:+.0f} MB / {vram_total:.0f} MB  ·  "
                    f"PC RAM Δ: {ram:+.0f} MB  ·  model {size_gb:.2f} GB"
                )
        else:
            if self._mem_label is not None:
                self._mem_label.setText(
                    f"GPU VRAM: N/A  ·  PC RAM Δ: {ram:+.0f} MB  ·  model {size_gb:.2f} GB"
                )

        self._set_status(f"OLLAMA: {model_name} (LOADED)", "online")
        # Mark model as loaded and update button
        self._ollama_model_loaded = True
        self._ollama_loaded_model = model_name
        if self._load_btn is not None:
            self._load_btn.setText("UNLOAD")
            self._load_btn.setProperty("loaded", "true")
            self._load_btn.style().unpolish(self._load_btn)
            self._load_btn.style().polish(self._load_btn)

    def _on_model_load_failed(self, reason: str) -> None:
        """The model could not be loaded."""
        self._set_status("OLLAMA: LOAD FAILED", "offline")
        if self._mem_label is not None:
            self._mem_label.setText(f"GPU/PC MEM: load error — {reason}")
        self._ollama_model_loaded = False
        self._ollama_loaded_model = None

    def _on_load_worker_finished(self) -> None:
        """The worker thread ended — stop the spinner and show the time."""
        import time as _time

        self._stop_spinner()
        if self._load_timer is not None:
            self._load_timer.stop()
        if self._ollama_load_start is not None:
            elapsed = _time.monotonic() - self._ollama_load_start
            if self._ollama_model_loaded:
                model_name = self._ollama_loaded_model
                self._set_status(
                    f"OLLAMA: {model_name} (LOADED in {elapsed:.1f}s)", "online"
                )
        self._load_worker = None

    def _tick_load_timer(self) -> None:
        """Update elapsed-time display while a model is loading."""
        import time as _time
        if self._ollama_load_start is None:
            return
        elapsed = _time.monotonic() - self._ollama_load_start
        model_name = self._ollama_loaded_model or self._current_local_model()
        self._set_status(
            f"OLLAMA: LOADING {model_name}… ({elapsed:.1f}s)", "loading"
        )
        # Show the elapsed time next to the spinning dial.
        if self._load_spinner is not None:
            self._load_spinner.set_caption(f"LOADING {elapsed:.1f}s")

    def _unload_ollama_model(self) -> None:
        """Unload the currently loaded Ollama model and reset UI state."""
        # Cancel any in-flight request
        if self._thread is not None:
            self._thread.worker.cancel()
            self._thread = None

        # Abandon a running load as well.
        self._cancel_load_worker()

        self._ollama_model_loaded = False
        self._ollama_loaded_model = None
        self._ollama_load_start = None
        if self._load_timer is not None:
            self._load_timer.stop()
        self._stop_spinner()

        self._set_status("OLLAMA: ONLINE (model unloaded)", "online")
        if self._mem_label is not None:
            self._mem_label.setText("GPU/PC MEM: —")
        if self._load_btn is not None:
            self._load_btn.setText("LOAD MODEL")
            self._load_btn.setEnabled(True)

    def _cancel_load_worker(self) -> None:
        """Stop and forget a running model-load worker."""
        worker = self._load_worker
        self._load_worker = None
        if worker is None:
            return
        try:
            worker.loaded.disconnect()
            worker.failed.disconnect()
        except (RuntimeError, TypeError):
            pass
        worker.requestInterruption()
        worker.wait(2000)

    def _check_backend_health(self) -> None:
        """Keep the OLLAMA lamp truthful, also while OpenCode is the provider.

        While Ollama is the active provider the lamp is driven by the regular
        model refresh; in OpenCode mode nothing else would update it.
        """
        if not self._use_opencode:
            return
        if self._health_probe is not None and self._health_probe.isRunning():
            return
        client = self._client
        self._health_probe = _BgCall(lambda: client.list_models(timeout=1.0), self)
        self._health_probe.done.connect(self._apply_health)
        self._health_probe.start()

    def _apply_health(self, result) -> None:
        if isinstance(result, Exception):
            self._set_lamp("offline", "OLLAMA: OFFLINE")
            return
        self._set_lamp("online", f"OLLAMA: ONLINE ({len(result)} models)")

    def _refresh_memory(self) -> None:
        """Sample the memory that TheCore and Ollama use (not the whole PC)."""
        if self._ollama_loading:
            return
        if self._mem_probe is not None and self._mem_probe.isRunning():
            return
        collector = self._ai_memory
        self._mem_probe = _BgCall(collector.sample, self)
        self._mem_probe.done.connect(self._apply_memory)
        self._mem_probe.start()

    def _apply_memory(self, snap) -> None:
        if isinstance(snap, Exception):
            return
        started = time.monotonic()
        try:
            if self._mem_gauge is not None:
                if snap.gpu_available:
                    self._mem_gauge.set_gpu(
                        snap.total_vram_mb,
                        snap.vram_capacity_mb,
                        snap.vram_percent,
                    )
                else:
                    self._mem_gauge.set_gpu_unavailable()
                self._mem_gauge.set_ram(
                    snap.total_ram_gb,
                    snap.ram_capacity_gb,
                    snap.ram_percent,
                )
            if self._mem_label is not None:
                self._mem_label.setText(
                    f"CORE+OLLAMA  ·  VRAM {snap.total_vram_mb:.0f} MB"
                    f"  ·  RAM {snap.total_ram_gb:.2f} GB"
                    f"  (ollama {snap.ollama_ram_gb:.2f} GB)"
                )
            log_timing("memory sample", started)
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ OpenCode embedded console

    def _console_cwd(self) -> str:
        """Working directory for the OpenCode console (project path or default)."""
        if self._current_project_id is not None:
            project = self._database.get_project(self._current_project_id)
            if project is not None:
                workspace = self._database.get_workspace(project.workspace_id)
                if workspace is not None and workspace.path:
                    return workspace.path
        return str(Path(__file__).resolve().parents[3])

    def _start_opencode_console(self) -> None:
        """Start ``opencode serve`` and show the genuine OpenCode console."""
        if not self._opencode.is_available():
            self._set_console_status("OPENCODE: NOT FOUND", "offline")
            return

        # Show loading state while the server comes up.
        self._set_console_status("OPENCODE: STARTING…", "loading")
        if self._load_btn is not None:
            self._load_btn.setEnabled(False)

        console = self._console_frame
        if console is None:
            return

        # The console widget is created once and reused across LOAD/UNLOAD
        # cycles, and its signals are connected once at build time — so there
        # is nothing to reconnect here.
        self._opencode_console = console
        cwd = self._console_cwd()
        logger.info("starting the OpenCode console in %s", cwd)
        if not console.start(cwd):
            if self._load_btn is not None:
                self._load_btn.setEnabled(True)
            self._set_console_status("OPENCODE: START FAILED", "offline")
            self._opencode_console = None
            return

        # Loaded state is finalized in _on_opencode_started once the
        # server actually answers (start is non-blocking).

    def _on_opencode_started(self) -> None:
        """The real OpenCode UI is now loaded in the embedded view."""
        self._opencode_loaded = True
        self._opencode_load_failed = False
        if self._load_btn is not None:
            self._load_btn.setText("UNLOAD OPENCODE")
            self._load_btn.setProperty("loaded", "true")
            self._load_btn.setEnabled(True)
            self._load_btn.style().unpolish(self._load_btn)
            self._load_btn.style().polish(self._load_btn)

        cwd = self._console_cwd()
        self._set_console_status(f"OPENCODE: READY ({cwd})", "online")
        self._set_console_visible(True)

    def _on_opencode_status(self, text: str) -> None:
        """Short status line from the OpenCode server."""
        self._set_console_status(text, "online")

    def _on_opencode_load_failed(self, reason: str) -> None:
        """Keep the console visible so the user sees the startup error."""
        self._opencode_load_failed = True
        self._opencode_loaded = False
        self._opencode_console = None
        if self._load_btn is not None:
            self._load_btn.setText("LOAD OPENCODE")
            self._load_btn.setProperty("loaded", "false")
            self._load_btn.setEnabled(True)
            self._load_btn.style().unpolish(self._load_btn)
            self._load_btn.style().polish(self._load_btn)
        self._set_console_status(f"OPENCODE: START FAILED — {reason}", "offline")
        self._set_console_visible(True)

    def _stop_opencode_console(self) -> None:
        """Shut the OpenCode server down and leave the placeholder visible."""
        console = self._opencode_console
        self._opencode_console = None
        self._opencode_loaded = False
        if console is not None:
            console.stop()

        if self._load_btn is not None:
            self._load_btn.setText("LOAD OPENCODE")
            self._load_btn.setProperty("loaded", "false")
            self._load_btn.setEnabled(True)
            self._load_btn.style().unpolish(self._load_btn)
            self._load_btn.style().polish(self._load_btn)

        self._set_console_status("OPENCODE: CONSOLE NOT LOADED", "offline")
        self._set_console_visible(self._use_opencode)

    def _set_console_visible(self, visible: bool) -> None:
        if self._console_frame is None or self._input_frame is None:
            return
        # OpenCode takes the main viewport. The chat transcript is hidden
        # while it is up, and the composer stays at the bottom.
        self._console_frame.setVisible(visible)
        if self._scroll_area is not None:
            self._scroll_area.setVisible(not visible)
        self._composer.set_input_visible(not self._use_opencode)

    def _fill_cloud_provider_combo(self) -> None:
        """List every cloud provider, not only the one that already has a key."""
        providers = [(p.id, p.name) for p in PROVIDERS]
        self._composer.set_cloud_providers(providers)
        chosen = self._composer.selected_cloud_provider()
        if chosen:
            self._cloud_provider_id = chosen

    def _ensure_runtimes(self) -> None:
        """Show install buttons. Startup only checks; it does not install."""
        missing_ollama = not ollama_installed()
        missing_opencode = not opencode_installed()
        self._composer.set_install_buttons(missing_ollama, missing_opencode)

    def _install_runtime(self, kind: str) -> None:
        if self._runtime_install is not None and self._runtime_install.isRunning():
            self._console_line("An install is already running")
            return
        self._list_log = None
        worker = RuntimeInstall(kind, self)
        worker.log.connect(self._console_line)
        worker.finished_with.connect(lambda _message: self._ensure_runtimes_buttons())
        self._runtime_install = worker
        worker.start()

    def _ensure_runtimes_buttons(self) -> None:
        self._composer.set_install_buttons(not ollama_installed(), not opencode_installed())

    def _console_line(self, text: str) -> None:
        """Show a refresh or ping line in the chat, not in a separate panel."""
        if self._list_log is None:
            self._add_message("assistant", text)
            self._list_log = self._last_message_widget()
        else:
            self._list_log.set_content(self._list_log.content + "\n" + text)
        self._scroll_to_bottom()

    def _on_refresh_list(self) -> None:
        """Load the provider's live model list and print each step."""
        client = self._cloud_client()
        if client is None:
            self._console_line("REFRESH  no API key for this provider")
            return
        if self._list_thread is not None and self._list_thread.isRunning():
            self._console_line("REFRESH  already running")
            return
        self._list_log = None
        self._composer.set_list_buttons_enabled(False)
        worker = CloudListWorker(client)
        thread = CloudListThread(worker, self)
        worker.log.connect(self._console_line)
        worker.models.connect(self._on_live_models)
        worker.failed.connect(lambda _message: self._composer.set_list_buttons_enabled(True))
        thread.finished.connect(lambda: self._composer.set_list_buttons_enabled(True))
        self._list_thread = thread
        thread.start()

    def _on_live_models(self, models: list) -> None:
        provider_id = self._cloud_provider_id
        self._cloud_models = [
            model
            for model in self._cloud_models
            if getattr(model, "provider_id", "") != provider_id
        ]
        self._live_providers.add(provider_id)
        self._cloud_models.extend(models)
        self._show_models_for_cloud_provider()

    def _on_ping_list(self) -> None:
        """Drop models that are paid or do not answer a ping."""
        client = self._cloud_client()
        if client is None:
            self._console_line("PING  no API key for this provider")
            return
        if self._ping_thread is not None and self._ping_thread.isRunning():
            self._console_line("PING  already running")
            return
        provider_id = self._cloud_provider_id
        models = [
            model
            for model in self._cloud_models
            if getattr(model, "provider_id", "") == provider_id
        ]
        if not models:
            provider = PROVIDERS_BY_ID.get(provider_id)
            models = catalogue_models(provider) if provider is not None else []
        if not models:
            self._console_line("PING  the list is empty — press REFRESH LIST first")
            return
        self._list_log = None
        self._composer.set_list_buttons_enabled(False)
        worker = CloudPingWorker(client, models)
        thread = CloudPingThread(worker, self)
        worker.log.connect(self._console_line)
        worker.kept.connect(self._on_ping_kept)
        thread.finished.connect(lambda: self._composer.set_list_buttons_enabled(True))
        self._ping_thread = thread
        thread.start()

    def _on_ping_kept(self, models: list) -> None:
        provider_id = self._cloud_provider_id
        self._cloud_models = [
            model
            for model in self._cloud_models
            if getattr(model, "provider_id", "") != provider_id
        ]
        self._live_providers.add(provider_id)
        self._cloud_models.extend(models)
        self._show_models_for_cloud_provider()

    def _on_cloud_provider_picked(self, provider_id: str) -> None:
        self._cloud_provider_id = provider_id
        self._show_models_for_cloud_provider()

    def _show_models_for_cloud_provider(self) -> None:
        """Fill the model dropdown with only the selected cloud provider."""
        provider_id = self._composer.selected_cloud_provider()
        self._cloud_provider_id = provider_id
        provider = PROVIDERS_BY_ID.get(provider_id)
        models = [
            model
            for model in (self._cloud_models or [])
            if getattr(model, "provider_id", "") == provider_id
        ]
        if (
            not models
            and provider is not None
            and provider_id not in self._live_providers
        ):
            models = catalogue_models(provider)
        if not models and provider_id and not load_key(provider_id):
            name = provider.name if provider is not None else provider_id
            self._apply_catalogue([])
            self._set_status(f"CLOUD: ADD A {name.upper()} KEY IN SETTINGS", "offline")
            return
        rows = build_entries(local_models=[], cloud_models=models)
        current = self._composer.selected_model()
        self._apply_catalogue(rows)
        same = (
            current is not None
            and getattr(current, "kind", "") == "cloud"
            and getattr(current, "provider_id", "") == provider_id
        )
        if not same:
            self._select_first_of("cloud")

    def _flush_pending_assistant(self) -> None:
        """Kept for API compatibility — the web console persists nothing here."""

    # ------------------------------------------------------------------ cloud provider

    def _cloud_client(self) -> Optional[CloudClient]:
        """A client for the selected cloud provider (None when not set up)."""
        provider = PROVIDERS_BY_ID.get(self._cloud_provider_id)
        if provider is None:
            return None
        key = load_key(provider.id)
        if not key:
            return None
        if provider.id == "custom":
            base_url = load_base_url()
            if not base_url:
                return None
            provider = replace(provider, base_url=base_url)
        return CloudClient(provider=provider, api_key=key)

    def _refresh_cloud_models(self) -> None:
        """Ask every configured cloud provider which models it offers.

        The models of *all* providers with a key are gathered and shown in one
        list, grouped per provider and labelled ``● FREE`` / ``○ PAID``.  The
        network call runs on a worker thread so the window never freezes.
        """
        if not self._use_cloud or self._model_combo is None:
            return

        from thecore.ai.cloud_client import configured_providers

        providers = configured_providers()
        if not providers:
            self._cloud_models = []
            self._apply_catalogue([])
            self._set_status("CLOUD: ADD AN API KEY IN THE SETTINGS", "offline")
            return

        self._set_status(f"CLOUD: {len(providers)} PROVIDERS — LOADING", "loading")

        if self._catalogue_thread is not None and self._catalogue_thread.isRunning():
            return

        self._cloud_models = []
        worker = CloudCatalogueWorker()
        thread = CloudCatalogueThread(worker, self)
        worker.provider_models.connect(self._on_provider_models)
        worker.finished.connect(self._on_catalogue_finished)
        self._catalogue_thread = thread
        thread.start()

    def _on_provider_models(self, _provider_id: str, models: list) -> None:
        """One provider answered with its model list."""
        self._cloud_models.extend(models)
        self._show_models_for_cloud_provider()

    def _on_catalogue_finished(self) -> None:
        """Every provider has answered — sort the list and show it."""
        self._show_models_for_cloud_provider()
        if not self._cloud_models:
            self._set_status("CLOUD: NO MODELS", "offline")
            return
        free = sum(1 for m in self._cloud_models if m.free)
        self._set_status(
            f"CLOUD: {len(self._cloud_models)} MODELS ({free} FREE)", "online"
        )

    def _send_cloud(self, text: str) -> None:
        """Stream a reply from the cloud provider of the picked model."""
        entry = self._selected_entry
        if entry is None or entry.kind != "cloud":
            self._set_status("CLOUD: NO MODEL PICKED", "offline")
            self._composer.set_running(False)
            return

        client = self._cloud_client()
        model_id = entry.model_id
        if client is None or not model_id:
            self._set_status("CLOUD: NO PROVIDER OR MODEL", "offline")
            self._composer.set_running(False)
            return

        messages: list[dict] = []
        for i in range(self._message_layout.count() - 1):  # skip trailing stretch
            item = self._message_layout.itemAt(i)
            widget = item.widget()
            if isinstance(widget, MessageWidget):
                messages.append(
                    {"role": widget.role, "content": widget.content}
                )
        messages.append({"role": "user", "content": text})

        self._start_indicator(entry.provider_name or "Cloud")
        self._accumulated = ""

        worker = CloudWorker(client, model_id, messages)
        thread = CloudThread(worker, self)
        worker.chunk_received.connect(self._on_chunk)
        worker.connected.connect(self._on_connected)
        worker.finished.connect(self._on_finished)
        worker.error.connect(self._on_error)
        thread.finished.connect(self._on_thread_finished)
        self._thread = thread
        thread.start()

    # ------------------------------------------------------------------ settings

    def on_settings_cloud_changed(self, provider_id: str) -> None:
        """A cloud key was saved or removed in the settings page."""
        if self._use_cloud:
            self._refresh_cloud_models()
        self._update_model_indicator()

    def _update_model_indicator(self) -> None:
        """Show the current provider + model in the bottom-right label."""
        if self._model_indicator is None:
            return
        entry = self._selected_entry
        if self._use_opencode:
            self._model_indicator.setText("OPENCODE")
            self._model_indicator.setProperty("provider", "opencode")
        elif entry is not None and entry.kind == "cloud":
            tier = "  ● FREE" if entry.free else "  ○ PAID"
            self._model_indicator.setText(
                f"CLOUD: {entry.provider_name}:{entry.model_id}{tier}"
            )
            self._model_indicator.setProperty("provider", "cloud")
        else:
            name = entry.model_id if entry is not None else ""
            self._model_indicator.setText(f"OLLAMA: {name}" if name else "OLLAMA: —")
            self._model_indicator.setProperty("provider", "ollama")
        self._model_indicator.style().unpolish(self._model_indicator)
        self._model_indicator.style().polish(self._model_indicator)

    def _update_load_button_visibility(self) -> None:
        """Update load button visibility based on provider type."""
        if self._load_btn is None:
            return
        entry = self._selected_entry
        if self._use_opencode:
            self._load_btn.setText("UNLOAD OPENCODE" if self._opencode_loaded else "LOAD OPENCODE")
            self._load_btn.setEnabled(self._opencode.is_available())
            self._load_btn.show()
            return
        if entry is not None and entry.kind == "cloud":
            self._load_btn.setText("REFRESH MODELS")
            self._load_btn.setEnabled(True)
            self._load_btn.show()
            return
        if entry is not None and entry.kind == "local":
            if self._ollama_model_loaded:
                self._load_btn.setText("UNLOAD")
                self._load_btn.setProperty("loaded", "true")
            else:
                self._load_btn.setText("LOAD MODEL")
                self._load_btn.setProperty("loaded", "false")
            self._load_btn.setEnabled(True)
            self._load_btn.show()
            self._load_btn.style().unpolish(self._load_btn)
            self._load_btn.style().polish(self._load_btn)
            return
        self._load_btn.hide()

    # ------------------------------------------------------------------ tools

    def _tool_registry(self) -> Optional[ToolRegistry]:
        """The tools for the current project folder (None when unavailable)."""
        root = self._project_root()
        if not root:
            return None
        if self._tool_registry_obj is not None and self._tool_root == root:
            return self._tool_registry_obj
        try:
            self._tool_registry_obj = ToolRegistry(root)
            self._tool_root = root
        except Exception:  # noqa: BLE001
            return None
        return self._tool_registry_obj

    def _project_root(self) -> str:
        """The folder the model may work in: the workspace of the project."""
        try:
            if self._current_project_id is not None:
                workspace = self._database.get_workspace_for_project(
                    self._current_project_id
                )
                if workspace is not None and workspace.path:
                    return workspace.path
        except Exception:  # noqa: BLE001
            pass
        return str(Path(__file__).resolve().parents[3])

    def _on_tool_called(self, name: str, arguments: object, display: str) -> None:
        """Show a tool call in the chat."""
        label = display or name
        logger.info("tool call: %s %s", name, arguments)
        self._add_tool_line(f"⚙ {label}")
        self._scroll_to_bottom()

    def _on_content_replaced(self, text: str) -> None:
        """The answer text changed (tool-call JSON was removed from it)."""
        last = self._last_message_widget()
        if last is not None and last.role == "assistant":
            last.set_content(text)

    # ------------------------------------------------------------------ images

    def _on_attach_image(self) -> None:
        """Pick an image to send to a vision model."""
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Attach an image",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)",
        )
        if not path:
            return
        try:
            data = Path(path).read_bytes()
        except OSError as exc:
            QMessageBox.warning(self, "Image", f"Could not read the image:\n{exc}")
            return
        if len(data) > 8 * 1024 * 1024:
            QMessageBox.warning(self, "Image", "The image is larger than 8 MB.")
            return
        encoded = base64.b64encode(data).decode("ascii")
        self._pending_images.append(encoded)
        self._pending_image_paths.append(path)
        self._refresh_image_strip()

    def _clear_images(self) -> None:
        self._pending_images.clear()
        self._pending_image_paths.clear()
        self._refresh_image_strip()

    def _refresh_image_strip(self) -> None:
        """Show the thumbnails of the images waiting to be sent."""
        strip = self._image_strip
        if strip is None:
            return
        for child in strip.findChildren(QWidget):
            child.setParent(None)
            child.deleteLater()
        if not self._pending_image_paths:
            strip.hide()
            return
        strip.show()
        for path in self._pending_image_paths:
            label = QLabel(Path(path).name)
            label.setObjectName("chatImageChip")
            label.setToolTip(path)
            strip.addWidget(label)
        strip.addStretch(1)

    # ------------------------------------------------------------------ menu actions

    def undo(self) -> None:
        self._composer.input.undo()

    def redo(self) -> None:
        self._composer.input.redo()

    def cut(self) -> None:
        self._composer.input.cut()

    def copy(self) -> None:
        self._composer.input.copy()

    def paste(self) -> None:
        self._composer.input.paste()

    def select_all(self) -> None:
        self._composer.input.selectAll()

    def reload_models(self) -> None:
        """Re-read the model list (and the cloud providers)."""
        self._refresh_models()
        if self._use_cloud:
            self._refresh_cloud_models()

    def zoom(self, direction: int) -> None:
        """Change the text size: 1 = bigger, -1 = smaller, 0 = reset."""
        base = self._font_size
        if direction == 0:
            new_size = 14
        else:
            new_size = max(10, min(28, base + direction * 2))
        self._font_size = new_size
        app_font = self.font()
        app_font.setPointSize(new_size)
        self.setFont(app_font)
        self._composer.set_font_size(new_size)

    # ------------------------------------------------------------------ conversation lifecycle

    def start_new_conversation(self, project_id: int) -> None:
        self._current_project_id = project_id
        ws = self._database.get_workspace_for_project(project_id)
        self._current_workspace_id = ws.id if ws is not None else None
        self._current_conversation_id = None
        self._clear_messages()
        model = self._current_model_name()
        conv = self._database.create_conversation(project_id, "New Conversation", model)
        self._current_conversation_id = conv.id
        self.conversation_created.emit(conv.id)

    def load_conversation(self, conversation_id: int) -> None:
        self._current_conversation_id = conversation_id
        conv = None
        for c in self._database.list_conversations(self._current_project_id or 0):
            if c.id == conversation_id:
                conv = c
                break
        if conv is None:
            return
        self._current_project_id = conv.project_id
        ws = self._database.get_workspace_for_project(conv.project_id)
        self._current_workspace_id = ws.id if ws is not None else None
        self._clear_messages()
        messages = self._database.get_messages(conversation_id)
        for m in messages:
            self._add_message(m.role, m.content, temporary=False)

    def _current_model_name(self) -> str:
        """The name of the active model, as shown in the chat header."""
        if self._use_opencode:
            return "opencode"
        entry = self._selected_entry
        if entry is None:
            return ""
        if entry.kind == "cloud":
            return f"{entry.provider_name}:{entry.model_id}"
        return entry.model_id

    def _ensure_conversation(self, model: str) -> None:
        """Make sure there is a conversation to attach messages to."""
        if self._current_conversation_id is not None:
            return
        if self._current_project_id is None:
            # Auto-create a default workspace and project so sending works
            try:
                ws = self._database.create_workspace("Default", str(Path.cwd()))
            except Exception:
                # Workspace with this path may already exist — find it
                for existing in self._database.list_workspaces():
                    if existing.path == str(Path.cwd()):
                        ws = existing
                        break
                else:
                    raise
            pr = self._database.create_project(ws.id, "General")
            self._current_project_id = pr.id
            self._current_workspace_id = ws.id
        conv = self._database.create_conversation(
            self._current_project_id, "New Conversation", model
        )
        self._current_conversation_id = conv.id
        self.conversation_created.emit(conv.id)

    def _clear_messages(self) -> None:
        self._indicator = None
        while self._message_layout.count() > 1:  # keep the trailing stretch
            item = self._message_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    # ------------------------------------------------------------------ project / workspace creation

    def request_new_project(self, workspace_id: int) -> None:
        name, ok = QInputDialog.getText(
            self, "New Project", "Project name:"
        )
        if not ok or not name.strip():
            return
        desc, ok2 = QInputDialog.getText(
            self, "New Project", "Description (optional):"
        )
        self._database.create_project(workspace_id, name.strip(), desc if ok2 else "")
        self.new_project_created.emit()

    def request_new_workspace(self) -> None:
        name, ok = QInputDialog.getText(self, "New Workspace", "Workspace name:")
        if not ok or not name.strip():
            return
        default_path = str(Path(__file__).resolve().parents[3])
        path, ok2 = QInputDialog.getText(
            self, "New Workspace", "Workspace path:", text=default_path
        )
        if not ok2 or not path.strip():
            return
        self._database.create_workspace(name.strip(), path.strip())
        self.new_workspace_created.emit()

    # ------------------------------------------------------------------ send / receive

    def _name_conversation(self, question: str) -> None:
        """Give a new conversation its automatic name.

        "what is the color of a house mouse" becomes "Mouse" — the subject of
        the question, not a generic word like "New Conversation".
        """
        conversation_id = self._current_conversation_id
        if conversation_id is None:
            return
        title = title_from_question(question)
        if not title:
            return
        try:
            self._database.rename_conversation(conversation_id, title)
        except Exception:  # noqa: BLE001 — a failed rename must not break the chat
            return
        self.conversation_renamed.emit(conversation_id, title)

    def _on_send(self) -> None:
        try:
            from thecore.debug_log import logger
            logger.debug("SEND requested (thread=%r)", self._thread)
        except Exception:
            pass
        try:
            text = self._composer.text()
            try:
                from thecore.debug_log import logger
                logger.debug("SEND text=%r thread=%r model=%r use_opencode=%r use_cloud=%r selected=%r",
                             text, self._thread, self._current_model_name(),
                             getattr(self, '_use_opencode', False), getattr(self, '_use_cloud', False),
                             getattr(self, '_selected_entry', None))
            except Exception:
                pass
            if self._thread is not None and not self._thread.isRunning():
                self._thread = None
            if not text or self._thread is not None:
                return

            model = self._current_model_name()
            if not model:
                try:
                    from thecore.debug_log import logger
                    logger.warning("No model name, trying to use selected entry")
                except Exception:
                    pass
                entry = getattr(self, '_selected_entry', None)
                if entry is not None and getattr(entry, 'kind', None) == 'local':
                    model = getattr(entry, 'model_id', '')
                if not model:
                    QMessageBox.warning(
                        self, "No Model", "Please select or load a model first."
                    )
                    return

            try:
                self._ensure_conversation(model=model)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(
                    self, "Conversation Error", f"Failed to create conversation:\n{exc}"
                )
                return
            if self._current_conversation_id is None:
                return

            # A brand new conversation takes its name from the first question.
            is_first_question = (
                self._database.count_messages(self._current_conversation_id) == 0
            )

            try:
                self._add_message("user", text)
            except Exception as e:
                try:
                    from thecore.debug_log import logger
                    logger.exception("Error adding user message: %s", e)
                except Exception:
                    pass
            try:
                self._database.add_message(self._current_conversation_id, "user", text)
            except Exception as e:
                try:
                    from thecore.debug_log import logger
                    logger.exception("Error saving user message: %s", e)
                except Exception:
                    pass

            if is_first_question:
                try:
                    self._name_conversation(text)
                except Exception:
                    pass
            self._composer.clear()
            self._composer.set_running(True)

            if self._use_opencode:
                # Ollama-style send isn't used for OpenCode; use the console instead.
                self._composer.set_running(False)
            elif self._use_cloud:
                try:
                    self._send_cloud(text)
                except Exception as e:
                    try:
                        from thecore.debug_log import logger
                        logger.exception("Error in _send_cloud: %s", e)
                    except Exception:
                        pass
                    self._composer.set_running(False)
            else:
                try:
                    self._send_ollama(text)
                except Exception as e:
                    try:
                        from thecore.debug_log import logger
                        logger.exception("Error in _send_ollama: %s", e)
                    except Exception:
                        pass
                    self._composer.set_running(False)
        except Exception as e:
            try:
                from thecore.debug_log import logger
                logger.exception("Error in _on_send: %s", e)
            except Exception:
                pass
            self._composer.set_running(False)

    def _send_ollama(self, prompt: str) -> None:
        try:
            from thecore.debug_log import logger
            logger.debug("Starting _send_ollama")
        except Exception:
            pass
        try:
            model = self._current_local_model()
            try:
                from thecore.debug_log import logger
                logger.debug("Model from _current_local_model: %r", model)
            except Exception:
                pass
            if not model:
                entry = getattr(self, '_selected_entry', None)
                if entry is not None and getattr(entry, 'kind', None) == 'local':
                    model = getattr(entry, 'model_id', '')
                try:
                    from thecore.debug_log import logger
                    logger.debug("Model from selected entry: %r", model)
                except Exception:
                    pass
            if not model:
                self._composer.set_running(False)
                return

            messages: list[ChatMessage] = []
            for i in range(self._message_layout.count() - 1):  # skip trailing stretch
                try:
                    item = self._message_layout.itemAt(i)
                    if item is None:
                        continue
                    widget = item.widget()
                    if isinstance(widget, MessageWidget):
                        messages.append(ChatMessage(role=widget.role, content=widget.content))
                except Exception:
                    continue

            # Images attached to this message (vision models only).
            images = list(self._pending_images)
            self._pending_images.clear()
            messages.append(
                ChatMessage(role="user", content=prompt, images=images)
            )

            # Tools: only for models that advertise the capability.
            tools = None
            tool_runner = None
            registry = self._tool_registry()
            if registry is not None and getattr(self, '_model_supports_tools', False):
                try:
                    tools = registry.definitions()
                    tool_runner = registry.execute
                    messages.insert(
                        0, ChatMessage(role="system", content=_TOOL_SYSTEM_PROMPT)
                    )
                except Exception:
                    tools = None
                    tool_runner = None

            worker = OllamaWorker(
                client=self._client,
                model=model,
                messages=messages,
                stream=True,
                think=(
                    True
                    if (getattr(self, '_thinking_enabled', False) and getattr(self, '_model_supports_thinking', False))
                    else None
                ),
                tools=tools,
                tool_runner=tool_runner,
            )
            thread = OllamaThread(worker)
            self._thread = thread

            worker.chunk_received.connect(self._on_chunk)
            worker.thinking_received.connect(self._on_thinking)
            worker.connected.connect(self._on_connected)
            worker.stats_received.connect(self._on_stats)
            worker.tool_called.connect(self._on_tool_called)
            worker.content_replaced.connect(self._on_content_replaced)
            worker.finished.connect(self._on_finished)
            worker.error.connect(self._on_error)
            thread.finished.connect(self._on_thread_finished)

            # Show an inline status bubble so the user can see the AI working.
            self._start_indicator(model)

            thread.start()
            try:
                from thecore.debug_log import logger
                logger.debug("Started Ollama thread for model %s", model)
            except Exception:
                pass
        except Exception as e:
            try:
                from thecore.debug_log import logger
                logger.exception("Error in _send_ollama: %s", e)
            except Exception:
                pass
            self._composer.set_running(False)

    # ------------------------------------------------------------------ status indicator

    def _start_indicator(self, model: str) -> None:
        """Insert the @connecting / @reasoning / @generating bubble into the chat."""
        # Finalise a leftover indicator (should not happen — one turn at a time).
        if self._indicator is not None:
            self._indicator.finish()
            self._indicator = None
        indicator = ThinkingIndicator(model)
        idx = self._message_layout.count() - 1
        self._message_layout.insertWidget(idx, indicator)
        self._indicator = indicator
        self._scroll_to_bottom()

    def _remove_indicator(self) -> None:
        """Drop the active status bubble (used on errors)."""
        indicator = self._indicator
        self._indicator = None
        if indicator is None:
            return
        idx = self._message_layout.indexOf(indicator)
        if idx >= 0:
            self._message_layout.takeAt(idx)
        indicator.deleteLater()

    def _on_connected(self) -> None:
        indicator = self._indicator
        if indicator is None:
            return
        # Only promote a still-connecting indicator — a reasoning model that
        # already produced chain-of-thought stays in the @reasoning phase.
        if indicator.state == ThinkingIndicator.CONNECTING:
            indicator.set_state(ThinkingIndicator.GENERATING)

    def _on_thinking(self, text: str) -> None:
        if self._indicator is not None:
            self._indicator.add_reasoning(text)

    def _on_stats(self, stats: dict) -> None:
        indicator = self._indicator
        if indicator is None or not isinstance(stats, dict):
            return
        indicator.set_stats(
            int(stats.get("eval_count") or 0),
            int(stats.get("eval_duration") or 0),
        )
        indicator.total_duration_ns = int(stats.get("total_duration") or 0)
        indicator.load_duration_ns = int(stats.get("load_duration") or 0)

    def _setup_auto_scroll(self) -> None:
        """Keep the view on the newest message while the AI is writing.

        The scroll follows the content while it grows, but stops as soon as
        the user scrolls up to read something.
        """
        if self._scroll_area is None:
            return
        bar = self._scroll_area.verticalScrollBar()

        def on_range_changed(_minimum: int, _maximum: int) -> None:
            if self._auto_scroll:
                bar.setValue(bar.maximum())

        def on_value_changed(value: int) -> None:
            # At the bottom -> keep following; scrolled up -> stop.
            at_bottom = value >= bar.maximum() - 4
            if at_bottom != self._auto_scroll:
                self._auto_scroll = at_bottom

        try:
            bar.rangeChanged.disconnect()
        except (RuntimeError, TypeError):
            pass
        try:
            bar.valueChanged.disconnect()
        except (RuntimeError, TypeError):
            pass
        bar.rangeChanged.connect(on_range_changed)
        bar.valueChanged.connect(on_value_changed)
        self._auto_scroll = True

    def _scroll_to_bottom(self) -> None:
        """Scroll the message area to the bottom."""
        if self._scroll_area is None:
            return

        def _to_bottom() -> None:
            bar = self._scroll_area.verticalScrollBar()
            bar.setValue(bar.maximum())

        QTimer.singleShot(0, _to_bottom)
        # The content grows while the answer streams in, so the range changes
        # after the first call — follow it.
        QTimer.singleShot(60, _to_bottom)

    def _on_stop(self) -> None:
        if self._thread is not None:
            self._thread.worker.cancel()
        if self._indicator is not None:
            self._indicator.stop()
            self._indicator = None
        # The embedded OpenCode console owns its own requests; STOP only
        # affects an in-flight Ollama stream here.
        self._composer.set_running(False)

    def _on_chunk(self, delta: str) -> None:
        try:
            from thecore.debug_log import logger
            logger.debug("Chunk received: %r", delta[:50])
        except Exception:
            pass
        self._accumulated += delta
        if self._indicator is not None:
            self._indicator.add_content(delta)
        last = self._last_message_widget()
        if last is not None and last.role == "assistant":
            last.set_content(last.content + delta)
        else:
            self._add_message("assistant", delta, temporary=True)

    def _on_finished(self, full: str) -> None:
        self._composer.set_running(False)
        self._accumulated = ""
        last = self._last_message_widget()
        if last is not None and last.role == "assistant":
            last.set_temporary(False)
            # A long answer is folded so the chat stays readable; clicking it
            # shows the whole text.
            if len(full.splitlines()) > _COLLAPSED_LINES:
                last.set_collapsed(True)
        if self._indicator is not None:
            self._indicator.finish(
                total_duration_ns=self._indicator.total_duration_ns,
                load_duration_ns=self._indicator.load_duration_ns,
            )
            # Keep the finished summary in the chat as a record of the turn.
            self._indicator = None
        if self._current_conversation_id is not None:
            self._database.add_message(
                self._current_conversation_id, "assistant", full
            )
            self._database.update_conversation_timestamp(self._current_conversation_id)

    def _on_error(self, message: str) -> None:
        self._composer.set_running(False)
        self._accumulated = ""
        # Drop the status bubble — the error message below carries the details.
        self._remove_indicator()
        self._add_message("assistant", f"[ERROR] {message}", temporary=False)

    def _on_thread_finished(self) -> None:
        self._thread = None

    # ------------------------------------------------------------------ messages

    def _last_message_widget(self):
        for i in range(self._message_layout.count() - 1, -1, -1):
            item = self._message_layout.itemAt(i)
            widget = item.widget()
            if isinstance(widget, MessageWidget):
                return widget
        return None

    def _add_message(self, role: str, content: str, temporary: bool = False) -> None:
        try:
            idx = self._message_layout.count() - 1
            widget = MessageWidget(role, content, temporary=temporary)
            self._message_layout.insertWidget(idx, widget)
            if self._scroll_area is not None:
                try:
                    QTimer.singleShot(0, lambda: self._scroll_area.verticalScrollBar().setValue(
                        self._scroll_area.verticalScrollBar().maximum()
                    ))
                except Exception:
                    pass
        except Exception as e:
            try:
                from thecore.debug_log import logger
                logger.exception("Error adding message: %s", e)
            except Exception:
                pass

    def _add_tool_line(self, text: str) -> None:
        """Show a tool call as its own line in the chat."""
        idx = self._message_layout.count() - 1
        label = QLabel(text)
        label.setObjectName("chatToolLine")
        label.setWordWrap(True)
        self._message_layout.insertWidget(idx, label)

    def closeEvent(self, event) -> None:  # noqa: N802 — Qt API
        self._flush_pending_assistant()
        self._cancel_load_worker()
        if self._opencode_console is not None:
            self._opencode_console.stop()
            self._opencode_console = None
        if self._thread is not None:
            self._thread.worker.cancel()
        self._tracker.close()
        super().closeEvent(event)
