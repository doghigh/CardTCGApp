"""
Batch Import Tab
"""

import csv
import cv2
import os
from datetime import datetime
from pathlib import Path
from typing import Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QCheckBox, QProgressBar, QTextEdit, QFileDialog, QMessageBox, QGroupBox
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

    # pairing modes
    SINGLE     = "single"      # each image = one card
    SEQUENTIAL = "sequential"  # files in order: 1=front, 2=back, 3=front, ...
    FILENAME   = "filename"    # pair by *_front / *_back style names

    def __init__(self, folder: Path, db: Database, scanner: ScannerInterface,
                 inspector: CardInspector, identifier: CardIdentifier,
                 valuator: CardValuator, auto_value: bool = False,
                 pairing: str = "single"):
        super().__init__()
        self.folder = folder
        self.db = db
        self.scanner = scanner
        self.inspector = inspector
        self.identifier = identifier
        self.valuator = valuator
        self.auto_value = auto_value
        self.pairing = pairing

    # ── front/back pairing ────────────────────────────────────────────────────

    @staticmethod
    def _pair_images(paths, mode: str):
        """Group image paths into (front, back|None) tuples per the chosen mode."""
        if mode == ImageBatchWorker.SINGLE:
            return [(p, None) for p in paths]

        if mode == ImageBatchWorker.SEQUENTIAL:
            pairs = []
            for i in range(0, len(paths), 2):
                front = paths[i]
                back = paths[i + 1] if i + 1 < len(paths) else None
                pairs.append((front, back))
            return pairs

        # FILENAME — match *_front / *_back (also f/b, front/rear, 1/2 suffixes)
        import re
        BACK_TOKENS  = ("back", "rear", "rev", "reverse")
        FRONT_TOKENS = ("front", "frnt", "face", "obverse")

        def classify(stem: str):
            s = stem.lower()
            # explicit words first
            for t in BACK_TOKENS:
                if t in s:
                    return "back", re.sub(rf"[ _\-]*{t}", "", s)
            for t in FRONT_TOKENS:
                if t in s:
                    return "front", re.sub(rf"[ _\-]*{t}", "", s)
            # trailing single-letter / digit markers: _f/_b, -1/-2
            m = re.search(r"[ _\-]([fb])$", s)
            if m:
                return ("front" if m.group(1) == "f" else "back"), s[:m.start()]
            m = re.search(r"[ _\-]([12])$", s)
            if m:
                return ("front" if m.group(1) == "1" else "back"), s[:m.start()]
            return None, s

        groups: dict = {}
        order = []
        for p in paths:
            side, base = classify(p.stem)
            base = re.sub(r"[ _\-]+$", "", base).strip()
            if base not in groups:
                groups[base] = {"front": None, "back": None}
                order.append(base)
            slot = side or "front"
            if groups[base][slot] is None:
                groups[base][slot] = p
            elif groups[base]["back"] is None:
                groups[base]["back"] = p
        return [(groups[b]["front"] or groups[b]["back"], groups[b]["back"]
                 if groups[b]["front"] else None) for b in order]

    def _load(self, path):
        if path is None:
            return None
        img = self.scanner.scan_from_file(str(path))
        if img is None:
            return None
        try:
            from utils.image_ops import deskew
            return deskew(img)
        except Exception:
            return img

    def run(self):
        images = sorted(list(self.folder.glob("*.png")) +
                        list(self.folder.glob("*.jpg")) +
                        list(self.folder.glob("*.jpeg")))
        pairs = self._pair_images(images, self.pairing)
        added = 0
        total = max(1, len(pairs))

        for i, (front_path, back_path) in enumerate(pairs):
            progress_pct = int((i + 1) / total * 100)
            try:
                self.progress.emit(f"Processing {front_path.name}…", progress_pct)

                front = self._load(front_path)
                if front is None:
                    continue
                back = self._load(back_path)

                info = self.identifier.identify_card(front, back)
                inspection = self.inspector.inspect(front)

                estimate = 0.0
                if self.auto_value and info.get('name'):
                    summary = self.valuator.value_summary(
                        info.get('name', ''), info.get('set_name'),
                        info.get('game'), inspection.get('grade'),
                        inspection.get('score', 85.0)
                    )
                    estimate = summary.get('estimated', 0.0)

                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                front_scan = str(SCANS_DIR / f"batch_{ts}_{i:03d}_front.png")
                cv2.imwrite(front_scan, cv2.cvtColor(front, cv2.COLOR_RGB2BGR))
                back_scan = None
                if back is not None:
                    back_scan = str(SCANS_DIR / f"batch_{ts}_{i:03d}_back.png")
                    cv2.imwrite(back_scan, cv2.cvtColor(back, cv2.COLOR_RGB2BGR))

                card_data = {
                    'name': info.get('name') or front_path.stem,
                    'set_name': info.get('set_name'),
                    'card_number': info.get('card_number'),
                    'rarity': info.get('rarity'),
                    'game': info.get('game') or 'Other',
                    'year': info.get('year') or datetime.now().year,
                    'front_scan_path': front_scan,
                    'back_scan_path': back_scan,
                    'condition_grade': inspection['grade'],
                    'condition_score': inspection['score'],
                    'defects': inspection['defects'],
                    'estimated_value': estimate,
                    'quantity': 1,
                    'notes': f"Batch import from {front_path.name}",
                }

                self.db.add_card(card_data)
                added += 1
                sides = "front+back" if back is not None else "front"
                self.progress.emit(f"✅ Saved: {card_data['name']} ({sides})", progress_pct)

            except Exception as e:
                nm = front_path.name if front_path else "?"
                self.progress.emit(f"❌ Error on {nm}: {str(e)[:80]}", progress_pct)

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
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header
        header = QHBoxLayout()
        title = QLabel("📦 Batch Import")
        title.setStyleSheet("font-size: 20px; font-weight: 600; color: #e8eaf0;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # Source group
        source_group = QGroupBox("Import Source")
        sg = QVBoxLayout(source_group)
        sg.setContentsMargins(12, 24, 12, 12)
        sg.setSpacing(10)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["📷 Image Folder (Auto Identify + Grade)", "📊 CSV Import"])
        self.mode_combo.setMinimumWidth(280)
        self.mode_combo.currentIndexChanged.connect(self._switch_mode)
        mode_row.addWidget(self.mode_combo)
        mode_row.addStretch()
        sg.addLayout(mode_row)

        # Image folder widgets
        self.image_widget = QWidget()
        iw = QVBoxLayout(self.image_widget)
        iw.setContentsMargins(0, 0, 0, 0)
        iw.setSpacing(8)
        folder_row = QHBoxLayout()
        self.folder_btn = QPushButton("📁 Select Folder with Card Images")
        self.folder_btn.setMinimumHeight(38)
        self.folder_btn.setMaximumWidth(320)
        self.folder_btn.clicked.connect(self._select_folder)
        self.folder_label = QLabel("No folder selected")
        self.folder_label.setStyleSheet("color: #8b8fa8; font-size: 12px;")
        folder_row.addWidget(self.folder_btn)
        folder_row.addWidget(self.folder_label)
        folder_row.addStretch()
        iw.addLayout(folder_row)

        # Front/back pairing mode
        pair_row = QHBoxLayout()
        pair_row.addWidget(QLabel("Images:"))
        self.pairing_combo = QComboBox()
        self.pairing_combo.addItems([
            "One image = one card",
            "Front/back pairs — sequential (1=front, 2=back)",
            "Front/back pairs — by filename (_front / _back)",
        ])
        self.pairing_combo.setMinimumWidth(320)
        self.pairing_combo.setToolTip(
            "How to group the files in the folder.\n"
            "• Sequential: files in order are paired front, back, front, back…\n"
            "• By filename: matches name_front.jpg with name_back.jpg")
        pair_row.addWidget(self.pairing_combo)
        pair_row.addStretch()
        iw.addLayout(pair_row)

        self.auto_value_check = QCheckBox("Auto-fetch online values after import")
        iw.addWidget(self.auto_value_check)
        sg.addWidget(self.image_widget)

        # CSV widgets
        self.csv_widget = QWidget()
        cw = QVBoxLayout(self.csv_widget)
        cw.setContentsMargins(0, 0, 0, 0)
        cw.setSpacing(8)
        csv_btns = QHBoxLayout()
        self.csv_btn = QPushButton("📄 Select CSV File")
        self.csv_btn.setMinimumHeight(38)
        self.csv_btn.clicked.connect(self._select_csv)
        self.template_btn = QPushButton("📥 Download Template")
        self.template_btn.setMinimumHeight(38)
        self.template_btn.clicked.connect(self._create_csv_template)
        csv_btns.addWidget(self.csv_btn)
        csv_btns.addWidget(self.template_btn)
        cw.addLayout(csv_btns)
        sg.addWidget(self.csv_widget)
        self.csv_widget.hide()

        layout.addWidget(source_group)

        # Action row
        action_row = QHBoxLayout()
        self.process_btn = QPushButton("🚀 Start Batch Import")
        self.process_btn.setMinimumHeight(44)
        self.process_btn.setProperty("primary", True)
        self.process_btn.clicked.connect(self._start_import)
        self.process_btn.setEnabled(False)
        action_row.addWidget(self.process_btn)
        layout.addLayout(action_row)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimumHeight(8)
        layout.addWidget(self.progress_bar)

        # Log
        log_group = QGroupBox("Import Log")
        lg = QVBoxLayout(log_group)
        lg.setContentsMargins(10, 24, 10, 10)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(200)
        lg.addWidget(self.log_text)
        layout.addWidget(log_group, 1)

        self.status_label = QLabel("Select a folder or CSV file to begin.")
        self.status_label.setStyleSheet("color: #8b8fa8; font-size: 12px;")
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
            self.folder_label.setText(self.current_path.name)
            self.log_text.append(f"📁 Selected folder: {self.current_path}")
            self.process_btn.setEnabled(True)
            self.status_label.setText(f"Ready — {self.current_path.name}")

    def _select_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select CSV", "", "CSV (*.csv)")
        if path:
            self.current_path = Path(path)
            self.log_text.append(f"📄 Selected file: {self.current_path}")
            self.process_btn.setEnabled(True)
            self.status_label.setText(f"Ready — {self.current_path.name}")

    def _start_import(self):
        if not self.current_path:
            return
        self.process_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log_text.clear()

        if self.mode_combo.currentIndex() == 0:
            pairing = {
                0: ImageBatchWorker.SINGLE,
                1: ImageBatchWorker.SEQUENTIAL,
                2: ImageBatchWorker.FILENAME,
            }[self.pairing_combo.currentIndex()]
            self._batch_worker = ImageBatchWorker(
                self.current_path, self.db, self.scanner, self.inspector,
                self.identifier, self.valuator, self.auto_value_check.isChecked(),
                pairing,
            )
        else:
            dialog = CsvMappingDialog(self.current_path, self)
            if dialog.exec() != 1:
                self.process_btn.setEnabled(True)
                return
            self._batch_worker = CsvBatchWorker(self.current_path, self.db, dialog.mapping)

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
        self.log_text.append(f"\n✅ Batch complete — {count} cards imported.")
        self.status_label.setText(f"Done — {count} cards imported.")
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
            f"Template saved to:\n{template_path}\n\nFill it in and import.")
