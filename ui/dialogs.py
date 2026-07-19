# ui/dialogs.py
import csv
import json
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QGroupBox,
    QDialogButtonBox, QMessageBox, QComboBox, QFormLayout, QScrollArea,
    QWidget, QLineEdit, QSpinBox, QDoubleSpinBox, QPushButton,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage

import cv2
import numpy as np

from core.games import all_games

GRADES = [
    "", "Gem Mint", "Mint", "Near Mint", "Excellent",
    "Very Good", "Good", "Played", "Poor",
]


class CardDetailDialog(QDialog):
    """Editable card detail: fields + image rotation, persisted on Save."""

    def __init__(self, card: Dict, valuations: List[Dict], db=None, parent=None):
        super().__init__(parent)
        self.card = card
        self.db = db
        self.card_id = card.get('id')
        self.setWindowTitle(f"Card #{self.card_id} - {card.get('name', 'Unknown')}")
        self.resize(960, 600)

        # In-memory image buffers + which sides were edited (need re-saving)
        self._imgs: Dict[str, Optional[np.ndarray]] = {'front': None, 'back': None}
        self._views: Dict[str, QLabel] = {}
        self._dirty: set = set()

        outer = QVBoxLayout(self)

        top = QHBoxLayout()
        top.setSpacing(10)

        # Image columns (front / back) with rotation controls
        for label, key, side in [("Front", 'front_scan_path', 'front'),
                                  ("Back", 'back_scan_path', 'back')]:
            top.addWidget(self._build_image_group(label, card.get(key), side))

        # Editable field form
        top.addWidget(self._build_form(card, valuations), 1)
        outer.addLayout(top)

        # Bottom button bar
        bar = QHBoxLayout()
        self._status = QLabel("")
        self._status.setStyleSheet("color: #8b8fa8; font-size: 12px;")
        bar.addWidget(self._status, 1)

        save_btn = QPushButton("💾 Save Changes")
        save_btn.setProperty("primary", True)
        save_btn.setMinimumHeight(36)
        save_btn.clicked.connect(self._save)
        bar.addWidget(save_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        bar.addWidget(close_btn)
        outer.addLayout(bar)

    # ── image group + rotation ────────────────────────────────────────────────

    def _build_image_group(self, label: str, path: Optional[str], side: str) -> QGroupBox:
        grp = QGroupBox(label)
        gl = QVBoxLayout(grp)
        gl.setSpacing(6)

        view = QLabel()
        view.setMinimumSize(200, 280)
        view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        view.setStyleSheet("background-color: #13151f; border: 1px solid #2a2d3e; border-radius: 6px;")
        self._views[side] = view

        if path and Path(path).exists():
            img = cv2.imread(path)
            if img is not None:
                self._imgs[side] = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self._refresh_view(side)

        gl.addWidget(view)

        # Rotation / straighten controls
        bar = QHBoxLayout()
        bar.setSpacing(4)
        for text, op, a11y in [("↺ 90°", 'ccw', f"Rotate {label} 90 degrees counter-clockwise"),
                               ("↻ 180°", '180', f"Rotate {label} 180 degrees"),
                               ("↻ 90°", 'cw', f"Rotate {label} 90 degrees clockwise"),
                               ("📐", 'deskew', f"Auto-straighten the {label} image")]:
            btn = QPushButton(text)
            btn.setMinimumHeight(28)
            btn.setToolTip(a11y)
            btn.setAccessibleName(a11y)
            btn.clicked.connect(lambda _=False, s=side, o=op: self._rotate(s, o))
            bar.addWidget(btn)
        # Disable controls if no image present
        has_img = self._imgs[side] is not None
        for i in range(bar.count()):
            w = bar.itemAt(i).widget()
            if w:
                w.setEnabled(has_img)
        gl.addLayout(bar)
        return grp

    def _rotate(self, side: str, op: str):
        from utils import image_ops
        img = self._imgs.get(side)
        if img is None:
            return
        fn = {
            'cw': image_ops.rotate_90_cw,
            'ccw': image_ops.rotate_90_ccw,
            '180': image_ops.rotate_180,
            'deskew': image_ops.deskew,
        }[op]
        self._imgs[side] = fn(img)
        self._dirty.add(side)
        self._refresh_view(side)
        self._status.setText(f"{side.capitalize()} image edited — Save to keep.")

    def _refresh_view(self, side: str):
        view = self._views[side]
        img = self._imgs.get(side)
        if img is None:
            view.setText("No image")
            return
        h, w = img.shape[:2]
        contiguous = np.ascontiguousarray(img)
        qimg = QImage(contiguous.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        view.setPixmap(QPixmap.fromImage(qimg).scaled(
            200, 280,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    # ── editable form ──────────────────────────────────────────────────────────

    def _build_form(self, card: Dict, valuations: List[Dict]) -> QWidget:
        from datetime import datetime
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)

        form_box = QGroupBox("Card Details")
        form = QFormLayout(form_box)

        self.name_edit = QLineEdit(card.get('name', '') or '')
        self.set_edit = QLineEdit(card.get('set_name', '') or '')
        self.num_edit = QLineEdit(card.get('card_number', '') or '')
        self.rarity_edit = QLineEdit(card.get('rarity', '') or '')

        self.game_combo = QComboBox()
        self.game_combo.addItems(all_games())
        g = card.get('game') or 'Other'
        gi = self.game_combo.findText(g)
        self.game_combo.setCurrentIndex(gi if gi >= 0 else self.game_combo.count() - 1)

        self.year_spin = QSpinBox()
        self.year_spin.setRange(0, datetime.now().year + 1)
        self.year_spin.setSpecialValueText("—")
        self.year_spin.setValue(int(card.get('year') or 0))

        self.grade_combo = QComboBox()
        self.grade_combo.addItems(GRADES)
        grade = card.get('condition_grade') or ''
        ci = self.grade_combo.findText(grade)
        self.grade_combo.setCurrentIndex(ci if ci >= 0 else 0)

        self.score_spin = QDoubleSpinBox()
        self.score_spin.setRange(0.0, 100.0)
        self.score_spin.setDecimals(1)
        self.score_spin.setValue(float(card.get('condition_score') or 0.0))

        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 9999)
        self.qty_spin.setValue(int(card.get('quantity') or 1))

        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0.0, 1_000_000.0)
        self.price_spin.setDecimals(2)
        self.price_spin.setPrefix("$")
        self.price_spin.setValue(float(card.get('purchase_price') or 0.0))

        self.value_spin = QDoubleSpinBox()
        self.value_spin.setRange(0.0, 1_000_000.0)
        self.value_spin.setDecimals(2)
        self.value_spin.setPrefix("$")
        self.value_spin.setValue(float(card.get('estimated_value') or 0.0))

        form.addRow("Name:", self.name_edit)
        form.addRow("Set:", self.set_edit)
        form.addRow("Card #:", self.num_edit)
        form.addRow("Rarity:", self.rarity_edit)
        form.addRow("Game:", self.game_combo)
        form.addRow("Year:", self.year_spin)
        form.addRow("Grade:", self.grade_combo)
        form.addRow("Score:", self.score_spin)
        form.addRow("Quantity:", self.qty_spin)
        form.addRow("Paid:", self.price_spin)
        form.addRow("Est. Value:", self.value_spin)

        self.notes_edit = QTextEdit(card.get('notes', '') or '')
        self.notes_edit.setMaximumHeight(70)
        form.addRow("Notes:", self.notes_edit)
        v.addWidget(form_box)

        # Defects + valuations (read-only reference)
        defects = json.loads(card.get('defects_json', '[]')) if card.get('defects_json') else []
        valuations = valuations or []
        defect_lines = "\n".join(f"• {d.get('type')} @ {d.get('location')}" for d in defects) or "None"
        val_lines = "\n".join(f"• {x['source']}: ${x['value']}" for x in valuations) or "None"

        ref = QTextEdit()
        ref.setReadOnly(True)
        ref.setMaximumHeight(120)
        ref.setHtml(f"<b>Detected defects</b><pre>{defect_lines}</pre>"
                    f"<b>Valuation history</b><pre>{val_lines}</pre>")
        v.addWidget(ref)
        return container

    # ── save ────────────────────────────────────────────────────────────────

    def _save(self):
        if self.db is None or self.card_id is None:
            QMessageBox.warning(self, "Cannot Save", "No database connection.")
            return

        # 1) Persist any rotated/straightened images back to their files
        for side in self._dirty:
            path = self.card.get(f'{side}_scan_path')
            img = self._imgs.get(side)
            if path and img is not None:
                try:
                    cv2.imwrite(path, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
                except Exception as exc:
                    QMessageBox.warning(self, "Image Save Failed",
                                        f"Could not write {side} image:\n{exc}")

        # 2) Persist field edits
        year = self.year_spin.value()
        updates = {
            'name':            self.name_edit.text().strip() or 'Unknown',
            'set_name':        self.set_edit.text().strip(),
            'card_number':     self.num_edit.text().strip(),
            'rarity':          self.rarity_edit.text().strip(),
            'game':            self.game_combo.currentText(),
            'year':            year if year > 0 else None,
            'condition_grade': self.grade_combo.currentText() or None,
            'condition_score': self.score_spin.value(),
            'quantity':        self.qty_spin.value(),
            'purchase_price':  self.price_spin.value(),
            'estimated_value': self.value_spin.value(),
            'notes':           self.notes_edit.toPlainText().strip(),
        }
        try:
            self.db.update_card(self.card_id, updates)
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))
            return

        self.accept()


class CsvMappingDialog(QDialog):
    """Map CSV column headers to card fields before batch import."""

    FIELDS = [
        ('name', 'Name *'),
        ('set_name', 'Set Name'),
        ('card_number', 'Card Number'),
        ('rarity', 'Rarity'),
        ('game', 'Game'),
        ('year', 'Year'),
        ('language', 'Language'),
        ('foil', 'Foil (1/0)'),
        ('condition_grade', 'Condition Grade'),
        ('condition_score', 'Condition Score'),
        ('estimated_value', 'Estimated Value'),
        ('purchase_price', 'Purchase Price'),
        ('quantity', 'Quantity'),
        ('notes', 'Notes'),
    ]

    def __init__(self, csv_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Map CSV Columns")
        self.resize(480, 500)
        self.mapping: Dict[str, str] = {}

        # Read CSV header
        try:
            with open(csv_path, newline='', encoding='utf-8') as f:
                headers = next(csv.reader(f), [])
        except Exception:
            headers = []

        options = ['(skip)'] + headers

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>CSV columns found:</b> {', '.join(headers) or 'none'}"))
        layout.addWidget(QLabel("Match each card field to the corresponding CSV column:"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QFormLayout(inner)

        self._combos: Dict[str, QComboBox] = {}
        for field, label in self.FIELDS:
            combo = QComboBox()
            combo.addItems(options)
            # Auto-select if header name matches field name
            for i, h in enumerate(headers):
                if h.lower().replace(' ', '_') == field:
                    combo.setCurrentIndex(i + 1)
                    break
            form.addRow(f"{label}:", combo)
            self._combos[field] = combo

        scroll.setWidget(inner)
        layout.addWidget(scroll)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _accept(self):
        self.mapping = {}
        for field, combo in self._combos.items():
            selected = combo.currentText()
            if selected != '(skip)':
                self.mapping[field] = selected
        if not self.mapping.get('name'):
            QMessageBox.warning(self, "Required", "You must map the 'Name' field.")
            return
        self.accept()