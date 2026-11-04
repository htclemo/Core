"""A single chat message bubble.

Code blocks inside an assistant reply are rendered as **collapsible** sections
so a long code answer does not immediately flood the conversation.  The text
around the code stays visible, and the collapse state can be toggled with a
single click.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# How many lines a folded message still shows.
_COLLAPSED_LINES = 6


@dataclass
class _Segment:
    """A slice of a message: plain text or a fenced code block."""

    kind: str  # "text" | "code"
    lang: str
    text: str


def split_segments(content: str) -> List[_Segment]:
    """Split a message into text and fenced-code segments.

    An unterminated fence (still streaming) is treated as a code block so the
    output stays collapsed while it is being written.
    """
    segments: List[_Segment] = []
    text_buf: List[str] = []
    code_buf: List[str] = []
    lang = ""
    in_code = False

    def flush_text() -> None:
        if text_buf:
            segments.append(_Segment("text", "", "\n".join(text_buf)))
            text_buf.clear()

    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_code:
                segments.append(_Segment("code", lang, "\n".join(code_buf)))
                code_buf.clear()
                lang = ""
                in_code = False
            else:
                flush_text()
                in_code = True
                lang = stripped[3:].strip()
            continue
        if in_code:
            code_buf.append(line)
        else:
            text_buf.append(line)

    if in_code:
        # Streaming / unterminated block.
        segments.append(_Segment("code", lang, "\n".join(code_buf)))
    flush_text()
    return segments


class _CodeBlock(QFrame):
    """A collapsible fenced-code section."""

    def __init__(self, lang: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("codeBlock")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("codeBlockHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 6, 8, 6)
        header_layout.setSpacing(8)

        self._toggle = QPushButton("")
        self._toggle.setObjectName("codeBlockToggle")
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.setFlat(True)
        self._toggle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._toggle.clicked.connect(self._on_toggle)

        self._copy = QPushButton("COPY")
        self._copy.setObjectName("codeBlockCopy")
        self._copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy.setFlat(True)
        self._copy.clicked.connect(self._on_copy)

        header_layout.addWidget(self._toggle, stretch=1)
        header_layout.addWidget(self._copy, stretch=0)
        layout.addWidget(header)

        self._view = QPlainTextEdit()
        self._view.setObjectName("codeBlockContent")
        self._view.setReadOnly(True)
        self._view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        self._view.hide()

        layout.addWidget(self._view)

        self._expanded = False
        self._lang = lang
        self.set_content(lang, text)

    # ------------------------------------------------------------------ api

    def set_content(self, lang: str, text: str) -> None:
        self._lang = lang
        self._view.setPlainText(text)
        lines = text.count("\n") + 1 if text else 0
        height = min(430, 26 + lines * 16)
        self._view.setFixedHeight(max(40, height))
        self._update_header(lines)

    def _update_header(self, lines: int) -> None:
        arrow = "▾" if self._expanded else "▸"
        label = self._lang.upper() if self._lang else "CODE"
        self._toggle.setText(f"{arrow}  {label}  ·  {lines} line{'s' if lines != 1 else ''}")

    def _on_toggle(self) -> None:
        self._expanded = not self._expanded
        self._view.setVisible(self._expanded)
        self._update_header(self._view.toPlainText().count("\n") + 1)
        if self._expanded:
            self._view.verticalScrollBar().setValue(0)

    def _on_copy(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._view.toPlainText())
        self._copy.setText("COPIED")
        from PySide6.QtCore import QTimer

        QTimer.singleShot(1200, lambda: self._copy.setText("COPY"))


class MessageWidget(QFrame):
    def __init__(
        self,
        role: str,
        content: str,
        temporary: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("messageBubble")
        self._role = role
        self._content = content
        self._temporary = temporary
        self._collapsed = False
        self._more_btn: Optional[QPushButton] = None

        is_user = role == "user"

        # All messages left-aligned — no user/assistant alignment nudge.
        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 4)
        outer.setSpacing(0)

        bubble = QFrame()
        bubble.setObjectName("assistantBubble" if not is_user else "userBubble")
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(12, 8, 12, 8)
        bubble_layout.setSpacing(4)

        role_label = QLabel("YOU" if is_user else "ASSISTANT")
        role_label.setObjectName("messageRole")
        # Same alignment for both roles.
        role_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        bubble_layout.addWidget(role_label)

        # Cap bubble width so long lines wrap nicely
        bubble.setMaximumWidth(820)

        self._body = bubble_layout
        self._segment_widgets: List[QWidget] = []
        self._structure: Optional[List[tuple]] = None

        outer.addWidget(bubble)
        outer.addStretch(1)

        self._apply_temporary_style()
        self._rebuild()

    # ------------------------------------------------------------------ properties

    @property
    def role(self) -> str:
        return self._role

    @property
    def content(self) -> str:
        return self._content

    @property
    def temporary(self) -> bool:
        return self._temporary

    # ------------------------------------------------------------------ mutations

    def set_content(self, content: str) -> None:
        self._content = content
        self._rebuild()

    def set_temporary(self, temporary: bool) -> None:
        self._temporary = temporary
        self._apply_temporary_style()

    def set_collapsed(self, collapsed: bool) -> None:
        """Collapse a long message to its last lines, or expand it again.

        A long answer is shown folded so the chat stays readable; clicking it
        reveals the whole text.
        """
        if self._collapsed == collapsed:
            return
        self._collapsed = collapsed
        # Force a full rebuild so the labels get their text back.
        self._structure = None
        self._rebuild()

    @property
    def collapsed(self) -> bool:
        return self._collapsed

    def _apply_collapse(self) -> None:
        """Show only the tail of a long message, with a way to expand it."""
        if self._more_btn is not None:
            self._more_btn.setParent(None)
            self._more_btn.deleteLater()
            self._more_btn = None

        if not self._collapsed:
            for widget in self._segment_widgets:
                if isinstance(widget, QLabel):
                    widget.setMaximumHeight(16777215)
            return

        # Trim the text labels down to the last few lines.
        lines = self._content.splitlines()
        keep = lines[-_COLLAPSED_LINES:]
        hidden = len(lines) - len(keep)
        for widget in self._segment_widgets:
            if isinstance(widget, QLabel):
                widget.setText("\n".join(keep))
                widget.setMaximumHeight(_COLLAPSED_LINES * 22 + 8)

        if hidden <= 0:
            return

        self._more_btn = QPushButton(
            f"⋯ {hidden} more line{'s' if hidden != 1 else ''}  ·  show all"
        )
        self._more_btn.setObjectName("messageMoreButton")
        self._more_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._more_btn.clicked.connect(self._on_more_clicked)
        self._body.insertWidget(0, self._more_btn)

    def _on_more_clicked(self) -> None:
        """Expand the message."""
        self.set_collapsed(False)

    def _apply_temporary_style(self) -> None:
        # Dim temporary (streaming) bubbles slightly so the user knows it is still
        # being generated.
        if self._temporary:
            self.setProperty("temporary", "true")
        else:
            self.setProperty("temporary", "false")
        self.style().unpolish(self)
        self.style().polish(self)

    # ------------------------------------------------------------------ rendering

    def _rebuild(self) -> None:
        """Render the message, reusing widgets when the structure is unchanged."""
        segments = split_segments(self._content)
        structure = [(s.kind, s.lang) for s in segments]

        if structure == self._structure and len(self._segment_widgets) == len(segments):
            # Same layout — just refresh the text.
            for widget, segment in zip(self._segment_widgets, segments):
                if isinstance(widget, _CodeBlock):
                    widget.set_content(segment.lang, segment.text)
                elif isinstance(widget, QLabel):
                    widget.setText(segment.text)
            return

        # Structure changed — rebuild the widgets.
        while self._body.count():
            item = self._body.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # Detach first so the stale widget leaves the widget tree
                # immediately instead of lingering until the event loop runs.
                widget.setParent(None)
                widget.deleteLater()

        self._segment_widgets = []
        for segment in segments:
            if segment.kind == "code":
                block = _CodeBlock(segment.lang, segment.text)
                self._body.addWidget(block)
                self._segment_widgets.append(block)
            else:
                label = QLabel(segment.text)
                label.setObjectName("messageContent")
                label.setWordWrap(True)
                label.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                )
                label.setAlignment(
                    Qt.AlignmentFlag.AlignRight
                    if self._role == "user"
                    else Qt.AlignmentFlag.AlignLeft
                )
                self._body.addWidget(label)
                self._segment_widgets.append(label)

        if self._collapsed:
            self._apply_collapse()

        self._structure = structure
