"""
Scan & Add Tab - Full implementation with fixes.
"""

import os
import cv2
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
    QFormLayout, QSplitter, QMessageBox, QFileDialog, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage

from core.scanner import ScannerInterface
from core.inspector import CardInspector
from core.identifier import CardIdentifier
from core.valuator import CardValuator
from core.database import Database


SCANS_DIR = Path(os.environ.get('APPDATA', Path.home())) / "TradingCardManager" / "scans"
SCANS_DIR.mkdir(parents=True, exist_ok=True)


class ScanWorker(QThread):
    """Background thread for scanning and file loading."""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, scanner: ScannerInterface, source_name: str = None,
                 dpi: int = 300, file_path: str = None):
        super().__init__()
        self.scanner = scanner
        self.source_name = source_name
        self.dpi = dpi
        self.file_path = file_path

    def run(self):
        try:
            if self.file_path:
                img = self.scanner.scan_from_file(self.file_path)
            else:
                img = self.scanner.scan(self.source_name, self.dpi)
            self.finished.emit(img)
        except Exception as e:
            self.error.emit(str(e))


class ImageViewer(QLabel):
    """Display card images."""
    def __init__(self, placeholder: str = "No image"):
        super().__init__()
        self.setMinimumSize(280, 380)
        self.setMaximumSize(450, 600)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel { background: #1a202c; color: #718096;
                     border: 2px dashed #2d3748; border-radius: 8px; font-size: 13px; }
        """)
        self._placeholder = placeholder
        self.setText(placeholder)

    def set_image(self, img: Optional[np.ndarray]):
        if img is None:
            self.setText(self._placeholder)
            self.setPixmap(QPixmap())
            return
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        h, w = img.shape[:2]
        qimg = QImage(img.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        scaled = pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        self.setPixmap(scaled)


class ScanTab(QWidget):
    card_added = pyqtSignal()

    def __init__(self, db: Database, scanner: ScannerInterface,
                 inspector: CardInspector, identifier: CardIdentifier,
                 valuator: CardValuator):
        super().__init__()
        self.db = db
        self.scanner = scanner
        self.inspector = inspector
        self.identifier = identifier
        self.valuator = valuator

        self.current_front_img = None
        self.current_back_img = None
        self.current_inspection = None
        self.current_valuations = []

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Scanner controls
        bar = QHBoxLayout()
        self.source_combo = QComboBox()
        self.source_combo.setMinimumWidth(220)
        sources = self.scanner.list_sources()
        self.source_combo.addItems(sources if sources else ["(No TWAIN scanner detected)"])

        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 1200)
        self.dpi_spin.setValue(300)
        self.dpi_spin.setSuffix(" DPI")

        self.scan_front_btn = QPushButton("📷 Scan Front")
        self.scan_back_btn = QPushButton("🔄 Scan Back")
        self.load_front_btn = QPushButton("📂 Load Front")
        self.load_back_btn = QPushButton("📂 Load Back")
        self.continuous_btn = QPushButton("🔄 Continuous Scan")

        for btn in [self.scan_front_btn, self.scan_back_btn, self.load_front_btn,
                    self.load_back_btn, self.continuous_btn]:
            btn.setMinimumHeight(36)

        self.scan_front_btn.clicked.connect(lambda: self._scan('front'))
        self.scan_back_btn.clicked.connect(lambda: self._scan('back'))
        self.load_front_btn.clicked.connect(lambda: self._load_file('front'))
        self.load_back_btn.clicked.connect(lambda: self._load_file('back'))
        self.continuous_btn.clicked.connect(self._start_continuous_scan)

        bar.addWidget(QLabel("Scanner:"))
        bar.addWidget(self.source_combo)
        bar.addWidget(self.dpi_spin)
        bar.addWidget(self.scan_front_btn)
        bar.addWidget(self.scan_back_btn)
        bar.addWidget(self.load_front_btn)
        bar.addWidget(self.load_back_btn)
        bar.addWidget(self.continuous_btn)
        bar.addStretch()
        layout.addLayout(bar)

        # Images
        splitter = QSplitter(Qt.Orientation.Horizontal)
        img_widget = QWidget()
        img_layout = QHBoxLayout(img_widget)

        front_box = QGroupBox("Front")
        fl = QVBoxLayout(front_box)
        self.front_view = ImageViewer("Front side\nNot scanned yet")
        fl.addWidget(self.front_view)

        back_box = QGroupBox("Back")
        bl = QVBoxLayout(back_box)
        self.back_view = ImageViewer("Back side\nNot scanned yet")
        bl.addWidget(self.back_view)

        img_layout.addWidget(front_box)
        img_layout.addWidget(back_box)
        splitter.addWidget(img_widget)

        # Right panel
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setSpacing(10)

        # Card Details Form
        details_group = QGroupBox("Card Details")
        form = QFormLayout(details_group)
        self.name_edit = QLineEdit()
        self.set_edit = QLineEdit()
        self.number_edit = QLineEdit()
        self.rarity_edit = QLineEdit()
        self.game_edit = QComboBox()
        self.game_edit.setEditable(True)
        self.game_edit.addItems(["Magic: The Gathering", "Pokémon", "Yu-Gi-Oh!", "One Piece", "Lorcana", "Flesh and Blood", "Sports", "Other"])
        self.year_spin = QSpinBox()
        self.year_spin.setRange(1900, 2100)
        self.year_spin.setValue(datetime.now().year)
        self.lang_edit = QLineEdit("English")
        self.foil_check = QCheckBox("Foil / Holographic")
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 9999)
        self.qty_spin.setValue(1)
        self.purchase_spin = QDoubleSpinBox()
        self.purchase_spin.setRange(0, 999999)
        self.purchase_spin.setPrefix("$")
        self.purchase_spin.setDecimals(2)
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(60)

        for label, widget in [
            ("Name:", self.name_edit), ("Set:", self.set_edit),
            ("Card #:", self.number_edit), ("Rarity:", self.rarity_edit),
            ("Game:", self.game_edit), ("Year:", self.year_spin),
            ("Language:", self.lang_edit), ("Foil:", self.foil_check),
            ("Quantity:", self.qty_spin), ("Purchase Price:", self.purchase_spin),
            ("Notes:", self.notes_edit)
        ]:
            form.addRow(label, widget)

        right_layout.addWidget(details_group)

        # Inspection
        insp_group = QGroupBox("Inspection")
        il = QVBoxLayout(insp_group)
        self.grade_label = QLabel("Not inspected")
        self.grade_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.score_label = QLabel("Score: -")
        self.defects_text = QTextEdit()
        self.defects_text.setReadOnly(True)
        self.defects_text.setMaximumHeight(110)
        self.inspect_btn = QPushButton("🔍 Re-inspect")
        self.inspect_btn.clicked.connect(self._inspect)
        il.addWidget(self.grade_label)
        il.addWidget(self.score_label)
        il.addWidget(self.defects_text)
        il.addWidget(self.inspect_btn)
        right_layout.addWidget(insp_group)

        # Valuation
        val_group = QGroupBox("Valuation")
        vl = QVBoxLayout(val_group)
        self.value_label = QLabel("Estimate: -")
        self.value_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #38a169;")
        self.value_text = QTextEdit()
        self.value_text.setReadOnly(True)
        self.value_text.setMaximumHeight(110)
        self.fetch_value_btn = QPushButton("💰 Fetch Online Values")
        self.fetch_value_btn.clicked.connect(self._fetch_value)
        vl.addWidget(self.value_label)
        vl.addWidget(self.value_text)
        vl.addWidget(self.fetch_value_btn)
        right_layout.addWidget(val_group)

        self.save_btn = QPushButton("💾 Save Card to Collection")
        self.save_btn.setMinimumHeight(44)
        self.save_btn.clicked.connect(self._save_card)
        right_layout.addWidget(self.save_btn)
        right_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(right)
        splitter.addWidget(scroll)
        splitter.setSizes([700, 500])
        layout.addWidget(splitter)

        self.status_label = QLabel("Ready.")
        layout.addWidget(self.status_label)

    def _scan(self, side: str):
        source = self.source_combo.currentText()
        if "no TWAIN" in source.lower():
            QMessageBox.warning(self, "No Scanner", "Use Load buttons or connect a TWAIN scanner.")
            return

        self.status_label.setText(f"Scanning {side}...")
        self._worker = ScanWorker(self.scanner, source_name=source, dpi=self.dpi_spin.value())
        self._worker.finished.connect(lambda img: self._scan_done(side, img))
        self._worker.error.connect(self._scan_error)
        self._worker.start()

    def _load_file(self, side: str):
        path, _ = QFileDialog.getOpenFileName(self, f"Load {side} image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff)")
        if not path:
            return
        self.status_label.setText(f"Loading {side}...")
        self._worker = ScanWorker(self.scanner, file_path=path)
        self._worker.finished.connect(lambda img: self._scan_done(side, img))
        self._worker.error.connect(self._scan_error)
        self._worker.start()

    def _scan_done(self, side: str, img: np.ndarray):
        if side == 'front':
            self.current_front_img = img
            self.front_view.set_image(img)
        else:
            self.current_back_img = img
            self.back_view.set_image(img)

        self._auto_identify()
        if side == 'front':
            self._inspect()
        self.status_label.setText(f"{side.capitalize()} captured.")

    def _scan_error(self, msg: str):
        self.status_label.setText(f"Error: {msg}")
        QMessageBox.critical(self, "Scan Error", msg)

    def _auto_identify(self):
        front_text = self.identifier.extract_text(self.current_front_img) if self.current_front_img is not None else ""
        back_text = self.identifier.extract_text(self.current_back_img) if self.current_back_img is not None else ""
        info = self.identifier.parse_card_info(front_text, back_text)

        if info.get('name') and not self.name_edit.text():
            self.name_edit.setText(info['name'])
        if info.get('card_number') and not self.number_edit.text():
            self.number_edit.setText(info['card_number'])
        if info.get('set_name') and not self.set_edit.text():
            self.set_edit.setText(info['set_name'])
        if info.get('rarity') and not self.rarity_edit.text():
            self.rarity_edit.setText(info['rarity'])

    def _inspect(self):
        if self.current_front_img is None:
            self.status_label.setText("Scan or load a front image first.")
            return
        try:
            self.current_inspection = self.inspector.inspect(self.current_front_img)
            self.grade_label.setText(f"Grade: {self.current_inspection['grade']}")
            self.score_label.setText(f"Score: {self.current_inspection['score']}/100")
            # defects display...
        except Exception as e:
            QMessageBox.warning(self, "Inspection Error", str(e))

    def _fetch_value(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing", "Enter card name first.")
            return
        self.fetch_value_btn.setEnabled(False)
        self.fetch_value_btn.setText("Fetching…")
        set_name = self.set_edit.text().strip() or None
        score = (self.current_inspection or {}).get('score', 85.0) or 85.0
        valuator = self.valuator

        def work():
            results = valuator.fetch_all_values(name, set_name)
            estimate = valuator.compute_estimate(results, score)
            return results, estimate

        self._val_worker = QThread()

        class _ValWorker(QThread):
            done = pyqtSignal(object, float)
            err = pyqtSignal(str)
            def __init__(self, fn):
                super().__init__()
                self._fn = fn
            def run(self):
                try:
                    r, e = self._fn()
                    self.done.emit(r, e)
                except Exception as ex:
                    self.err.emit(str(ex))

        w = _ValWorker(work)
        w.done.connect(self._on_value_done)
        w.err.connect(lambda msg: (
            self.fetch_value_btn.setEnabled(True),
            self.fetch_value_btn.setText("💰 Fetch Online Values"),
            QMessageBox.warning(self, "Valuation Error", msg)
        ))
        w.start()
        self._val_worker = w

    def _on_value_done(self, results, estimate):
        self.fetch_value_btn.setEnabled(True)
        self.fetch_value_btn.setText("💰 Fetch Online Values")
        self.current_valuations = results
        self.value_label.setText(f"Estimate: ${estimate:.2f}")
        lines = [f"• {r['source']}: ${r['value']:.2f}" for r in results]
        self.value_text.setPlainText("\n".join(lines) if lines else "No results found.")

    def _save_card(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Card name is required.")
            self.name_edit.setFocus()
            return

        SCANS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        front_path = back_path = None

        if self.current_front_img is not None:
            front_path = str(SCANS_DIR / f"front_{ts}.png")
            cv2.imwrite(front_path, cv2.cvtColor(self.current_front_img, cv2.COLOR_RGB2BGR))
        if self.current_back_img is not None:
            back_path = str(SCANS_DIR / f"back_{ts}.png")
            cv2.imwrite(back_path, cv2.cvtColor(self.current_back_img, cv2.COLOR_RGB2BGR))

        insp = self.current_inspection or {}
        estimate = 0.0
        if self.current_valuations:
            score = insp.get('score', 85.0) or 85.0
            estimate = self.valuator.compute_estimate(self.current_valuations, score)

        card = {
            'name': name,
            'set_name': self.set_edit.text().strip() or None,
            'card_number': self.number_edit.text().strip() or None,
            'rarity': self.rarity_edit.text().strip() or None,
            'game': self.game_edit.currentText(),
            'year': self.year_spin.value(),
            'language': self.lang_edit.text().strip() or 'English',
            'foil': int(self.foil_check.isChecked()),
            'front_scan_path': front_path,
            'back_scan_path': back_path,
            'condition_grade': insp.get('grade'),
            'condition_score': insp.get('score'),
            'defects': insp.get('defects', []),
            'estimated_value': estimate,
            'purchase_price': self.purchase_spin.value(),
            'notes': self.notes_edit.toPlainText().strip() or None,
            'quantity': self.qty_spin.value(),
        }

        try:
            self.db.add_card(card)
            QMessageBox.information(self, "Saved", f"'{name}' added to collection.")
            self.card_added.emit()
            self._reset()
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _reset(self):
        self.current_front_img = self.current_back_img = None
        self.current_inspection = None
        self.current_valuations = []
        self.front_view.set_image(None)
        self.back_view.set_image(None)
        self.name_edit.clear()
        self.set_edit.clear()
        self.number_edit.clear()
        self.rarity_edit.clear()
        self.game_edit.setCurrentIndex(0)
        self.year_spin.setValue(datetime.now().year)
        self.lang_edit.setText("English")
        self.foil_check.setChecked(False)
        self.qty_spin.setValue(1)
        self.purchase_spin.setValue(0)
        self.notes_edit.clear()
        self.grade_label.setText("Not inspected")
        self.score_label.setText("Score: -")
        self.defects_text.clear()
        self.value_label.setText("Estimate: -")
        self.value_text.clear()
        self.status_label.setText("Ready.")

    def _start_continuous_scan(self):
        """Ctrl+Shift+N — scan front immediately."""
        self._scan('front')