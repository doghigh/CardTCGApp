"""Store review prompt dialog.

Shown at most twice per user — see core/review_prompt.py for the policy. Every
exit path resolves the prompt exactly once, including closing via the window X.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)

from core import review_prompt, usage


class ReviewPromptDialog(QDialog):
    """Ask the user to review Lorebox on the Microsoft Store."""

    def __init__(self, card_count: int, parent=None):
        super().__init__(parent)
        self._resolved = False
        self.setWindowTitle("Rate Lorebox")
        self.setMinimumWidth(460)

        v = QVBoxLayout(self)
        v.setSpacing(12)
        v.setContentsMargins(22, 22, 22, 22)

        msg = QLabel(
            "<b>Getting value out of Lorebox?</b><br><br>"
            "Reviews on the Microsoft Store are the main way other collectors "
            "find it. Takes about a minute."
        )
        msg.setWordWrap(True)
        v.addWidget(msg)

        row = QHBoxLayout()
        never_btn = QPushButton("Don't ask again")
        never_btn.clicked.connect(self._never)
        row.addWidget(never_btn)
        row.addStretch()

        later_btn = QPushButton("Not now")
        later_btn.clicked.connect(self._later)
        row.addWidget(later_btn)

        rate_btn = QPushButton("Rate Lorebox")
        rate_btn.setProperty("primary", True)
        rate_btn.setDefault(True)
        rate_btn.clicked.connect(self._rate)
        row.addWidget(rate_btn)
        v.addLayout(row)

    def _decline(self, permanent: bool):
        """Resolve as a decline, exactly once."""
        if self._resolved:
            return
        self._resolved = True
        review_prompt.mark_declined(permanent=permanent)
        usage.log_event("review_prompt_declined", permanent=permanent)

    def _rate(self):
        self._resolved = True
        review_prompt.mark_rated()
        usage.log_event("review_prompt_rated", source="prompt")
        review_prompt.open_store_review()
        self.accept()

    def _later(self):
        self._decline(permanent=False)
        self.reject()

    def _never(self):
        self._decline(permanent=True)
        self.reject()

    def reject(self):
        """Every dismissal funnels here: Escape, the window X, and both buttons.

        Overriding reject() rather than closeEvent() is deliberate. Escape does
        NOT emit a close event — QDialog routes it straight to reject() — so a
        closeEvent override silently misses it. The window X does emit one, but
        QDialog.closeEvent's default implementation then calls reject(), so this
        single override covers every path. Verified:
            ESCAPE  -> ['reject']
            CLOSE/X -> ['closeEvent', 'reject']
        """
        self._decline(permanent=False)
        super().reject()
