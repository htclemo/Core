"""The chat composer.

The composer is one rounded block that carries everything you need to start
a turn:

* a **provider** selector (the local model, a cloud model or OpenCode) and a
  **scope** selector (the workspace and project the turn belongs to),
* a big **multi-line** input with the hint "Plan, Build, / for skills,
  @ for context",
* an **attach** button, the **model** picker, a **microphone** button (Windows
  dictation) and a **speaker** button (reads the answer out loud),
* the "Multitask" **action chip** that pre-fills the input.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from thecore.ai.model_catalogue import CatalogueRow
from thecore.ai.ui.provider_icons import provider_icon

# The placeholder shown in the empty input.
PLACEHOLDER = "Plan, Build, / for skills, @ for context"

# The action chips under the input.
CHIPS: tuple[tuple[str, str, str], ...] = (
    ("Multitask", "", "multitask"),
)

# The suggestions are gone — the user removed them.  Only the action chips
# below remain.


def _model_tip(entry) -> str:
    """The hover text for one model."""
    if entry is None:
        return ""
    if getattr(entry, "kind", "") == "local":
        size = getattr(entry, "size_gb", 0.0) or 0.0
        extra = f"\n{size:.1f} GB on disk" if size else ""
        return f"{entry.model_id}\nLocal model, Ollama{extra}"
    tier = "Free tier" if getattr(entry, "free", False) else "Paid"
    provider = getattr(entry, "provider_name", "") or "Cloud"
    return f"{entry.model_id}\n{provider}\n{tier}"


class _ModelCombo(QComboBox):
    """The closed box stays compact. The open list shows the whole name."""

    def showPopup(self) -> None:
        view = self.view()
        view.setMouseTracking(True)
        view.setTextElideMode(Qt.TextElideMode.ElideNone)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        metrics = self.fontMetrics()
        widest = self.width()
        for index in range(self.count()):
            widest = max(widest, metrics.horizontalAdvance(self.itemText(index)) + 56)
        widest = min(widest, 920)
        view.setMinimumWidth(widest)
        super().showPopup()
        popup = view.window()
        if popup is not None and popup is not self:
            popup.resize(max(popup.width(), widest), popup.height())


class ChatComposer(QFrame):
    """The chat input area."""

    # The user pressed send.
    sendRequested = Signal()
    # Attach an image.
    attachRequested = Signal()
    # Start dictation.
    micRequested = Signal()
    # Read the last answer out loud.
    speakRequested = Signal()
    # Stop the current answer.
    stopRequested = Signal()
    # The provider changed: (provider id)
    providerChanged = Signal(str)
    # The cloud provider changed: (provider id)
    cloudProviderChanged = Signal(str)
    # A chip was used: (pre-filled text)
    prefillRequested = Signal(str)
    # A model was picked from the dropdown: (model entry)
    modelSelected = Signal(object)
    # Reload the live model list of the selected cloud provider.
    refreshListRequested = Signal()
    # Ping that list and drop whatever does not answer.
    pingListRequested = Signal()
    installOpencodeRequested = Signal()
    installOllamaRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("chatComposer")

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 6, 14, 10)
        root.setSpacing(8)

        # ---- the top row: provider + scope ----
        top = QHBoxLayout()
        top.setSpacing(8)

        self._provider_combo = QComboBox()
        self._provider_combo.setObjectName("composerCombo")
        self._provider_combo.addItem(provider_icon("local"), "Local-LLM", "ollama")
        self._provider_combo.addItem(provider_icon("cloud"), "Cloud LLM", "cloud")
        self._provider_combo.addItem(provider_icon("terminal"), "OpenCode", "opencode")
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        top.addWidget(self._provider_combo)

        self._cloud_provider_combo = QComboBox()
        self._cloud_provider_combo.setObjectName("composerCombo")
        self._cloud_provider_combo.setMinimumWidth(150)
        self._cloud_provider_combo.setToolTip("Cloud provider")
        self._cloud_provider_combo.currentIndexChanged.connect(self._on_cloud_provider_changed)
        self._cloud_provider_combo.hide()
        top.addWidget(self._cloud_provider_combo)

        self._model_combo = _ModelCombo()
        self._model_combo.setObjectName("composerModelCombo")
        self._model_combo.setMinimumWidth(200)
        self._model_combo.setToolTip("The model that answers")
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        top.addWidget(self._model_combo)

        self._refresh_list_btn = QPushButton("REFRESH LIST")
        self._refresh_list_btn.setObjectName("chatLoadButton")
        self._refresh_list_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_list_btn.setToolTip("Load the newest models from this cloud provider")
        self._refresh_list_btn.clicked.connect(self.refreshListRequested.emit)
        self._refresh_list_btn.hide()
        top.addWidget(self._refresh_list_btn)

        self._ping_list_btn = QPushButton("PING LIST")
        self._ping_list_btn.setObjectName("chatLoadButton")
        self._ping_list_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ping_list_btn.setToolTip("Keep only the free models that answer")
        self._ping_list_btn.clicked.connect(self.pingListRequested.emit)
        self._ping_list_btn.hide()
        top.addWidget(self._ping_list_btn)

        self._install_opencode_btn = QPushButton("INSTALL OPENCODE")
        self._install_opencode_btn.setObjectName("chatLoadButton")
        self._install_opencode_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._install_opencode_btn.setToolTip("Install OpenCode on this PC")
        self._install_opencode_btn.clicked.connect(self.installOpencodeRequested.emit)
        self._install_opencode_btn.hide()
        top.addWidget(self._install_opencode_btn)

        self._install_ollama_btn = QPushButton("INSTALL OLLAMA")
        self._install_ollama_btn.setObjectName("chatLoadButton")
        self._install_ollama_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._install_ollama_btn.setToolTip("Install Ollama on this PC")
        self._install_ollama_btn.clicked.connect(self.installOllamaRequested.emit)
        self._install_ollama_btn.hide()
        top.addWidget(self._install_ollama_btn)

        self._load_btn = QPushButton("LOAD MODEL")
        self._load_btn.setObjectName("chatLoadButton")
        self._load_btn.setMinimumWidth(130)
        self._load_btn.setMaximumWidth(160)
        self._load_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        top.addWidget(self._load_btn)

        self._scope_combo = QComboBox()
        self._scope_combo.setObjectName("composerCombo")
        self._scope_combo.setToolTip("The workspace and project this turn belongs to")
        self._scope_combo.setMinimumWidth(160)
        self._scope_combo.hide()
        top.addWidget(self._scope_combo)
        top.addStretch(1)
        root.addLayout(top)

        # ---- the input box ----
        box = QFrame()
        box.setObjectName("composerBox")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(12, 10, 10, 8)
        box_layout.setSpacing(6)

        self._input = QTextEdit()
        self._input.setObjectName("composerInput")
        self._input.setPlaceholderText(PLACEHOLDER)
        self._input.setAcceptRichText(False)
        self._input.setMinimumHeight(60)
        self._input.setMaximumHeight(120)
        self._input.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._input.installEventFilter(self)
        box_layout.addWidget(self._input)

        # The row inside the box.
        bottom = QHBoxLayout()
        bottom.setSpacing(6)

        self._attach_btn = QPushButton("+")
        self._attach_btn.setObjectName("composerIconBtn")
        self._attach_btn.setToolTip("Attach an image (needs a model with vision)")
        self._attach_btn.clicked.connect(self.attachRequested.emit)
        bottom.addWidget(self._attach_btn)

        bottom.addStretch(1)

        self._mic_btn = QPushButton("🎤")
        self._mic_btn.setObjectName("composerIconBtn")
        self._mic_btn.setToolTip("Dictate (Windows voice typing)")
        self._mic_btn.clicked.connect(self.micRequested.emit)
        bottom.addWidget(self._mic_btn)

        self._speak_btn = QPushButton("🔊")
        self._speak_btn.setObjectName("composerRoundBtn")
        self._speak_btn.setToolTip("Read the last answer out loud")
        self._speak_btn.clicked.connect(self.speakRequested.emit)
        bottom.addWidget(self._speak_btn)

        self._send_btn = QPushButton("SEND")
        self._send_btn.setObjectName("composerSendBtn")
        self._send_btn.setToolTip("Send the message (Enter)")
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.clicked.connect(self._on_send_clicked)
        bottom.addWidget(self._send_btn)

        self._stop_btn = QPushButton("STOP")
        self._stop_btn.setObjectName("composerStopBtn")
        self._stop_btn.setToolTip("Stop the current answer")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self.stopRequested.emit)
        self._stop_btn.hide()
        bottom.addWidget(self._stop_btn)

        box_layout.addLayout(bottom)
        root.addWidget(box)

        # ---- the action chips ----
        chips = QHBoxLayout()
        chips.setSpacing(8)
        for title, hint, _kind in CHIPS:
            chip = QPushButton(f"{title}  {hint}".strip())
            chip.setObjectName("composerChip")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(
                lambda _checked=False, kind=_kind: self._on_chip(kind)
            )
            chips.addWidget(chip)
        chips.addStretch(1)
        root.addLayout(chips)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

    # ------------------------------------------------------------------ api

    @property
    def provider_combo(self) -> QComboBox:
        return self._provider_combo

    @property
    def model_combo(self) -> QComboBox:
        return self._model_combo

    @property
    def cloud_provider_combo(self) -> QComboBox:
        return self._cloud_provider_combo

    @property
    def scope_combo(self) -> QComboBox:
        return self._scope_combo

    @property
    def input(self) -> QTextEdit:
        return self._input

    @property
    def attach_button(self) -> QPushButton:
        return self._attach_btn

    @property
    def stop_button(self) -> QPushButton:
        return self._stop_btn

    @property
    def load_button(self) -> QPushButton:
        return self._load_btn

    @property
    def send_button(self) -> QPushButton:
        return self._send_btn

    def set_running(self, running: bool) -> None:
        """Show STOP while a turn is in flight and hide SEND."""
        try:
            self._stop_btn.setVisible(running)
            self._stop_btn.setEnabled(running)
            self._send_btn.setVisible(not running)
            self._send_btn.setEnabled(not running)
        except Exception:
            pass

    def _on_send_clicked(self) -> None:
        """SEND was clicked — emit the send request if there is text."""
        try:
            if self.text():
                self.sendRequested.emit()
        except Exception:
            pass

    def set_install_buttons(self, ollama: bool, opencode: bool) -> None:
        self._install_ollama_btn.setVisible(ollama)
        self._install_opencode_btn.setVisible(opencode)

    def set_list_buttons_enabled(self, enabled: bool) -> None:
        self._refresh_list_btn.setEnabled(enabled)
        self._ping_list_btn.setEnabled(enabled)

    def set_input_visible(self, visible: bool) -> None:
        """Hide the input box (the OpenCode console takes over) but keep the
        provider row, so the provider can still be switched."""
        self._input.setVisible(visible)
        self._attach_btn.setVisible(visible)
        self._mic_btn.setVisible(visible)
        self._speak_btn.setVisible(visible)
        self._send_btn.setVisible(visible)

    def set_picker_mode(self, mode: str) -> None:
        """Show the extra pickers for the active provider.

        ``cloud`` shows the provider list and then the models. ``ollama``
        shows only the models. ``opencode`` hides both.
        """
        self._cloud_provider_combo.setVisible(mode == "cloud")
        self._model_combo.setVisible(mode != "opencode")
        self._refresh_list_btn.setVisible(mode == "cloud")
        self._ping_list_btn.setVisible(mode == "cloud")

    def set_cloud_providers(self, providers: list[tuple[str, str]]) -> None:
        """Fill the cloud-provider dropdown. Each item is ``(id, name)``."""
        current = self.selected_cloud_provider()
        self._cloud_provider_combo.blockSignals(True)
        self._cloud_provider_combo.clear()
        for provider_id, name in providers:
            self._cloud_provider_combo.addItem(name, provider_id)
        index = self._cloud_provider_combo.findData(current) if current else 0
        self._cloud_provider_combo.setCurrentIndex(index if index >= 0 else 0)
        self._cloud_provider_combo.blockSignals(False)

    def selected_cloud_provider(self) -> str:
        data = self._cloud_provider_combo.currentData()
        return str(data or "")

    def _on_cloud_provider_changed(self, _index: int) -> None:
        provider_id = self.selected_cloud_provider()
        if provider_id:
            self.cloudProviderChanged.emit(provider_id)

    def text(self) -> str:
        return self._input.toPlainText().strip()

    def set_font_size(self, size: int) -> None:
        """Change the size of the input text."""
        font = self._input.font()
        font.setPointSize(size)
        self._input.setFont(font)

    def set_scope(self, text: str) -> None:
        """Show which workspace and project the turn belongs to.

        The picker itself is hidden — the model is picked in the composer, so
        a dead button in the header only gets in the way.
        """
        self._scope_combo.clear()
        self._scope_combo.addItem(text or "This PC")
        self._scope_combo.setEnabled(False)

    def set_catalogue(self, rows: list[CatalogueRow]) -> None:
        """Fill the model dropdown with the whole catalogue.

        The local models come first, then the models of every cloud provider
        that has a key in the settings — each labelled with its provider and
        with ``● FREE`` or ``○ PAID``.
        """
        if self._model_combo is None:
            return
        current = self.selected_model()

        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        for row in rows:
            index = self._model_combo.count()
            if row.is_header:
                # A section header: shown, but it cannot be picked.  QComboBox
                # stores the item text in the UserRole by default, so it is
                # replaced by None — that is how a header is recognised.
                self._model_combo.insertItem(index, f"— {row.header} —", None)
                model = self._model_combo.model().item(index)
                if model is not None:
                    model.setEnabled(False)
            else:
                self._model_combo.insertItem(index, row.entry.display, row.entry)
                self._model_combo.setItemData(
                    index, _model_tip(row.entry), Qt.ItemDataRole.ToolTipRole
                )
        self._model_combo.blockSignals(False)

        if current is not None:
            self.select_model(current)
        self._model_combo.setToolTip(_model_tip(self.selected_model()))

    def selected_model(self):
        """The model entry that is picked (None when there is none)."""
        if self._model_combo is None:
            return None
        index = self._model_combo.currentIndex()
        if index < 0:
            return None
        return self._model_combo.itemData(index, Qt.ItemDataRole.UserRole)

    def select_model(self, entry) -> bool:
        """Pick a model in the dropdown by its entry."""
        if self._model_combo is None or entry is None:
            return False
        for index in range(self._model_combo.count()):
            data = self._model_combo.itemData(index, Qt.ItemDataRole.UserRole)
            if data is None:
                continue
            if (
                getattr(data, "kind", "") == getattr(entry, "kind", "")
                and getattr(data, "model_id", "") == getattr(entry, "model_id", "")
                and getattr(data, "provider_id", "")
                == getattr(entry, "provider_id", "")
            ):
                self._model_combo.setCurrentIndex(index)
                return True
        return False

    def set_text(self, text: str) -> None:
        self._input.setPlainText(text)
        self._input.setFocus()

    def clear(self) -> None:
        self._input.clear()

    def focus(self) -> None:
        self._input.setFocus()

    def set_vision_enabled(self, enabled: bool) -> None:
        self._attach_btn.setEnabled(enabled)
        self._attach_btn.setToolTip(
            "Attach an image (needs a model with vision)"
            if enabled
            else "This model has no vision — pick one that has"
        )

    # ------------------------------------------------------------------ events

    def _on_provider_changed(self, _index: int) -> None:
        try:
            from thecore.debug_log import logger
            logger.debug("Composer provider changed")
        except Exception:
            pass
        try:
            provider_id = str(self._provider_combo.currentData() or "")
            self.providerChanged.emit(provider_id)
        except Exception as e:
            try:
                from thecore.debug_log import logger
                logger.exception("Error in composer provider change: %s", e)
            except Exception:
                pass

    def _on_model_changed(self, _index: int) -> None:
        """A model was picked in the dropdown."""
        try:
            entry = self.selected_model()
            if entry is not None:
                if hasattr(self, '_last_emitted_model'):
                    last = self._last_emitted_model
                    if getattr(last, 'kind', '') == getattr(entry, 'kind', '') and \
                       getattr(last, 'model_id', '') == getattr(entry, 'model_id', '') and \
                       getattr(last, 'provider_id', '') == getattr(entry, 'provider_id', ''):
                        return
                self._last_emitted_model = entry
                self._model_combo.setToolTip(_model_tip(entry))
                self.modelSelected.emit(entry)
        except Exception:
            pass

    def _on_chip(self, kind: str) -> None:
        """A chip was clicked — it pre-fills the input."""
        self.prefillRequested.emit(
            "Work through this in several steps and keep me posted: "
        )

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 — Qt API
        """Enter sends, Shift+Enter makes a new line."""
        if obj is self._input and event.type() == event.Type.KeyPress:
            if isinstance(event, QKeyEvent) and event.key() in (
                Qt.Key.Key_Return,
                Qt.Key.Key_Enter,
            ):
                if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                    if self.text():
                        self.sendRequested.emit()
                        return True
                    return True  # consume even if empty to prevent new line issues
        return super().eventFilter(obj, event)
