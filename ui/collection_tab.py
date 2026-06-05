"""
Collection Tab - Full implementation with search, stats, actions, and detail view.
Fixed: Input validation, safe operations, better error handling.
"""

import csv
from pathlib import Path
from typing import List, Dict, Optional

import os

import cv2

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox, QHeaderView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor

from core.database import Database
from core.valuator import CardValuator
from ui.dialogs import CardDetailDialog


APP_DIR = Path(os.environ.get('APPDATA', Path.home())) / "TradingCardManager"


class _SortItem(QTableWidgetItem):
    """Table item that sorts by an underlying value, not its display text.

    Lets numeric/date columns (price, score, qty, added) sort correctly
    instead of lexicographically (e.g. so $9 < $10, and 2 < 100).
    """
    def __init__(self, text: str, sort_key=None):
        super().__init__(text)
        self._sort_key = text if sort_key is None else sort_key

    def __lt__(self, other):
        if isinstance(other, _SortItem):
            try:
                return self._sort_key < other._sort_key
            except TypeError:
                return str(self._sort_key) < str(other._sort_key)
        return super().__lt__(other)


class RevalueWorker(QThread):
    """Background thread for re-valuating cards."""
    finished = pyqtSignal()
    
    def __init__(self, db: Database, valuator: CardValuator, ids: List[int]):
        super().__init__()
        self.db = db
        self.valuator = valuator
        self.ids = ids
    
    def run(self):
        for cid in self.ids:
            card = self.db.get_card(cid)
            if not card or not card.get('name'):
                continue
            try:
                summary = self.valuator.value_summary(
                    card['name'],
                    card.get('set_name'),
                    card.get('game'),
                    card.get('condition_grade'),
                    card.get('condition_score') or 85.0,
                )
                estimate = summary.get('estimated', 0.0)
                if estimate > 0:
                    self.db.update_card(cid, {'estimated_value': estimate})
            except Exception as e:
                print(f"Error re-valuing card {cid}: {e}")
        self.finished.emit()


class ReidentifyWorker(QThread):
    """Re-run vision identification on saved scans, then re-value."""
    progress = pyqtSignal(int, int)   # (done, total)
    finished = pyqtSignal(int)        # number of cards updated

    def __init__(self, db: Database, identifier, valuator: CardValuator,
                 ids: List[int]):
        super().__init__()
        self.db = db
        self.identifier = identifier
        self.valuator = valuator
        self.ids = ids

    @staticmethod
    def _load(path: Optional[str]):
        if not path or not Path(path).exists():
            return None
        img = cv2.imread(path)
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB) if img is not None else None

    def run(self):
        updated = 0
        total = len(self.ids)
        for i, cid in enumerate(self.ids):
            card = self.db.get_card(cid)
            if not card:
                self.progress.emit(i + 1, total)
                continue

            front = self._load(card.get('front_scan_path'))
            back = self._load(card.get('back_scan_path'))
            if front is None:
                self.progress.emit(i + 1, total)
                continue

            try:
                info = self.identifier.identify_card(front, back)
                # Only overwrite fields the model actually returned
                updates = {}
                for key in ('name', 'set_name', 'card_number', 'rarity', 'game'):
                    if info.get(key):
                        updates[key] = info[key]
                if info.get('year'):
                    updates['year'] = info['year']
                if updates:
                    self.db.update_card(cid, updates)
                    updated += 1

                # Re-value with the (possibly corrected) identity
                summary = self.valuator.value_summary(
                    updates.get('name', card.get('name')),
                    updates.get('set_name', card.get('set_name')),
                    updates.get('game', card.get('game')),
                    card.get('condition_grade'),
                    card.get('condition_score') or 85.0,
                )
                est = summary.get('estimated', 0.0)
                if est > 0:
                    self.db.update_card(cid, {'estimated_value': est})
            except Exception as e:
                print(f"Re-identify error for card {cid}: {e}")

            self.progress.emit(i + 1, total)
        self.finished.emit(updated)


class CollectionTab(QWidget):
    """Collection browser tab."""

    def __init__(self, db: Database, valuator: CardValuator, identifier=None):
        super().__init__()
        self.db = db
        self.valuator = valuator
        self.identifier = identifier
        self._revalue_worker = None
        self._reid_worker = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Toolbar
        bar = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔎 Search by name, set, game, or card number...")
        self.search_edit.textChanged.connect(self.refresh)

        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.refresh)

        self.revalue_btn = QPushButton("💰 Re-value Selected")
        self.revalue_btn.clicked.connect(self._revalue_selected)

        self.reid_btn = QPushButton("🔍 Re-identify Selected")
        self.reid_btn.setToolTip("Re-read name/set from the saved scans (uses the AI vision API), then re-value")
        self.reid_btn.clicked.connect(self._reidentify_selected)

        self.merge_btn = QPushButton("🔁 Merge Duplicates")
        self.merge_btn.setToolTip("Combine duplicate cards into one row with summed quantity")
        self.merge_btn.clicked.connect(self._merge_duplicates)

        self.delete_btn = QPushButton("🗑 Delete Selected")
        self.delete_btn.clicked.connect(self._delete_selected)

        self.export_btn = QPushButton("📤 Export CSV")
        self.export_btn.clicked.connect(self._export_csv)

        bar.addWidget(self.search_edit)
        bar.addWidget(self.refresh_btn)
        bar.addWidget(self.revalue_btn)
        bar.addWidget(self.reid_btn)
        bar.addWidget(self.merge_btn)
        bar.addWidget(self.delete_btn)
        bar.addWidget(self.export_btn)
        layout.addLayout(bar)

        # Statistics bar
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet(
            "background-color: #252840; color: #e8eaf0;"
            "padding: 10px 14px; border-radius: 6px; font-size: 13px;"
        )
        layout.addWidget(self.stats_label)

        # Main table
        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "ID", "Name", "Set", "Card #", "Game", "Grade",
            "Score", "Qty", "Unit Value", "Total Value", "Added"
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        # Click a column header to sort by it (toggles asc/desc)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.doubleClicked.connect(self._show_detail)
        layout.addWidget(self.table)

    def refresh(self):
        """Refresh table and statistics."""
        search = self.search_edit.text().strip() or None
        cards = self.db.get_all_cards(search)
        stats = self.db.get_collection_stats()

        self.stats_label.setText(
            f"📦 <b>{stats.get('total_cards', 0)}</b> unique • "
            f"<b>{stats.get('total_quantity', 0)}</b> total • "
            f"💰 <b>${stats.get('total_value', 0):,.2f}</b> • "
            f"Net: <b>${stats.get('total_value', 0) - stats.get('total_cost', 0):+,.2f}</b>"
        )

        # Disable sorting while repopulating, otherwise rows shuffle mid-insert
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(cards))
        for i, c in enumerate(cards):
            try:
                cid = int(c.get('id', 0) or 0)
            except (ValueError, TypeError):
                cid = 0
            qty = int(c.get('quantity', 1) or 1)
            val = float(c.get('estimated_value', 0) or 0)

            score = c.get('condition_score')
            try:
                score_val = float(score) if score is not None else -1.0
            except (ValueError, TypeError):
                score_val = -1.0
            score_display = f"{score_val:.1f}" if score_val >= 0 else "—"

            created = str(c.get('created_at', '') or '')

            # (display_text, sort_key) per column
            cells = [
                (str(cid),                          cid),
                (c.get('name', '') or '',           (c.get('name', '') or '').lower()),
                (c.get('set_name', '') or '',       (c.get('set_name', '') or '').lower()),
                (c.get('card_number', '') or '',    c.get('card_number', '') or ''),
                (c.get('game', '') or '',           (c.get('game', '') or '').lower()),
                (c.get('condition_grade', '') or "—", score_val),  # grade sorts by score
                (score_display,                     score_val),
                (str(qty),                          qty),
                (f"${val:.2f}",                     val),
                (f"${val * qty:.2f}",               val * qty),
                (created[:10],                      created),
            ]

            for j, (text, key) in enumerate(cells):
                item = _SortItem(text, key)
                if j == 6 and score_val >= 0:   # Score column colour coding
                    if score_val >= 90:
                        item.setForeground(QColor("#38a169"))
                    elif score_val >= 70:
                        item.setForeground(QColor("#d69e2e"))
                    else:
                        item.setForeground(QColor("#e53e3e"))
                self.table.setItem(i, j, item)

        self.table.setSortingEnabled(True)
                
    def _selected_ids(self) -> List[int]:
        """Get selected card IDs."""
        rows = {idx.row() for idx in self.table.selectedIndexes()}
        ids = []
        for r in rows:
            item = self.table.item(r, 0)
            if item:
                try:
                    ids.append(int(item.text()))
                except ValueError:
                    pass
        return ids

    def _delete_selected(self):
        ids = self._selected_ids()
        if not ids:
            return
        reply = QMessageBox.question(self, "Confirm Delete",
            f"Delete {len(ids)} selected card(s)? This cannot be undone.")
        if reply == QMessageBox.StandardButton.Yes:
            for cid in ids:
                self.db.delete_card(cid)
            self.refresh()

    def _reidentify_selected(self):
        """Re-run vision identification on the selected cards' saved scans."""
        ids = self._selected_ids()
        if not ids:
            return
        if self.identifier is None:
            QMessageBox.warning(self, "Unavailable",
                                "Identifier is not available.")
            return
        if self._reid_worker and self._reid_worker.isRunning():
            QMessageBox.warning(self, "In Progress", "Re-identification already running.")
            return

        reply = QMessageBox.question(
            self, "Re-identify Cards",
            f"Re-read name, set and details for {len(ids)} card(s) from their "
            f"saved scans, then re-value them?\n\n"
            f"This uses the AI vision API (~$0.006 per card) and will overwrite "
            f"the current text fields with what it reads.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.reid_btn.setEnabled(False)
        self.reid_btn.setText("⏳ Re-identifying…")
        self._reid_worker = ReidentifyWorker(self.db, self.identifier, self.valuator, ids)
        self._reid_worker.progress.connect(self._on_reid_progress)
        self._reid_worker.finished.connect(self._on_reid_finished)
        self._reid_worker.start()

    def _on_reid_progress(self, done: int, total: int):
        self.reid_btn.setText(f"⏳ Re-identifying… {done}/{total}")

    def _on_reid_finished(self, updated: int):
        self.reid_btn.setEnabled(True)
        self.reid_btn.setText("🔍 Re-identify Selected")
        self.refresh()
        QMessageBox.information(self, "Re-identify Complete",
                               f"Updated {updated} card(s) from their scans.")

    def _merge_duplicates(self):
        """Consolidate existing duplicate rows into single rows with summed qty."""
        reply = QMessageBox.question(
            self, "Merge Duplicates",
            "Combine duplicate cards (same name, set, card #, game, foil) into "
            "single rows with their quantities added together?\n\n"
            "This keeps the earliest copy and removes the extras. It cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        result = self.db.merge_existing_duplicates()
        self.refresh()
        if result['removed']:
            QMessageBox.information(
                self, "Merge Complete",
                f"🔁 Merged {result['removed']} duplicate row(s) into "
                f"{result['groups']} card(s).",
            )
        else:
            QMessageBox.information(self, "No Duplicates",
                                    "No duplicate cards were found.")

    def _revalue_selected(self):
        ids = self._selected_ids()
        if not ids:
            return
        if self._revalue_worker and self._revalue_worker.isRunning():
            QMessageBox.warning(self, "In Progress", "Re-valuation already in progress.")
            return
        
        self.revalue_btn.setEnabled(False)
        self.revalue_btn.setText("⏳ Re-valuing...")
        
        self._revalue_worker = RevalueWorker(self.db, self.valuator, ids)
        self._revalue_worker.finished.connect(self._on_revalue_finished)
        self._revalue_worker.start()
    
    def _on_revalue_finished(self):
        """Handle re-valuation completion."""
        self.revalue_btn.setEnabled(True)
        self.revalue_btn.setText("💰 Re-value Selected")
        self.refresh()
        QMessageBox.information(self, "Complete", "Re-valuation finished!")

    def _show_detail(self):
        ids = self._selected_ids()
        if not ids:
            return
        card = self.db.get_card(ids[0])
        if card:
            valuations = self.db.get_valuations(card['id'])
            dlg = CardDetailDialog(card, valuations, self.db, self)
            if dlg.exec():        # Saved — reflect edits in the table
                self.refresh()

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Collection", str(APP_DIR / "collection_export.csv"), "CSV (*.csv)")
        if not path:
            return

        cards = self.db.get_all_cards()
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'ID', 'Name', 'Set', 'Card Number', 'Rarity', 'Game', 'Year',
                    'Language', 'Foil', 'Grade', 'Score', 'Quantity',
                    'Estimated Value', 'Purchase Price', 'Total Value', 'Added'
                ])
                for c in cards:
                    qty = int(c.get('quantity', 1) or 1)
                    val = float(c.get('estimated_value', 0) or 0)
                    writer.writerow([
                        c.get('id'), c.get('name'), c.get('set_name'), c.get('card_number'),
                        c.get('rarity'), c.get('game'), c.get('year'),
                        c.get('language'), c.get('foil'), c.get('condition_grade'),
                        c.get('condition_score'), qty, val, c.get('purchase_price'),
                        val * qty, c.get('created_at')
                    ])
            QMessageBox.information(self, "Success", f"Exported to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))