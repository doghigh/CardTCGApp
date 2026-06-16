"""
Batch Review Dialog — processes all scanned cards in parallel, then shows
a review table where the user can edit fields and save everything at once.
"""

import cv2
import logging
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import os

import numpy as np
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QWidget, QAbstractItemView, QComboBox, QSizePolicy,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QImage, QColor

from core.identifier import CardIdentifier
from core.inspector import CardInspector
from core.valuator import CardValuator
from core.database import Database

SCANS_DIR = Path(os.environ.get('APPDATA', Path.home())) / "Lorebox" / "scans" / "cards"
SCANS_DIR.mkdir(parents=True, exist_ok=True)

GAMES = [
    "Baseball", "Basketball", "Football", "Hockey", "Sports Cards",
    "Magic: The Gathering", "Pokémon", "Yu-Gi-Oh!", "One Piece",
    "Lorcana", "Flesh and Blood", "Non-Sport", "Other",
]

COL_CHECK = 0
COL_THUMB = 1
COL_NAME  = 2
COL_SET   = 3
COL_NUM   = 4
COL_GAME  = 5
COL_YEAR  = 6
COL_GRADE = 7
COL_VALUE = 8
NCOLS     = 9


# ── Background worker ─────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

class BatchProcessWorker(QThread):
    card_ready = pyqtSignal(int, dict)   # (index, result_dict)
    progress   = pyqtSignal(int, int)    # (done, total)
    finished   = pyqtSignal()

    def __init__(self, chunks: List[List[np.ndarray]],
                 identifier: CardIdentifier,
                 inspector:  CardInspector,
                 valuator:   CardValuator):
        super().__init__()
        self.chunks     = chunks
        self.identifier = identifier
        self.inspector  = inspector
        self.valuator   = valuator
        self._done      = 0

    def run(self):
        total = len(self.chunks)
        # Use up to 4 threads — Claude vision is I/O bound
        with ThreadPoolExecutor(max_workers=min(4, total)) as pool:
            futures = {
                pool.submit(self._process, i, chunk): i
                for i, chunk in enumerate(self.chunks)
            }
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = self._empty_result(idx, str(exc))
                self._done += 1
                self.card_ready.emit(idx, result)
                self.progress.emit(self._done, total)
        self.finished.emit()

    def _process(self, idx: int, chunk: List[np.ndarray]) -> dict:
        from utils.image_ops import deskew

        # Auto-straighten before identification/grading — improves both
        chunk = [deskew(im) for im in chunk]
        front = chunk[0]
        back  = chunk[1] if len(chunk) > 1 else None

        info       = self.identifier.identify_card(front, back)
        inspection = self.inspector.inspect(front)
        valuation  = self.valuator.value_summary(
            info.get('name', '') or '',
            info.get('set_name'),
            info.get('game'),
            inspection.get('grade'),
            inspection.get('score', 85.0),
        )

        return {
            'index':      idx,
            'images':     chunk,
            'name':       info.get('name') or '',
            'set_name':   info.get('set_name') or '',
            'card_number':info.get('card_number') or '',
            'game':       info.get('game') or 'Other',
            'year':       info.get('year') or datetime.now().year,
            'rarity':     info.get('rarity') or '',
            'grade':      inspection.get('grade', ''),
            'score':      inspection.get('score', 0.0),
            'defects':    inspection.get('defects', []),
            'estimated_value': valuation.get('estimated', 0.0),
            'val_source': valuation.get('source', ''),
        }

    @staticmethod
    def _empty_result(idx: int, error: str) -> dict:
        return {
            'index': idx, 'images': [], 'name': '', 'set_name': '',
            'card_number': '', 'game': 'Other', 'year': datetime.now().year,
            'rarity': '', 'grade': '', 'score': 0.0, 'defects': [],
            'estimated_value': 0.0, 'val_source': f'Error: {error}',
        }


# ── Main dialog ───────────────────────────────────────────────────────────────

class BatchReviewDialog(QDialog):
    """
    Two-phase dialog:
      Phase 1 — shows a progress bar while the worker processes all cards.
      Phase 2 — shows an editable review table; user saves with one click.
    """

    def __init__(self, chunks: List[List[np.ndarray]],
                 db: Database,
                 identifier: CardIdentifier,
                 inspector:  CardInspector,
                 valuator:   CardValuator,
                 parent=None):
        super().__init__(parent)
        self.chunks     = chunks
        self.db         = db
        self.identifier = identifier
        self.inspector  = inspector
        self.valuator   = valuator

        self._results: dict[int, dict] = {}   # index → result
        self._total = len(chunks)

        self.setWindowTitle(f"Batch Review — {self._total} card(s)")
        self.setMinimumSize(1100, 680)
        self.setModal(True)

        self._build_progress_phase()
        self._start_worker()

    # ── Phase 1: progress ────────────────────────────────────────────────────

    def _build_progress_phase(self):
        self._root = QVBoxLayout(self)
        self._root.setSpacing(16)
        self._root.setContentsMargins(24, 24, 24, 24)

        self._phase_label = QLabel(
            f"<b>Processing {self._total} cards…</b><br>"
            "Identifying and valuing each card in parallel. This may take a moment."
        )
        self._phase_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._root.addWidget(self._phase_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, self._total)
        self._progress.setValue(0)
        self._progress.setMinimumHeight(10)
        self._root.addWidget(self._progress)

        self._prog_detail = QLabel("Starting…")
        self._prog_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._prog_detail.setStyleSheet("color: #8b8fa8; font-size: 12px;")
        self._root.addWidget(self._prog_detail)

        # Placeholder for review table (hidden until phase 2)
        self._table_widget = QWidget()
        self._table_widget.setVisible(False)
        self._root.addWidget(self._table_widget, 1)

        # Bottom buttons (hidden until phase 2)
        self._btn_bar = QHBoxLayout()
        self._root.addLayout(self._btn_bar)

    def _start_worker(self):
        self._worker = BatchProcessWorker(
            self.chunks, self.identifier, self.inspector, self.valuator
        )
        self._worker.card_ready.connect(self._on_card_ready)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_all_done)
        self._worker.start()

    def _on_progress(self, done: int, total: int):
        self._progress.setValue(done)
        self._prog_detail.setText(f"Processed {done} of {total} cards…")

    def _on_card_ready(self, idx: int, result: dict):
        self._results[idx] = result

    def _on_all_done(self):
        self._switch_to_review()

    # ── Phase 2: review table ────────────────────────────────────────────────

    def _switch_to_review(self):
        # Remove progress widgets
        while self._root.count():
            item = self._root.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Header
        header = QHBoxLayout()
        title = QLabel(f"<b>Review {self._total} Card(s)</b>")
        title.setStyleSheet("font-size: 16px;")
        header.addWidget(title)
        header.addStretch()

        rotate_btn = QPushButton("↻ Rotate Row")
        rotate_btn.setToolTip("Rotate the selected row's image 90° clockwise")
        rotate_btn.clicked.connect(self._rotate_selected_row)
        straighten_btn = QPushButton("📐 Straighten Row")
        straighten_btn.setToolTip("Auto-correct skew on the selected row's image")
        straighten_btn.clicked.connect(self._straighten_selected_row)
        header.addWidget(rotate_btn)
        header.addWidget(straighten_btn)

        select_all_btn = QPushButton("☑ Select All")
        select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        deselect_btn   = QPushButton("☐ Deselect All")
        deselect_btn.clicked.connect(lambda: self._set_all_checked(False))
        header.addWidget(select_all_btn)
        header.addWidget(deselect_btn)
        self._root.addLayout(header)

        # Hint
        hint = QLabel(
            "Edit any field directly in the table.  "
            "Uncheck cards you want to skip.  "
            "Click <b>Save Selected</b> when ready."
        )
        hint.setStyleSheet("color: #8b8fa8; font-size: 12px;")
        self._root.addWidget(hint)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(NCOLS)
        self._table.setHorizontalHeaderLabels([
            "", "Preview", "Name", "Set", "Card #",
            "Game", "Year", "Grade", "Est. Value",
        ])
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setSectionResizeMode(COL_THUMB, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(COL_NAME,  QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(COL_SET,   QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(COL_GAME,  QHeaderView.ResizeMode.ResizeToContents)
        self._table.setColumnWidth(COL_CHECK, 30)
        self._table.setColumnWidth(COL_THUMB, 60)
        self._table.setColumnWidth(COL_NUM,   70)
        self._table.setColumnWidth(COL_YEAR,  60)
        self._table.setColumnWidth(COL_GRADE, 90)
        self._table.setColumnWidth(COL_VALUE, 90)
        self._table.setRowCount(self._total)
        self._table.setIconSize(QSize(50, 70))
        self._table.verticalHeader().setDefaultSectionSize(76)
        self._root.addWidget(self._table, 1)

        # Populate rows in index order
        for idx in sorted(self._results.keys()):
            self._populate_row(idx, self._results[idx])

        # Bottom bar
        bottom = QHBoxLayout()
        self._status = QLabel("")
        self._status.setStyleSheet("color: #8b8fa8; font-size: 12px;")
        bottom.addWidget(self._status)
        bottom.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(cancel_btn)

        self._save_btn = QPushButton("💾 Save Selected")
        self._save_btn.setProperty("primary", True)
        self._save_btn.setMinimumHeight(40)
        self._save_btn.setMinimumWidth(160)
        self._save_btn.clicked.connect(self._save_selected)
        bottom.addWidget(self._save_btn)

        self._root.addLayout(bottom)
        self._update_status()

    def _populate_row(self, row: int, r: dict):
        # Checkbox
        chk = QCheckBox()
        chk.setChecked(True)
        chk.stateChanged.connect(self._update_status)
        chk_widget = QWidget()
        chk_layout = QHBoxLayout(chk_widget)
        chk_layout.addWidget(chk)
        chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chk_layout.setContentsMargins(0, 0, 0, 0)
        self._table.setCellWidget(row, COL_CHECK, chk_widget)

        # Thumbnail
        images = r.get('images', [])
        if images:
            thumb = self._make_thumb(images[0], 50, 70)
            lbl = QLabel()
            lbl.setPixmap(thumb)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setCellWidget(row, COL_THUMB, lbl)

        # Editable text cells
        for col, key in [(COL_NAME, 'name'), (COL_SET, 'set_name'), (COL_NUM, 'card_number')]:
            item = QTableWidgetItem(str(r.get(key) or ''))
            self._table.setItem(row, col, item)

        # Game combo
        game_combo = QComboBox()
        game_combo.addItems(GAMES)
        game = r.get('game') or 'Other'
        idx = game_combo.findText(game)
        game_combo.setCurrentIndex(idx if idx >= 0 else game_combo.count() - 1)
        self._table.setCellWidget(row, COL_GAME, game_combo)

        # Year
        year_item = QTableWidgetItem(str(r.get('year') or ''))
        self._table.setItem(row, COL_YEAR, year_item)

        # Grade (read-only, colored)
        grade = r.get('grade', '')
        score = r.get('score', 0.0)
        grade_item = QTableWidgetItem(f"{grade}\n{score:.0f}/100")
        grade_item.setFlags(grade_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        grade_item.setForeground(QColor(self._grade_color(grade)))
        self._table.setItem(row, COL_GRADE, grade_item)

        # Value (read-only)
        est = r.get('estimated_value', 0.0)
        val_item = QTableWidgetItem(f"${est:.2f}")
        val_item.setFlags(val_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._table.setItem(row, COL_VALUE, val_item)

    def _make_thumb(self, img: np.ndarray, w: int, h: int) -> QPixmap:
        try:
            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
            qimg = QImage(img.data, img.shape[1], img.shape[0],
                          3 * img.shape[1], QImage.Format.Format_RGB888)
            return QPixmap.fromImage(qimg).scaled(
                w, h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        except Exception:
            return QPixmap()

    @staticmethod
    def _grade_color(grade: str) -> str:
        return {
            'Gem Mint': '#43b581', 'Mint': '#43b581', 'Near Mint': '#43b581',
            'Excellent': '#faa61a', 'Very Good': '#faa61a',
            'Good': '#ed4245', 'Played': '#ed4245', 'Poor': '#ed4245',
        }.get(grade, '#8b8fa8')

    def _get_checkbox(self, row: int) -> Optional[QCheckBox]:
        w = self._table.cellWidget(row, COL_CHECK)
        if w:
            for child in w.findChildren(QCheckBox):
                return child
        return None

    def _set_all_checked(self, checked: bool):
        for row in range(self._table.rowCount()):
            chk = self._get_checkbox(row)
            if chk:
                chk.setChecked(checked)

    def _update_status(self):
        if not hasattr(self, '_table'):
            return
        selected = sum(
            1 for row in range(self._table.rowCount())
            if (chk := self._get_checkbox(row)) and chk.isChecked()
        )
        self._status.setText(f"{selected} of {self._total} cards selected")

    # ── Row image transforms ─────────────────────────────────────────────────

    def _rotate_selected_row(self):
        self._transform_selected_row('cw')

    def _straighten_selected_row(self):
        self._transform_selected_row('deskew')

    def _transform_selected_row(self, op: str):
        from utils import image_ops
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.information(self, "No Selection",
                                    "Click a row first, then rotate/straighten.")
            return

        result = self._results.get(row)
        if not result or not result.get('images'):
            return

        fn = {'cw': image_ops.rotate_90_cw,
              'deskew': image_ops.deskew}[op]
        result['images'] = [fn(im) for im in result['images']]

        # Refresh the thumbnail in place
        thumb = self._make_thumb(result['images'][0], 50, 70)
        lbl = self._table.cellWidget(row, COL_THUMB)
        if isinstance(lbl, QLabel):
            lbl.setPixmap(thumb)

    # ── Save ─────────────────────────────────────────────────────────────────

    def _save_selected(self):
        saved = 0
        merged = 0
        errors = 0
        timestamp_base = datetime.now().strftime("%Y%m%d_%H%M%S")

        for row in range(self._table.rowCount()):
            chk = self._get_checkbox(row)
            if not chk or not chk.isChecked():
                continue

            result = self._results.get(row, {})
            images = result.get('images', [])

            try:
                # Read current field values from table
                name  = (self._table.item(row, COL_NAME)  or QTableWidgetItem('')).text().strip()
                set_n = (self._table.item(row, COL_SET)   or QTableWidgetItem('')).text().strip()
                num   = (self._table.item(row, COL_NUM)   or QTableWidgetItem('')).text().strip()
                year_t = (self._table.item(row, COL_YEAR) or QTableWidgetItem('')).text().strip()
                game_w = self._table.cellWidget(row, COL_GAME)
                game  = game_w.currentText() if game_w else result.get('game', 'Other')

                try:
                    year = int(year_t)
                except (ValueError, TypeError):
                    year = result.get('year', datetime.now().year)

                card_data = {
                    'name':            name or result.get('name', 'Unknown'),
                    'set_name':        set_n or result.get('set_name'),
                    'card_number':     num   or result.get('card_number'),
                    'rarity':          result.get('rarity'),
                    'game':            game,
                    'year':            year,
                    'language':        'English',
                    'foil':            0,
                    'condition_grade': result.get('grade'),
                    'condition_score': result.get('score'),
                    'defects':         result.get('defects', []),
                    'estimated_value': result.get('estimated_value', 0.0),
                    'purchase_price':  0.0,
                    'quantity':        1,
                }

                # If this merges into an existing card, skip writing image files
                # (they'd be orphaned — the original card keeps its scans).
                is_dup = self.db.find_duplicate(card_data) is not None
                if not is_dup and images:
                    ts = f"{timestamp_base}_{row:03d}"
                    front_path = str(SCANS_DIR / f"{ts}_front.png")
                    cv2.imwrite(front_path, cv2.cvtColor(images[0], cv2.COLOR_RGB2BGR))
                    card_data['front_scan_path'] = front_path
                    if len(images) > 1:
                        back_path = str(SCANS_DIR / f"{ts}_back.png")
                        cv2.imwrite(back_path, cv2.cvtColor(images[1], cv2.COLOR_RGB2BGR))
                        card_data['back_scan_path'] = back_path

                self.db.add_card(card_data)
                if is_dup:
                    merged += 1
                else:
                    saved += 1

                # Dim the row to show it's been handled
                for col in range(NCOLS):
                    item = self._table.item(row, col)
                    if item:
                        item.setForeground(QColor('#4a4d60'))
                if chk:
                    chk.setEnabled(False)

            except Exception as exc:
                errors += 1
                logger.warning("Save error row %s: %s", row, exc)

        msg = f"✅ Saved {saved} new card(s)."
        if merged:
            msg += f"\n🔁 {merged} duplicate(s) merged into existing cards (quantity increased)."
        if errors:
            msg += f"\n⚠ {errors} error(s) — check console."
        QMessageBox.information(self, "Batch Save Complete", msg)
        self.accept()
