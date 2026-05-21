"""
Collection Tab - Full implementation with search, stats, actions, and detail view.
Fixed: Input validation, safe operations, better error handling.
"""

import csv
from pathlib import Path
from typing import List, Dict

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox, QHeaderView
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor

from core.database import Database
from core.valuator import CardValuator
from ui.dialogs import CardDetailDialog


APP_DIR = Path(os.environ.get('APPDATA', Path.home())) / "TradingCardManager"


class CollectionTab(QWidget):
    """Collection browser tab."""

    def __init__(self, db: Database, valuator: CardValuator):
        super().__init__()
        self.db = db
        self.valuator = valuator
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

        self.delete_btn = QPushButton("🗑 Delete Selected")
        self.delete_btn.clicked.connect(self._delete_selected)

        self.export_btn = QPushButton("📤 Export CSV")
        self.export_btn.clicked.connect(self._export_csv)

        bar.addWidget(self.search_edit)
        bar.addWidget(self.refresh_btn)
        bar.addWidget(self.revalue_btn)
        bar.addWidget(self.delete_btn)
        bar.addWidget(self.export_btn)
        layout.addLayout(bar)

        # Statistics bar
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("""
            background: #2c5282; color: white;
            padding: 12px; border-radius: 6px; font-size: 13px;
        """)
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

        self.table.setRowCount(len(cards))
        for i, c in enumerate(cards):
            qty = int(c.get('quantity', 1) or 1)
            val = float(c.get('estimated_value', 0) or 0)
            
            # Safe condition score handling
            score = c.get('condition_score')
            score_display = f"{float(score):.1f}" if score is not None else "—"

            cells = [
                str(c.get('id', '')),
                c.get('name', ''),
                c.get('set_name', ''),
                c.get('card_number', ''),
                c.get('game', ''),
                c.get('condition_grade', '') or "—",
                score_display,                    # Fixed here
                str(qty),
                f"${val:.2f}",
                f"${val * qty:.2f}",
                str(c.get('created_at', ''))[:10]
            ]

            for j, text in enumerate(cells):
                item = QTableWidgetItem(text)
                # Color coding for score
                if j == 6 and score is not None:   # Score column
                    try:
                        s = float(score)
                        if s >= 90:
                            item.setForeground(QColor("#38a169"))
                        elif s >= 70:
                            item.setForeground(QColor("#d69e2e"))
                        else:
                            item.setForeground(QColor("#e53e3e"))
                    except:
                        pass
                self.table.setItem(i, j, item)
                
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

    def _revalue_selected(self):
        ids = self._selected_ids()
        if not ids:
            return
        QMessageBox.information(self, "Re-valuing", f"Re-fetching values for {len(ids)} cards...")
        QTimer.singleShot(100, lambda: self._revalue_worker(ids))

    def _revalue_worker(self, ids: List[int]):
        for cid in ids:
            card = self.db.get_card(cid)
            if not card or not card.get('name'):
                continue
            results = self.valuator.fetch_all_values(card['name'], card.get('set_name'))
            if results:
                score = card.get('condition_score') or 85.0
                estimate = self.valuator.compute_estimate(results, score)
                self.db.update_card(cid, {'estimated_value': estimate})
        self.refresh()

    def _show_detail(self):
        ids = self._selected_ids()
        if not ids:
            return
        card = self.db.get_card(ids[0])
        if card:
            valuations = self.db.get_valuations(card['id'])
            dlg = CardDetailDialog(card, valuations, self)
            dlg.exec()

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