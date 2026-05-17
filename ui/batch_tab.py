"""
Batch Import Tab - Full implementation with image folder + CSV support.
Fixed: Better error handling, input validation, and CSV mapping integration.
"""

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QCheckBox, QProgressBar, QTextEdit, QFileDialog, QMessageBox
)
from PyQt6.QtCore import QThread, pyqtSignal

from core.database import Database
from core.scanner import ScannerInterface
from core.inspector import CardInspector
from core.identifier import CardIdentifier
from core.valuator import CardValuator
from ui.dialogs import CsvMappingDialog


SCANS_DIR = Path(os.environ.get('APPDATA', Path.home())) / "TradingCardManager" / "scans"
SCANS_DIR.mkdir(parents=True, exist_ok=True)


class ImageBatchWorker(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(int)

    def __init__(self, folder: Path, scanner: ScannerInterface, inspector: CardInspector,
                 identifier: CardIdentifier, valuator: CardValuator, auto_value: bool = False):
        super().__init__()
        self.folder = folder
        self.scanner = scanner
        self.inspector = inspector
        self.identifier = identifier
        self.valuator = valuator
        self.auto_value = auto_value

    def run(self):
        images = sorted(list(self.folder.glob("*.png")) +
                       list(self.folder.glob("*.jpg")) +
                       list(self.folder.glob("*.jpeg")))
        added = 0
        total = len(images)

        for i, img_path in enumerate(images):
            try:
                progress_pct = int((i + 1) / total * 100)
                self.progress.emit(f"Processing {img_path.name}...", progress_pct)

                img = self.scanner.scan_from_file(str(img_path))
                if img is None:
                    continue

                text = self.identifier.extract_text(img)
                info = self.identifier.parse_card_info(text)
                inspection = self.inspector.inspect(img)

                estimate = 0.0
                if self.auto_value and info.get('name'):
                    vals = self.valuator.fetch_all_values(info.get('name'), info.get('set_name'))
                    if vals:
                        estimate = self.valuator.compute_estimate(vals, inspection['score'])

                # Save image
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                scan_path = str(SCANS_DIR / f"batch_{ts}_{img_path.stem}.png")
                cv2.imwrite(scan_path, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))

                card_data = {
                    'name': info.get('name') or img_path.stem,
                    'set_name': info.get('set_name'),
                    'card_number': info.get('card_number'),
                    'rarity': info.get('rarity'),
                    'game': 'Other',
                    'year': datetime.now().year,
                    'front_scan_path': scan_path,
                    'condition_grade': inspection['grade'],
                    'condition_score': inspection['score'],
                    'defects': inspection['defects'],
                    'estimated_value': estimate,
                    'quantity': 1,
                    'notes': f"Batch import from {img_path.name}",
                }

                self.db.add_card(card_data)
                added += 1
                self.progress.emit(f"✅ Saved: {card_data['name']}", progress_pct)

            except Exception as e:
                self.progress.emit(f"❌ Error on {img_path.name}: {str(e)[:80]}", progress_pct)

        self.finished.emit(added)


class CsvBatchWorker(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(int)

    def __init__(self, csv_path: Path, db: Database, mapping: Dict = None):
        super().__init__()
        self.csv_path = csv_path
        self.db = db
        self.mapping = mapping or {}

    def run(self):
        added = 0
        try:
            with open(self.csv_path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                total = len(rows)

                for i, row in enumerate(rows):
                    try:
                        progress_pct = int((i + 1) / total * 100)

                        card_data = {
                            'name': row.get(self.mapping.get('name')) or row.get('name', 'Unknown Card'),
                            'set_name': row.get(self.mapping.get('set_name')),
                            'card_number': row.get(self.mapping.get('card_number')),
                            'rarity': row.get(self.mapping.get('rarity')),
                            'game': row.get(self.mapping.get('game'), 'Other'),
                            'year': int(row.get(self.mapping.get('year'), datetime.now().year)),
                            'condition_grade': row.get(self.mapping.get('condition_grade')),
                            'condition_score': float(row.get(self.mapping.get('condition_score'), 75.0)),
                            'estimated_value': float(row.get(self.mapping.get('estimated_value'), 0.0)),
                            'purchase_price': float(row.get(self.mapping.get('purchase_price'), 0.0)),
                            'quantity': int(row.get(self.mapping.get('quantity'), 1)),
                            'foil': 1 if str(row.get(self.mapping.get('foil', ''), '')).lower() in ['yes', 'true', '1', 'foil', 'holo'] else 0,
                            'notes': row.get(self.mapping.get('notes'), ''),
                        }

                        if not card_data['name'] or card_data['name'] == 'Unknown Card':
                            continue

                        self.db.add_card(card_data)
                        added += 1
                        self.progress.emit(f"✅ Imported: {card_data['name']}", progress_pct)

                    except Exception as e:
                        self.progress.emit(f"❌ Row {i+1}: {str(e)[:70]}", progress_pct)

        except Exception as e:
            self.progress.emit(f"❌ Failed to read CSV: {e}", 100)

        self.progress.emit(f"✅ Import complete — {added} cards added", 100)
        self.finished.emit(added)


class BatchTab(QWidget):
    cards_added = pyqtSignal(int)

    def __init__(self, db: Database, scanner: ScannerInterface, inspector: CardInspector,
                 identifier: CardIdentifier, valuator: CardValuator):
        super().__init__()
        self.db = db
        self.scanner = scanner
        self.inspector = inspector
        self.identifier = identifier
        self.valuator = valuator
        self.current_path = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("📦 Batch Import")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # Mode selector
        mode_layout = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["📷 Image Folder (Auto OCR + Grade)", "📊 CSV Import"])
        self.mode_combo.currentIndexChanged.connect(self._switch_mode)
        mode_layout.addWidget(QLabel("Import Mode:"))
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # Image Folder
        self.image_widget = QWidget()
        iw = QVBoxLayout(self.image_widget)
        self.folder_btn = QPushButton("📁 Select Folder with Card Images")
        self.folder_btn.clicked.connect(self._select_folder)
        iw.addWidget(self.folder_btn)

        self.auto_value_check = QCheckBox("Auto-fetch online values")
        iw.addWidget(self.auto_value_check)
        layout.addWidget(self.image_widget)

        # CSV
        self.csv_widget = QWidget()
        cw = QVBoxLayout(self.csv_widget)
        self.csv_btn = QPushButton("📄 Select CSV File")
        self.csv_btn.clicked.connect(self._select_csv)
        cw.addWidget(self.csv_btn)

        self.template_btn = QPushButton("📥 Download CSV Template")
        self.template_btn.clicked.connect(self._create_csv_template)
        cw.addWidget(self.template_btn)
        layout.addWidget(self.csv_widget)
        self.csv_widget.hide()

        # Process button
        self.process_btn = QPushButton("🚀 Start Batch Import")
        self.process_btn.setMinimumHeight(48)
        self.process_btn.clicked.connect(self._start_import)
        self.process_btn.setEnabled(False)
        layout.addWidget(self.process_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(QLabel("Log:"))
        layout.addWidget(self.log_text)

        self.status_label = QLabel("Select a folder or CSV file to begin.")
        layout.addWidget(self.status_label)

    def _switch_mode(self, index):
        self.image_widget.setVisible(index == 0)
        self.csv_widget.setVisible(index == 1)
        self.process_btn.setEnabled(False)
        self.current_path = None

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder with Card Images")
        if folder:
            self.current_path = Path(folder)
            self.log_text.append(f"📁 Selected: {self.current_path.name}")
            self.process_btn.setEnabled(True)

    def _select_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select CSV", "", "CSV (*.csv)")
        if path:
            self.current_path = Path(path)
            self.log_text.append(f"📄 Selected: {self.current_path.name}")
            self.process_btn.setEnabled(True)

    def _start_import(self):
        if not self.current_path:
            return

        self.process_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log_text.clear()

        if self.mode_combo.currentIndex() == 0:  # Image Folder
            self._batch_worker = ImageBatchWorker(
                self.current_path, self.scanner, self.inspector,
                self.identifier, self.valuator, self.auto_value_check.isChecked()
            )
        else:  # CSV
            dialog = CsvMappingDialog(self.current_path, self)
            if dialog.exec() != 1:   # Accepted
                self.process_btn.setEnabled(True)
                return
            mapping = dialog.get_mapping()
            self._batch_worker = CsvBatchWorker(self.current_path, self.db, mapping)

        self._batch_worker.progress.connect(self._on_progress)
        self._batch_worker.finished.connect(self._on_finished)
        self._batch_worker.start()

    def _on_progress(self, msg: str, progress: int):
        self.log_text.append(msg)
        self.progress_bar.setValue(progress)
        self.status_label.setText(msg)

    def _on_finished(self, count: int):
        self.process_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.log_text.append(f"✅ Batch complete! {count} cards imported.")
        self.cards_added.emit(count)

    def _create_csv_template(self):
        template_path = Path.home() / "Desktop" / "card_import_template.csv"
        headers = ["name", "set_name", "card_number", "rarity", "game", "year",
                   "condition_grade", "condition_score", "estimated_value",
                   "purchase_price", "quantity", "foil", "notes"]

        with open(template_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerow(["Charizard VMAX", "Brilliant Stars", "74/172", "Ultra Rare",
                            "Pokémon", "2022", "Near Mint", "92", "245.50", "120.00",
                            "1", "Yes", "Pulled from booster"])

        QMessageBox.information(self, "Template Created",
            f"Template saved to:\n{template_path}\n\nFill it in Excel and import.")