"""
Scan & Add Tab - Single Scan Card + Manual Rotate Buttons
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
    QFormLayout, QSplitter, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage

from core.scanner import ScannerInterface
from core.inspector import CardInspector
from core.identifier import CardIdentifier
from core.valuator import CardValuator
from core.database import Database


SCANS_DIR = Path(os.environ.get('APPDATA', Path.home())) / "TradingCardManager" / "scans"
SCANS_DIR.mkdir(parents=True, exist_ok=True)


class ScanWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, scanner: ScannerInterface, source_name: str = None,
                 dpi: int = 300, file_path: str = None, duplex: bool = False):
        super().__init__()
        self.scanner = scanner
        self.source_name = source_name
        self.dpi = dpi
        self.file_path = file_path
        self.duplex = duplex

    def run(self):
        try:
            if self.file_path:
                img = self.scanner.scan_from_file(self.file_path)
                self.finished.emit(img)
            else:
                images = self.scanner.scan(self.source_name, self.dpi, self.duplex)
                self.finished.emit(images)
        except Exception as e:
            self.error.emit(str(e))


class ImageViewer(QLabel):
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
        self.dpi_spin.setValue(400)
        self.dpi_spin.setSuffix(" DPI")

        self.duplex_check = QCheckBox("Enable Duplex (both sides)")
        self.duplex_check.setChecked(True)

        self.scan_card_btn = QPushButton("📷 Scan Card")
        self.scan_card_btn.setMinimumHeight(36)
        self.scan_card_btn.clicked.connect(self._scan_card)

        self.load_front_btn = QPushButton("📂 Load Front")
        self.load_back_btn = QPushButton("📂 Load Back")
        self.continuous_btn = QPushButton("🔄 Continuous Scan")

        for btn in [self.load_front_btn, self.load_back_btn, self.continuous_btn]:
            btn.setMinimumHeight(36)

        self.load_front_btn.clicked.connect(lambda: self._load_file('front'))
        self.load_back_btn.clicked.connect(lambda: self._load_file('back'))
        self.continuous_btn.clicked.connect(self._start_continuous_scan)

        bar.addWidget(QLabel("Scanner:"))
        bar.addWidget(self.source_combo)
        bar.addWidget(self.dpi_spin)
        bar.addWidget(self.duplex_check)
        bar.addWidget(self.scan_card_btn)
        bar.addWidget(self.load_front_btn)
        bar.addWidget(self.load_back_btn)
        bar.addWidget(self.continuous_btn)
        bar.addStretch()
        layout.addLayout(bar)

        # Images with Rotate buttons
        splitter = QSplitter(Qt.Orientation.Horizontal)
        img_widget = QWidget()
        img_layout = QHBoxLayout(img_widget)

        # FRONT
        front_box = QGroupBox("Front")
        fl = QVBoxLayout(front_box)
        self.front_view = ImageViewer("Front side\nNot scanned yet")
        self.front_rotate_btn = QPushButton("↻ Rotate 180°")
        self.front_rotate_btn.clicked.connect(self._rotate_front)
        fl.addWidget(self.front_view)
        fl.addWidget(self.front_rotate_btn)

        # BACK
        back_box = QGroupBox("Back")
        bl = QVBoxLayout(back_box)
        self.back_view = ImageViewer("Back side\nNot scanned yet")
        self.back_rotate_btn = QPushButton("↻ Rotate 180°")
        self.back_rotate_btn.clicked.connect(self._rotate_back)
        bl.addWidget(self.back_view)
        bl.addWidget(self.back_rotate_btn)

        img_layout.addWidget(front_box)
        img_layout.addWidget(back_box)
        splitter.addWidget(img_widget)

        # Right panel - Card Details
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        details_group = QGroupBox("Card Details")
        form = QFormLayout(details_group)

        self.name_edit = QLineEdit()
        self.set_edit = QLineEdit()
        self.number_edit = QLineEdit()
        self.rarity_edit = QLineEdit()
        # Inside details_group form
        self.game_combo = QComboBox()
        self.game_combo.setEditable(True)
        self.game_combo.addItems([
            "Magic: The Gathering",
            "Pokémon",
            "Yu-Gi-Oh!",
            "One Piece",
            "Lorcana",
            "Flesh and Blood",
            "Baseball",
            "Basketball",
            "Football",
            "Hockey",
            "Sports Cards",
            "Other"
        ])
        self.year_spin = QSpinBox()
        self.year_spin.setRange(1900, 2100)
        self.year_spin.setValue(datetime.now().year)
        self.lang_edit = QLineEdit("English")
        self.foil_check = QCheckBox("Foil / Holographic")
        self.qty_spin = QSpinBox()
        self.qty_spin.setValue(1)
        self.purchase_spin = QDoubleSpinBox()
        self.purchase_spin.setPrefix("$")
        self.purchase_spin.setDecimals(2)
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(80)

        for label, widget in [
            ("Name:", self.name_edit), ("Set:", self.set_edit),
            ("Card #:", self.number_edit), ("Rarity:", self.rarity_edit),
            ("Game:", self.game_combo), ("Year:", self.year_spin),
            ("Language:", self.lang_edit), ("Foil:", self.foil_check),
            ("Quantity:", self.qty_spin), ("Purchase Price:", self.purchase_spin),
            ("Notes:", self.notes_edit)
        ]:
            form.addRow(label, widget)

        right_layout.addWidget(details_group)

        # Defects panel
        defects_group = QGroupBox("Defects Found")
        defects_layout = QVBoxLayout(defects_group)
        self.defects_text = QTextEdit()
        self.defects_text.setReadOnly(True)
        self.defects_text.setMaximumHeight(100)
        self.defects_text.setPlainText("No inspection yet")
        defects_layout.addWidget(self.defects_text)
        right_layout.addWidget(defects_group)

        save_btn = QPushButton("💾 Save Card")
        save_btn.clicked.connect(self._save_card)
        right_layout.addWidget(save_btn)

        splitter.addWidget(right_panel)
        layout.addWidget(splitter)

        self.status_label = QLabel("Ready.")
        layout.addWidget(self.status_label)

    def _scan_card(self):
        source = self.source_combo.currentText()
        if "no TWAIN" in source.lower():
            QMessageBox.warning(self, "No Scanner", "Use Load buttons or connect a TWAIN scanner.")
            return

        duplex = self.duplex_check.isChecked()
        self.status_label.setText(f"Scanning... {'(Duplex)' if duplex else ''}")

        self._worker = ScanWorker(
            self.scanner, source_name=source, dpi=self.dpi_spin.value(), duplex=duplex
        )
        self._worker.finished.connect(self._scan_done)
        self._worker.error.connect(self._scan_error)
        self._worker.start()

    def _scan_done(self, result):
        """Handle scan result."""
        if isinstance(result, list) and len(result) >= 2:
            self.current_front_img = result[0]
            self.current_back_img = result[1]
            self.front_view.set_image(result[0])
            self.back_view.set_image(result[1])
            self.status_label.setText("✅ Both sides scanned successfully!")
        elif isinstance(result, list) and len(result) == 1:
            self.current_front_img = result[0]
            self.front_view.set_image(result[0])
            self.status_label.setText("✅ Front scanned")
        else:
            self.current_front_img = result
            self.front_view.set_image(result)
            self.status_label.setText("✅ Card scanned")

        self._auto_identify()
        self._inspect()

    def _rotate_front(self):
        if self.current_front_img is not None:
            self.current_front_img = cv2.rotate(self.current_front_img, cv2.ROTATE_180)
            self.front_view.set_image(self.current_front_img)
            self.status_label.setText("↻ Front rotated 180°")

    def _rotate_back(self):
        if self.current_back_img is not None:
            self.current_back_img = cv2.rotate(self.current_back_img, cv2.ROTATE_180)
            self.back_view.set_image(self.current_back_img)
            self.status_label.setText("↻ Back rotated 180°")

    def _load_file(self, side: str):
        path, _ = QFileDialog.getOpenFileName(self, f"Load {side} image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff)")
        if not path:
            return
        self.status_label.setText(f"Loading {side}...")
        self._worker = ScanWorker(self.scanner, file_path=path)
        self._worker.finished.connect(lambda img: self._load_done(side, img))
        self._worker.error.connect(self._scan_error)
        self._worker.start()

    def _load_done(self, side: str, img):
        if side == 'front':
            self.current_front_img = img
            self.front_view.set_image(img)
        else:
            self.current_back_img = img
            self.back_view.set_image(img)
        self.status_label.setText(f"{side.capitalize()} loaded")
        self._auto_identify()

    def _scan_error(self, msg: str):
        self.status_label.setText(f"Error: {msg}")
        QMessageBox.critical(self, "Scan Error", msg)

    def _start_continuous_scan(self):
        QMessageBox.information(self, "Continuous Scan", "Coming soon!")

    def _auto_identify(self):
        if self.current_front_img is None:
            return
        try:
            front_text = self.identifier.extract_text(self.current_front_img)
            back_text = self.identifier.extract_text(self.current_back_img) if self.current_back_img is not None else ""
            info = self.identifier.parse_card_info(front_text, back_text)

            if info.get('name') and not self.name_edit.text().strip():
                self.name_edit.setText(info['name'])
            if info.get('set_name') and not self.set_edit.text().strip():
                self.set_edit.setText(info['set_name'])
            if info.get('card_number') and not self.number_edit.text().strip():
                self.number_edit.setText(info['card_number'])
            if info.get('rarity') and not self.rarity_edit.text().strip():
                self.rarity_edit.setText(info['rarity'])
            if info.get('year'):
                self.year_spin.setValue(info['year'])
            if info.get('game'):
                idx = self.game_combo.findText(info['game'], Qt.MatchFlag.MatchFixedString)
                if idx >= 0:
                    self.game_combo.setCurrentIndex(idx)
                else:
                    self.game_combo.setCurrentText(info['game'])

            if info.get('name'):
                self.status_label.setText(f"✅ Identified: {info['name']}")
        except Exception as e:
            self.status_label.setText(f"OCR: {str(e)[:60]}")

    def _inspect(self):
        if self.current_front_img is None:
            return
        try:
            self.current_inspection = self.inspector.inspect(self.current_front_img)
            grade = self.current_inspection['grade']
            score = self.current_inspection['score']
            defects = self.current_inspection.get('defects', [])
            defect_count = len(defects)
            
            self.status_label.setText(
                f"🔍 Grade: {grade} ({score:.1f}/100) — {defect_count} defect(s) found"
            )
            
            # Update defects display
            if defects:
                lines = [f"• [{d['severity'].upper()}] {d['type'].replace('_', ' ').title()} @ {d['location']}"
                         for d in defects]
                self.defects_text.setPlainText("\n".join(lines))
            else:
                self.defects_text.setPlainText("None detected.")
        except Exception as e:
            self.status_label.setText(f"Inspection error: {str(e)[:60]}")

    def _save_card(self):
        """Save card to database with images."""
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Missing Info", "Please enter at least the card Name.")
            return

        try:
            # Save images to disk
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            front_path = None
            back_path = None

            scans_dir = SCANS_DIR / "cards"
            scans_dir.mkdir(parents=True, exist_ok=True)

            if self.current_front_img is not None:
                front_path = str(scans_dir / f"{timestamp}_front.png")
                cv2.imwrite(front_path, cv2.cvtColor(self.current_front_img, cv2.COLOR_RGB2BGR))

            if self.current_back_img is not None:
                back_path = str(scans_dir / f"{timestamp}_back.png")
                cv2.imwrite(back_path, cv2.cvtColor(self.current_back_img, cv2.COLOR_RGB2BGR))

            # Prepare card data
            card_data = {
                'name': self.name_edit.text().strip(),
                'set_name': self.set_edit.text().strip(),
                'card_number': self.number_edit.text().strip(),
                'rarity': self.rarity_edit.text().strip(),
                'game': self.game_combo.currentText().strip(),
                'year': self.year_spin.value(),
                'language': self.lang_edit.text().strip() or "English",
                'foil': 1 if self.foil_check.isChecked() else 0,
                'front_scan_path': front_path,
                'back_scan_path': back_path,
                'purchase_price': float(self.purchase_spin.value()),
                'quantity': int(self.qty_spin.value()),
                'notes': self.notes_edit.toPlainText().strip(),
                'condition_grade': self.current_inspection['grade'] if self.current_inspection else None,
                'condition_score': self.current_inspection['score'] if self.current_inspection else None,
                'defects': self.current_inspection.get('defects', []) if self.current_inspection else [],
                'estimated_value': 0.0,
            }

            card_id = self.db.add_card(card_data)

            QMessageBox.information(self, "Success", 
                f"✅ Card saved successfully!\nID: {card_id}\nName: {card_data['name']}")

            # Clear form for next card
            self._reset_form()
            self.card_added.emit()  # Refresh collection tab

        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Error saving card:\n{str(e)}")
            print(f"Save error: {e}")
            
    def _reset_form(self):
        """Clear the form after saving."""
        self.name_edit.clear()
        self.set_edit.clear()
        self.number_edit.clear()
        self.rarity_edit.clear()
        self.notes_edit.clear()
        self.purchase_spin.setValue(0.0)
        self.qty_spin.setValue(1)
        self.current_front_img = None
        self.current_back_img = None
        self.current_inspection = None
        self.front_view.set_image(None)
        self.back_view.set_image(None)
        self.defects_text.setPlainText("No inspection yet")
        self.status_label.setText("Ready.")