"""The settings page — every setting of the program in one place.

It is opened from the gear icon in the bottom-left corner of the sidebar and
holds:

* **Cloud providers** — the API key of every provider, its pricing tier and
  the model list with a ``● FREE`` / ``○ PAID`` label per model.
* **Local models** — the Ollama models that are installed on this PC.
* **Appearance** — the text size.
* **About** — where the keys and the log file live.

The API keys are stored in ``%APPDATA%\\TheCore`` — never in the database and
never in the repository.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from thecore.ai.cloud_client import (
    PROVIDERS,
    PROVIDERS_BY_ID,
    load_base_url,
    load_key,
    save_base_url,
    save_key,
)
from thecore.ai.cloud_worker import CloudCatalogueThread, CloudCatalogueWorker
from thecore.ai.ollama_client import OllamaClient
from thecore.settings_store import get_setting, set_setting


class SettingsPage(QWidget):
    """The full settings page."""

    # The user wants to go back to the chat.
    closed = Signal()
    # The set of models changed (a key was saved or removed): (provider id)
    cloud_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsPage")

        self._catalogue: dict[str, list] = {}
        self._catalogue_thread: Optional[CloudCatalogueThread] = None
        self._selected_provider_id: str = PROVIDERS[0].id

        self._provider_cards: dict[str, QFrame] = {}
        self._key_edits: dict[str, QLineEdit] = {}
        self._status_labels: dict[str, QLabel] = {}

        self._build_ui()
        self._load_current()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- the header ----
        header = QFrame()
        header.setObjectName("settingsPageHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 14, 20, 14)
        header_layout.setSpacing(12)

        title = QLabel("SETTINGS")
        title.setObjectName("settingsPageTitle")
        header_layout.addWidget(title)
        header_layout.addStretch(1)

        back = QPushButton("←  BACK TO CHAT")
        back.setObjectName("settingsBackBtn")
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.clicked.connect(self.closed.emit)
        header_layout.addWidget(back)

        root.addWidget(header)

        # ---- the scrolling body ----
        scroll = QScrollArea()
        scroll.setObjectName("settingsPageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body = QWidget()
        body.setObjectName("settingsPageBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 18, 20, 24)
        body_layout.setSpacing(16)

        body_layout.addWidget(self._build_cloud_section())
        body_layout.addWidget(self._build_models_section())
        body_layout.addWidget(self._build_local_section())
        body_layout.addWidget(self._build_appearance_section())
        body_layout.addWidget(self._build_about_section())
        body_layout.addStretch(1)

        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

    # ---- the sections ---------------------------------------------------

    def _section(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("settingsSection")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        label = QLabel(title)
        label.setObjectName("settingsSectionTitle")
        layout.addWidget(label)
        return frame, layout

    def _build_cloud_section(self) -> QFrame:
        frame, layout = self._section("CLOUD PROVIDERS")
        layout.addWidget(
            self._hint(
                "Store an API key per provider. A key is needed before the "
                "provider's models can be listed. Keys never leave this PC."
            )
        )

        for provider in PROVIDERS:
            layout.addWidget(self._provider_card(provider))

        return frame

    def _provider_card(self, provider) -> QFrame:
        """One card per provider: name, tier, key field and buttons."""
        card = QFrame()
        card.setObjectName("providerCard")
        card.setProperty("selected", "false")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)

        # ---- the title row ----
        top = QHBoxLayout()
        top.setSpacing(8)

        name = QLabel(provider.name)
        name.setObjectName("providerName")
        top.addWidget(name)

        badge = QLabel(provider.tier_label)
        badge.setObjectName("providerBadge")
        badge.setProperty("tier", provider.tier_label.replace(" ", "-").lower())
        top.addWidget(badge)

        top.addStretch(1)
        layout.addLayout(top)

        notes = QLabel(provider.notes)
        notes.setObjectName("providerNotes")
        notes.setWordWrap(True)
        layout.addWidget(notes)

        # ---- the key row ----
        row = QHBoxLayout()
        row.setSpacing(8)

        key_edit = QLineEdit()
        key_edit.setObjectName("settingsKeyEdit")
        key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        key_edit.setPlaceholderText("API key — stored in %APPDATA%\\TheCore")
        key_edit.textChanged.connect(
            lambda _text, pid=provider.id: self._on_key_edited(pid)
        )
        row.addWidget(key_edit, stretch=1)
        self._key_edits[provider.id] = key_edit

        save = QPushButton("SAVE")
        save.setObjectName("settingsSaveBtn")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.clicked.connect(lambda _c=False, pid=provider.id: self._save_key(pid))
        row.addWidget(save)

        clear = QPushButton("CLEAR")
        clear.setObjectName("settingsClearBtn")
        clear.setCursor(Qt.CursorShape.PointingHandCursor)
        clear.clicked.connect(lambda _c=False, pid=provider.id: self._clear_key(pid))
        row.addWidget(clear)

        if provider.signup_url:
            link = QPushButton("GET A FREE KEY")
            link.setObjectName("settingsLinkBtn")
            link.setCursor(Qt.CursorShape.PointingHandCursor)
            link.setToolTip(provider.signup_url)
            link.clicked.connect(
                lambda _c=False, url=provider.signup_url: QDesktopServices.openUrl(
                    QUrl(url)
                )
            )
            row.addWidget(link)

        layout.addLayout(row)

        # ---- the base URL, only for the custom endpoint ----
        if provider.id == "custom":
            base_row = QHBoxLayout()
            base_row.setSpacing(8)
            base_row.addWidget(QLabel("Base URL:"))
            base_edit = QLineEdit()
            base_edit.setObjectName("settingsBaseEdit")
            base_edit.setPlaceholderText("https://your-endpoint/v1")
            base_row.addWidget(base_edit, stretch=1)
            layout.addLayout(base_row)
            self._base_edit = base_edit

        # ---- the status ----
        status = QLabel("")
        status.setObjectName("settingsKeyStatus")
        layout.addWidget(status)
        self._status_labels[provider.id] = status

        # Clicking the card selects the provider for the model list.
        card.mousePressEvent = self._make_click_handler(provider.id)  # type: ignore[method-assign]

        self._provider_cards[provider.id] = card
        return card

    def _make_click_handler(self, provider_id: str):
        def handler(event) -> None:
            self._select_provider(provider_id)
            QFrame.mousePressEvent(self._provider_cards[provider_id], event)

        return handler

    def _build_models_section(self) -> QFrame:
        frame, layout = self._section("CLOUD MODELS")

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel("Provider:"))

        self._model_provider_combo = QComboBox()
        self._model_provider_combo.setObjectName("settingsCombo")
        self._model_provider_combo.setMinimumWidth(220)
        for provider in PROVIDERS:
            self._model_provider_combo.addItem(provider.name, provider.id)
        self._model_provider_combo.currentIndexChanged.connect(
            self._on_model_provider_changed
        )
        row.addWidget(self._model_provider_combo)

        refresh = QPushButton("REFRESH MODELS")
        refresh.setObjectName("settingsSaveBtn")
        refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh.clicked.connect(self._refresh_catalogue)
        row.addWidget(refresh)

        row.addStretch(1)
        layout.addLayout(row)

        self._model_info = QLabel("")
        self._model_info.setObjectName("settingsModelInfo")
        self._model_info.setWordWrap(True)
        layout.addWidget(self._model_info)

        return frame

    def _build_local_section(self) -> QFrame:
        frame, layout = self._section("LOCAL MODELS (OLLAMA)")

        row = QHBoxLayout()
        row.setSpacing(8)

        self._local_info = QLabel("")
        self._local_info.setObjectName("settingsModelInfo")
        self._local_info.setWordWrap(True)
        row.addWidget(self._local_info, stretch=1)

        refresh = QPushButton("REFRESH")
        refresh.setObjectName("settingsSaveBtn")
        refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh.clicked.connect(self._refresh_local_models)
        row.addWidget(refresh)

        layout.addLayout(row)
        return frame

    def _build_appearance_section(self) -> QFrame:
        frame, layout = self._section("APPEARANCE")

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel("Text size:"))

        self._size_combo = QComboBox()
        self._size_combo.setObjectName("settingsCombo")
        for size in (11, 12, 13, 14, 16, 18, 20):
            self._size_combo.addItem(f"{size} pt", size)
        current = int(get_setting("font_size", 14) or 14)
        index = self._size_combo.findData(current)
        self._size_combo.setCurrentIndex(index if index >= 0 else 3)
        self._size_combo.currentIndexChanged.connect(self._on_size_changed)
        row.addWidget(self._size_combo)

        row.addStretch(1)
        layout.addLayout(row)
        return frame

    def _build_about_section(self) -> QFrame:
        frame, layout = self._section("ABOUT")

        text = QLabel(
            "CORE — Code Orchestration &amp; Real-time Engineering\n"
            "Your code. Your AI. Your control.\n\n"
            "Chat with a local model through Ollama, drive the real opencode "
            "console, or reach a cloud provider.\n\n"
            "API keys and the log file live in %APPDATA%\\TheCore — never in "
            "the database and never in the repository."
        )
        text.setObjectName("settingsAbout")
        text.setWordWrap(True)
        layout.addWidget(text)

        row = QHBoxLayout()
        row.setSpacing(8)
        folder = QPushButton("OPEN THE SETTINGS FOLDER")
        folder.setObjectName("settingsClearBtn")
        folder.setCursor(Qt.CursorShape.PointingHandCursor)
        folder.clicked.connect(self._open_folder)
        row.addWidget(folder)
        row.addStretch(1)
        layout.addLayout(row)

        return frame

    @staticmethod
    def _hint(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("settingsHint")
        label.setWordWrap(True)
        return label

    # ------------------------------------------------------------------ load / save

    def _load_current(self) -> None:
        """Show the stored keys and the local models."""
        for provider in PROVIDERS:
            edit = self._key_edits.get(provider.id)
            if edit is not None:
                edit.setText(load_key(provider.id))
            self._update_status(provider.id)

        base_edit = getattr(self, "_base_edit", None)
        if base_edit is not None:
            base_edit.setText(load_base_url())

        self._refresh_local_models()
        self._refresh_catalogue()

    def _update_status(self, provider_id: str) -> None:
        label = self._status_labels.get(provider_id)
        if label is None:
            return
        if load_key(provider_id):
            label.setText("KEY STORED ●")
            label.setProperty("state", "stored")
        else:
            label.setText("NO KEY — the provider cannot be used yet")
            label.setProperty("state", "none")
        label.style().unpolish(label)
        label.style().polish(label)

    def _select_provider(self, provider_id: str) -> None:
        """Highlight the card and show that provider's models."""
        for pid, card in self._provider_cards.items():
            card.setProperty("selected", "true" if pid == provider_id else "false")
            card.style().unpolish(card)
            card.style().polish(card)
        self._selected_provider_id = provider_id

        index = self._model_provider_combo.findData(provider_id)
        if index >= 0:
            self._model_provider_combo.setCurrentIndex(index)
        self._update_model_info()

    def _on_model_provider_changed(self, _index: int) -> None:
        provider_id = str(self._model_provider_combo.currentData() or "")
        self._selected_provider_id = provider_id
        for pid, card in self._provider_cards.items():
            card.setProperty("selected", "true" if pid == provider_id else "false")
            card.style().unpolish(card)
            card.style().polish(card)
        self._update_model_info()

    def _update_model_info(self) -> None:
        """Show the models of the selected provider, free ones first."""
        provider_id = self._selected_provider_id
        provider = PROVIDERS_BY_ID.get(provider_id)
        if provider is None:
            return

        models = self._catalogue.get(provider_id) or []
        if not load_key(provider_id):
            self._model_info.setText(
                f"{provider.name} — no API key stored, so no models can be listed."
            )
            return
        if not models:
            self._model_info.setText(
                f"{provider.name} — no models found. "
                "Check the key and press REFRESH MODELS."
            )
            return

        free = [m for m in models if m.free]
        paid = [m for m in models if not m.free]
        lines = [f"{provider.name} — {len(models)} models ({provider.tier_label})"]
        if free:
            lines.append(
                "● FREE: " + ", ".join(m.display for m in free[:10])
                + (" …" if len(free) > 10 else "")
            )
        if paid:
            lines.append(
                "○ PAID: " + ", ".join(m.display for m in paid[:10])
                + (" …" if len(paid) > 10 else "")
            )
        self._model_info.setText("\n".join(lines))

    def _refresh_local_models(self) -> None:
        """List the Ollama models that are installed on this PC."""
        try:
            models = OllamaClient().list_models()
        except Exception:  # noqa: BLE001 — Ollama may be offline
            models = []
        if not models:
            self._local_info.setText(
                "No local models found. Start Ollama and pull a model, "
                "for example:  ollama pull qwen2.5-coder:7b"
            )
            return
        lines = [f"{len(models)} models installed"]
        for model in models[:12]:
            lines.append(f"{model.name}  ({model.size_gb:.1f} GB)")
        if len(models) > 12:
            lines.append(f"… and {len(models) - 12} more")
        self._local_info.setText("\n".join(lines))

    def _refresh_catalogue(self) -> None:
        """Ask every provider with a key for its model list (in a thread)."""
        if self._catalogue_thread is not None and self._catalogue_thread.isRunning():
            return
        self._catalogue = {}
        worker = CloudCatalogueWorker()
        thread = CloudCatalogueThread(worker, self)
        worker.provider_models.connect(self._on_provider_models)
        worker.finished.connect(self._on_catalogue_finished)
        self._catalogue_thread = thread
        thread.start()

    def _on_provider_models(self, provider_id: str, models: list) -> None:
        self._catalogue[provider_id] = models
        if provider_id == self._selected_provider_id:
            self._update_model_info()

    def _on_catalogue_finished(self) -> None:
        self._update_model_info()

    # ------------------------------------------------------------------ events

    def _on_key_edited(self, provider_id: str) -> None:
        """A key was typed but not saved yet."""
        label = self._status_labels.get(provider_id)
        if label is None:
            return
        edit = self._key_edits.get(provider_id)
        stored = load_key(provider_id)
        if edit is not None and edit.text().strip() != stored:
            label.setText("UNSAVED CHANGES")
            label.setProperty("state", "none")
            label.style().unpolish(label)
            label.style().polish(label)

    def _save_key(self, provider_id: str) -> None:
        edit = self._key_edits.get(provider_id)
        key = edit.text().strip() if edit is not None else ""
        save_key(provider_id, key)
        if provider_id == "custom":
            base_edit = getattr(self, "_base_edit", None)
            if base_edit is not None:
                save_base_url(base_edit.text().strip())
        self._update_status(provider_id)
        self._refresh_catalogue()
        self.cloud_changed.emit(provider_id)

    def _clear_key(self, provider_id: str) -> None:
        save_key(provider_id, "")
        edit = self._key_edits.get(provider_id)
        if edit is not None:
            edit.clear()
        self._update_status(provider_id)
        self._catalogue.pop(provider_id, None)
        self._update_model_info()
        self.cloud_changed.emit(provider_id)

    def _on_size_changed(self, _index: int) -> None:
        size = self._size_combo.currentData()
        if size is not None:
            set_setting("font_size", int(size))

    def _open_folder(self) -> None:
        import os
        from pathlib import Path

        base = os.environ.get("APPDATA") or str(Path.home())
        folder = Path(base) / "TheCore"
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
