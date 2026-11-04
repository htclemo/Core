"""Inline in-chat status indicator.

Shown inside the conversation while the backend is working so the user can
always see what the AI is doing:

    @connecting   -> request sent, waiting for the model to answer
    @reasoning    -> the model is producing chain-of-thought (thinking models)
    @generating   -> the model is streaming the answer

The indicator also reports live statistics (elapsed time, token count,
tokens/second) and collapses into a compact one-line summary once the
turn is finished.
"""

from __future__ import annotations

import time
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ThinkingIndicator(QFrame):
    """A rounded status bubble rendered between chat messages."""

    CONNECTING = "connecting"
    THINKING = "thinking"
    GENERATING = "generating"
    DONE = "done"
    ERROR = "error"
    STOPPED = "stopped"

    _SPIN = ["◐", "◓", "◑", "◒"]

    def __init__(self, model: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusBubble")
        # The bubble hugs its content — it must never stretch vertically.
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        self._model = model
        self._state = self.CONNECTING
        self._start = time.monotonic()
        self._end: Optional[float] = None
        self._tokens = 0
        self._chars = 0
        self._spin_idx = 0
        self._reasoning = ""
        self._reason_visible = True
        self._tps: Optional[float] = None
        self.total_duration_ns = 0
        self.load_duration_ns = 0

        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 4)
        outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("statusCard")
        card.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 10, 14, 10)
        card_layout.setSpacing(6)

        # ---- top row: spinner + state + stats -------------------------------
        top = QHBoxLayout()
        top.setSpacing(10)

        self._spinner = QLabel(self._SPIN[0])
        self._spinner.setObjectName("statusSpinner")
        self._spinner.setFixedWidth(18)
        self._spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._title = QLabel("@connecting…")
        self._title.setObjectName("statusTitle")

        self._stats = QLabel("")
        self._stats.setObjectName("statusStats")

        top.addWidget(self._spinner)
        top.addWidget(self._title)
        top.addStretch(1)
        top.addWidget(self._stats)
        card_layout.addLayout(top, 0)

        # ---- reasoning body -------------------------------------------------
        self._reason_box = QFrame()
        self._reason_box.setObjectName("statusReasonBox")
        reason_layout = QVBoxLayout(self._reason_box)
        reason_layout.setContentsMargins(10, 8, 10, 8)
        reason_layout.setSpacing(0)

        self._reason_label = QLabel("")
        self._reason_label.setObjectName("statusReason")
        self._reason_label.setWordWrap(True)
        self._reason_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._reason_label.setMaximumHeight(150)
        # Never grow beyond the text height — the card must stay compact.
        self._reason_label.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Minimum
        )
        reason_layout.addWidget(self._reason_label)
        self._reason_box.hide()
        card_layout.addWidget(self._reason_box, 0)

        # ---- expand / collapse toggle ---------------------------------------
        self._toggle = QPushButton("hide reasoning")
        self._toggle.setObjectName("statusToggle")
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.setVisible(False)
        self._toggle.clicked.connect(self._toggle_reasoning)
        card_layout.addWidget(self._toggle, 0, Qt.AlignmentFlag.AlignLeft)
        card_layout.addStretch(1)

        outer.addWidget(card, stretch=0)
        outer.addStretch(1)
        card.setMaximumWidth(820)

        # ---- elapsed timer ---------------------------------------------------
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(100)

        self._apply_state_style()
        self._update_text()

    # ------------------------------------------------------------------ state

    def set_state(self, state: str) -> None:
        """Move the indicator to a new phase (connecting/thinking/generating)."""
        if self._state in (self.DONE, self.ERROR, self.STOPPED):
            return
        self._state = state
        self._apply_state_style()
        self._update_text()

    def add_reasoning(self, text: str) -> None:
        """Append chain-of-thought text produced by a thinking model."""
        if not text:
            return
        self._reasoning += text
        if self._state == self.CONNECTING:
            self.set_state(self.THINKING)
        self._reason_label.setText(self._reasoning)
        if self._reason_visible:
            self._reason_box.show()
        self._update_text()

    def add_content(self, text: str) -> None:
        """Register streamed answer content (token accounting)."""
        if not text:
            return
        self._chars += len(text)
        # Rough token estimate: ~4 characters per token for code/models.
        self._tokens = max(self._tokens, round(self._chars / 4))
        if self._state in (self.CONNECTING, self.THINKING):
            self.set_state(self.GENERATING)
        self._update_text()

    def set_stats(self, eval_count: int = 0, eval_duration_ns: int = 0) -> None:
        """Apply the authoritative token statistics reported by Ollama."""
        if eval_count:
            self._tokens = int(eval_count)
        if eval_count and eval_duration_ns:
            self._tps = eval_count / (eval_duration_ns / 1_000_000_000)
        self._update_text()

    def finish(self, total_duration_ns: int = 0, load_duration_ns: int = 0) -> None:
        """Mark the turn as finished and collapse the indicator."""
        self._end = time.monotonic()
        self._state = self.DONE
        self._timer.stop()
        self._apply_state_style()
        self._update_text(final=True, total_duration_ns=total_duration_ns,
                          load_duration_ns=load_duration_ns)

    def fail(self, reason: str) -> None:
        """Mark the turn as failed."""
        self._end = time.monotonic()
        self._state = self.ERROR
        self._timer.stop()
        self._title.setText(f"@error — {reason}")
        self._spinner.setText("✕")
        self._stats.setText("")
        self._apply_state_style()

    def stop(self) -> None:
        """Mark the turn as cancelled by the user."""
        self._end = time.monotonic()
        self._state = self.STOPPED
        self._timer.stop()
        self._spinner.setText("■")
        self._apply_state_style()
        self._update_text(final=True)

    # ------------------------------------------------------------------ helpers

    @property
    def state(self) -> str:
        return self._state

    @property
    def reasoning(self) -> str:
        return self._reasoning

    def _toggle_reasoning(self) -> None:
        self._reason_visible = not self._reason_visible
        self._reason_box.setVisible(self._reason_visible and bool(self._reasoning))
        self._toggle.setText("hide reasoning" if self._reason_visible else "show reasoning")

    def _elapsed(self) -> float:
        end = self._end if self._end is not None else time.monotonic()
        return max(0.0, end - self._start)

    def _tick(self) -> None:
        self._spin_idx = (self._spin_idx + 1) % len(self._SPIN)
        self._spinner.setText(self._SPIN[self._spin_idx])
        self._update_text()

    def _update_text(
        self,
        final: bool = False,
        total_duration_ns: int = 0,
        load_duration_ns: int = 0,
    ) -> None:
        elapsed = self._elapsed()

        if self._state == self.CONNECTING:
            self._title.setText(f"@connecting to {self._model}" if self._model else "@connecting")
        elif self._state == self.THINKING:
            self._title.setText("@reasoning")
        elif self._state == self.GENERATING:
            self._title.setText("@generating")
        elif self._state == self.DONE:
            self._title.setText("@done")
        elif self._state == self.STOPPED:
            self._title.setText("@stopped")

        parts: list[str] = []
        if total_duration_ns:
            parts.append(f"total {total_duration_ns / 1_000_000_000:.2f}s")
        if load_duration_ns:
            parts.append(f"load {load_duration_ns / 1_000_000_000:.2f}s")
        parts.append(f"{elapsed:.1f}s")
        if self._tokens:
            parts.append(f"{self._tokens} tok")
        if self._tps:
            parts.append(f"{self._tps:.1f} tok/s")

        self._stats.setText("  ·  ".join(parts))

        if self._reasoning and self._reason_visible:
            self._reason_box.show()
            self._toggle.setVisible(True)
        elif not self._reasoning:
            self._reason_box.hide()
            self._toggle.setVisible(False)

        if final and self._state == self.DONE:
            self._spinner.setText("✔")
            if self._reasoning:
                self._reason_visible = False
                self._reason_box.hide()
                self._toggle.setText("show reasoning")
                self._toggle.setVisible(True)

    def _apply_state_style(self) -> None:
        self.setProperty("state", self._state)
        self.style().unpolish(self)
        self.style().polish(self)
        title = self.findChild(QLabel, "statusTitle")
        if title is not None:
            title.style().unpolish(title)
            title.style().polish(title)
