"""The updates dropdown: a dark panel under the menu-bar button."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from thecore.updates import UpdateItem


class UpdatesPanel(QFrame):
    """PROGRAMMA'S list with a per-item update button. Nothing installs itself."""

    update_one = Signal(object)
    update_all = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint,
        )
        self.setObjectName("updatesPanel")
        self.setFixedWidth(420)
        self._body = QVBoxLayout(self)
        self._body.setContentsMargins(16, 14, 16, 14)
        self._body.setSpacing(10)
        title = QLabel("PROGRAMMA'S")
        title.setObjectName("updatesTitle")
        self._body.addWidget(title)
        self._rows = QVBoxLayout()
        self._rows.setSpacing(12)
        self._body.addLayout(self._rows)

    def show_items(self, items: list[UpdateItem]) -> None:
        while self._rows.count():
            child = self._rows.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()
        if not items:
            waiting = QLabel("Bezig met kijken…")
            waiting.setObjectName("updatesNote")
            self._rows.addWidget(waiting)
            return
        for item in items:
            if item.kind == "package":
                continue
            self._rows.addWidget(self._program(item))
        packages = [item for item in items if item.kind == "package"]
        pending = [item for item in packages if item.available]
        if pending:
            for item in pending:
                self._rows.addWidget(self._program(item))
        else:
            note = QLabel("pakketten: bijgewerkt")
            note.setObjectName("updatesNote")
            self._rows.addWidget(note)
        pending_all = [item for item in items if item.available]
        if len(pending_all) > 1:
            everything = QPushButton("UPDATE ALL")
            everything.setObjectName("updatesAction")
            everything.setCursor(Qt.CursorShape.PointingHandCursor)
            everything.clicked.connect(lambda _checked=False, chosen=list(pending_all): self._ask_all(chosen))
            self._rows.addWidget(everything)
        self.adjustSize()

    def _program(self, item: UpdateItem) -> QWidget:
        block = QWidget()
        block.setObjectName("updatesRow")
        layout = QVBoxLayout(block)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        head = QLabel(self._headline(item))
        head.setObjectName("updatesCurrent" if not item.available else "updatesAvailable")
        head.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(head)

        if item.kind == "python" and not item.available:
            sub = QLabel(item.detail or "intern  ·  bij")
            sub.setObjectName("updatesNote")
            layout.addWidget(sub)
        elif item.detail:
            note = QLabel(item.detail)
            note.setObjectName("updatesDetail")
            note.setWordWrap(True)
            layout.addWidget(note)

        if item.available:
            button = QPushButton(f"UPDATE {item.name.upper()}")
            button.setObjectName("updatesAction")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, chosen=item: self._ask(chosen))
            layout.addWidget(button)
            extra = self._keep_line(item)
            if extra:
                kept = QLabel(extra)
                kept.setObjectName("updatesNote")
                layout.addWidget(kept)
        elif item.kind == "package":
            size = QLabel(item.size) if item.size else None
            if size is not None:
                size.setObjectName("updatesNote")
                layout.addWidget(size)
        return block

    def changeEvent(self, event) -> None:
        # A popup ate the click before the button could fire. This window stays
        # up while the button is pressed and only closes once it loses focus.
        if event.type() == QEvent.Type.WindowDeactivate:
            self.hide()
        super().changeEvent(event)

    def _ask(self, item: UpdateItem) -> None:
        self.update_one.emit(item)
        self.hide()

    def _ask_all(self, items: list[UpdateItem]) -> None:
        self.update_all.emit(items)
        self.hide()


class UpdateProgress(QDialog):
    """Small 0–100 bar shown while an update is installed."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("updateProgress")
        self.setWindowTitle("Updating")
        self.setModal(True)
        self.setFixedSize(420, 150)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        self._label = QLabel("Updating")
        self._label.setObjectName("updatesAvailable")
        self._label.setWordWrap(True)
        self._bar = QProgressBar()
        self._bar.setObjectName("updateBar")
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(True)
        self._bar.setFormat("%p%")
        layout.addWidget(self._label)
        layout.addWidget(self._bar)

    def set_progress(self, percent: int, text: str) -> None:
        self._label.setText(text)
        self._bar.setValue(max(0, min(100, percent)))

    @staticmethod
    def _headline(item: UpdateItem) -> str:
        if item.available and item.current not in ("unknown", ""):
            return (
                f"{item.name.upper()}  "
                f"{item.current}  →  {item.latest}"
            )
        version = item.current if item.current not in ("unknown", "") else item.latest
        return f"{item.name.upper()} bij  ({version})"

    @staticmethod
    def _keep_line(item: UpdateItem) -> str:
        if item.kind == "ollama":
            size = f"  ·  {item.size}" if item.size else ""
            return f"modellen blijven bewaard{size}"
        if item.size:
            return item.size
        return ""
