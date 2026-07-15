# ui/regrade_dialog.py
"""Re-grade existing cards with the current grader (vision, CV fallback).

Shows a cost estimate + confirm, then re-runs grading on every card that has a
readable front scan, applying ONLY the condition fields (name/set untouched).
Stops and asks for a key if the free trial is exhausted mid-run.
"""
import os

import cv2
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QMessageBox
)

from core.grading import resolve_condition

COST_PER_CARD = 0.006


class _RegradeWorker(QThread):
    progress = pyqtSignal(int, int)          # done, total
    trial_blocked = pyqtSignal(str)          # source marker
    finished_ok = pyqtSignal(int, int)       # regraded, skipped

    def __init__(self, db, identifier, inspector, card_ids):
        super().__init__()
        self.db, self.identifier, self.inspector = db, identifier, inspector
        self.card_ids = card_ids
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        regraded = skipped = 0
        total = len(self.card_ids)
        for i, cid in enumerate(self.card_ids):
            if self._cancel:
                break
            card = self.db.get_card(cid)
            fp = card.get('front_scan_path') if card else None
            if not fp or not os.path.exists(fp):
                skipped += 1
                self.progress.emit(i + 1, total)
                continue
            front = cv2.cvtColor(cv2.imread(fp), cv2.COLOR_BGR2RGB)
            back = None
            bp = card.get('back_scan_path')
            if bp and os.path.exists(bp):
                back = cv2.cvtColor(cv2.imread(bp), cv2.COLOR_BGR2RGB)
            info = self.identifier.identify_card(front, back)
            if str(info.get('source', '')).startswith('trial_'):
                self.trial_blocked.emit(info['source'])
                return
            cond = resolve_condition(info, front, self.inspector)
            self.db.update_card(cid, {
                'condition_grade': cond['grade'],
                'condition_score': cond['score'],
                'defects': cond['defects'],
            })
            regraded += 1
            self.progress.emit(i + 1, total)
        self.finished_ok.emit(regraded, skipped)


class RegradeDialog(QDialog):
    trial_blocked = pyqtSignal(str)          # bubble up to MainWindow to open key dialog

    def __init__(self, db, identifier, inspector, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Re-grade collection")
        self.setMinimumWidth(420)
        self._db, self._identifier, self._inspector = db, identifier, inspector
        self._worker = None

        cards = db.get_all_cards()
        self._ids = [c['id'] for c in cards if c.get('front_scan_path')]
        n = len(self._ids)

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(12)
        v.addWidget(QLabel(
            f"<b>Re-grade {n} cards</b> with the current grader "
            f"(Claude vision, falling back to offline analysis).<br><br>"
            f"Vision grading costs about ${COST_PER_CARD:.3f}/card "
            f"(~${n * COST_PER_CARD:.2f} total, via your free trial or your own key). "
            f"Only condition is updated — names and sets are left alone."
        ))
        self._status = QLabel("")
        self._status.setWordWrap(True)
        v.addWidget(self._status)
        self._bar = QProgressBar()
        self._bar.setMaximum(max(1, n))
        self._bar.setVisible(False)
        v.addWidget(self._bar)

        row = QHBoxLayout()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)
        row.addWidget(self._cancel_btn)
        row.addStretch()
        self._start_btn = QPushButton("Re-grade")
        self._start_btn.setProperty("primary", True)
        self._start_btn.setDefault(True)
        self._start_btn.setEnabled(n > 0)
        self._start_btn.clicked.connect(self._start)
        row.addWidget(self._start_btn)
        v.addLayout(row)

    def _start(self):
        self._start_btn.setEnabled(False)
        self._bar.setVisible(True)
        self._status.setText("Re-grading…")
        self._worker = _RegradeWorker(self._db, self._identifier, self._inspector, self._ids)
        self._worker.progress.connect(lambda d, t: self._bar.setValue(d))
        self._worker.finished_ok.connect(self._done)
        self._worker.trial_blocked.connect(self._on_trial_blocked)
        self._worker.start()

    def _on_cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
        else:
            self.reject()

    def _done(self, regraded, skipped):
        self._status.setText(f"Done — {regraded} re-graded, {skipped} skipped (no scan on disk).")
        self._start_btn.setEnabled(False)
        self._cancel_btn.setText("Close")

    def _on_trial_blocked(self, source):
        self._status.setText("Free trial used up — add your own key to finish re-grading.")
        self._start_btn.setEnabled(True)
        self.trial_blocked.emit(source)
