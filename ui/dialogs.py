# ui/dialogs.py
import csv
import json
from pathlib import Path
from typing import Dict, List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QGroupBox,
    QDialogButtonBox, QMessageBox, QComboBox, QFormLayout, QScrollArea,
    QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage

import cv2


class CardDetailDialog(QDialog):
    """Full card detail dialog with images and data."""

    def __init__(self, card: Dict, valuations: List[Dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Card #{card.get('id')} - {card.get('name', 'Unknown')}")
        self.resize(940, 700)

        layout = QHBoxLayout(self)

        # Images
        img_panel = QVBoxLayout()
        for label, key in [("Front", 'front_scan_path'), ("Back", 'back_scan_path')]:
            grp = QGroupBox(label)
            gl = QVBoxLayout(grp)
            view = QLabel()
            view.setMinimumSize(320, 440)
            view.setAlignment(Qt.AlignmentFlag.AlignCenter)
            view.setStyleSheet("background-color: #13151f; border: 1px solid #2a2d3e; border-radius: 6px;")

            path = card.get(key)
            if path and Path(path).exists():
                img = cv2.imread(path)
                if img is not None:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    h, w = img.shape[:2]
                    qimg = QImage(img.data, w, h, 3 * w, QImage.Format.Format_RGB888)
                    pixmap = QPixmap.fromImage(qimg).scaled(320, 440, Qt.AspectRatioMode.KeepAspectRatio)
                    view.setPixmap(pixmap)

            gl.addWidget(view)
            img_panel.addWidget(grp)

        layout.addLayout(img_panel)

        # Info
        right = QVBoxLayout()
        info = QTextEdit()
        info.setReadOnly(True)

        defects = json.loads(card.get('defects_json', '[]')) if card.get('defects_json') else []
        valuations = valuations or []

        # Fixed: pre-compute lines to avoid backslash in f-string (BUG-5)
        defect_lines = "\n".join([f"• {d.get('type')} @ {d.get('location')}" for d in defects]) or "None"
        val_lines = "\n".join([f"• {v['source']}: ${v['value']}" for v in valuations]) or "None"

        info.setHtml(f"""
            <h2>{card.get('name')}</h2>
            <p><b>Set:</b> {card.get('set_name')}<br>
               <b>Number:</b> {card.get('card_number')}<br>
               <b>Grade:</b> {card.get('condition_grade')} ({card.get('condition_score')}/100)</p>
            <h3>Defects</h3>
            <pre>{defect_lines}</pre>
            <h3>Valuations</h3>
            <pre>{val_lines}</pre>
        """)

        right.addWidget(info)
        btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn.rejected.connect(self.reject)
        right.addWidget(btn)

        layout.addLayout(right)


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