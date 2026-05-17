import csv
import os
import cv2
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QCheckBox, QProgressBar, QTextEdit, QFileDialog, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from core.database import Database
from core.scanner import ScannerInterface
from core.inspector import CardInspector
from core.identifier import CardIdentifier
from core.valuator import CardValuator

APP_DIR = Path(os.environ.get('APPDATA', Path.home())) / "TradingCardManager"
SCANS_DIR = APP_DIR / "scans"


class _ImageBatchWorker(QThread):
    progress = pyqtSignal(str, int)
    card_ready = pyqtSignal(dict)
    finished = pyqtSignal(int)

    def __init__(self, paths: List[str], db: Database, scanner: ScannerInterface,
                 inspector: CardInspector, identifier: CardIdentifier,
                 valuator: CardValuator, auto_value: bool):
        super().__init__()
        self.paths = paths
        self.db = db
        self.scanner = scanner
        self.inspector = inspector
        self.identifier = identifier
        self.valuator = valuator
        self.auto_value = auto_value

    def run(self):
        SCANS_DIR.mkdir(parents=True, exist_ok=True)
        total = len(self.paths)
        added = 0

        for i, path_str in enumerate(self.paths):
            img_path = Path(path_str)
            pct = int((i + 1) / total * 100)
            self.progress.emit(f"Processing {img_path.name}…", pct)
            try:
                img = self.scanner.scan_from_file(path_str)
                if img is None:
                    self.progress.emit(f"Skip (unreadable): {img_path.name}", pct)
                    continue

                inspection = self.inspector.inspect(img)
                text = self.identifier.extract_text(img)
                info = self.identifier.parse_card_info(text)

                estimate = 0.0
                if self.auto_value and info.get("name"):
                    vals = self.valuator.fetch_all_values(info["name"], info.get("set_name"))
                    if vals:
                        estimate = self.valuator.compute_estimate(vals, inspection["score"])

                ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                scan_path = str(SCANS_DIR / f"batch_{ts}.png")
                cv2.imwrite(scan_path, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))

                card = {
                    "name": info.get("name") or img_path.stem,
                    "set_name": info.get("set_name"),
                    "card_number": info.get("card_number"),
                    "rarity": info.get("rarity"),
                    "game": "Other",
                    "year": datetime.now().year,
                    "front_scan_path": scan_path,
                    "condition_grade": inspection["grade"],
                    "condition_score": inspection["score"],
                    "defects": inspection["defects"],
                    "estimated_value": estimate,
                    "quantity": 1,
                    "notes": f"Batch import from {img_path.name}",
                }
                card_id = self.db.add_card(card)
                added += 1
                self.progress.emit(f"Saved: {card['name']} (ID {card_id})", pct)
            except Exception as e:
                self.progress.emit(f"Error on {img_path.name}: {str(e)[:80]}", pct)

        self.finished.emit(added)


class _CsvBatchWorker(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(int)

    def __init__(self, csv_path: str, db: Database, mapping: Dict[str, str]):
        super().__init__()
        self.csv_path = csv_path
        self.db = db
        self.mapping = mapping

    def run(self):
        added = 0
        try:
            with open(self.csv_path, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            total = len(rows)
            for i, row in enumerate(rows):
                pct = int((i + 1) / total * 100)
                try:
                    def get(field):
                        col = self.mapping.get(field)
                        return row.get(col, "").strip() if col else ""

                    name = get("name") or f"Row {i + 1}"
                    card = {
                        "name": name,
                        "set_name": get("set_name") or None,
                        "card_number": get("card_number") or None,
                        "rarity": get("rarity") or None,
                        "game": get("game") or None,
                        "year": int(get("year") or 0) or None,
                        "language": get("language") or "English",
                        "foil": int(get("foil") in ("1", "true", "True", "yes", "Yes")),
                        "front_scan_path": get("front_scan_path") or None,
                        "condition_grade": get("condition_grade") or None,
                        "condition_score": float(get("condition_score") or 0) or None,
                        "estimated_value": float(get("estimated_value") or 0),
                        "purchase_price": float(get("purchase_price") or 0),
                        "notes": get("notes") or None,
                        "quantity": int(get("quantity") or 1),
                    }
                    self.db.add_card(card)
                    added += 1
                    self.progress.emit(f"Imported: {name}", pct)
                except Exception as e:
                    self.progress.emit(f"Error row {i + 1}: {str(e)[:80]}", pct)
        except Exception as e:
            self.progress.emit(f"CSV read error: {e}", 100)
        self.finished.emit(added)


class BatchTab(QWidget):
    """Batch import tab — process a folder of images or a CSV file."""

    cards_added = pyqtSignal()

    def __init__(self, db: Database, scanner: ScannerInterface,
                 inspector: CardInspector, identifier: CardIdentifier,
                 valuator: CardValuator):
        super().__init__()
        self.db = db
        self.scanner = scanner
        self.inspector = inspector
        self.identifier = identifier
        self.valuator = valuator
        self._worker: QThread | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Mode selector
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("<b>Import Mode:</b>"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Image Folder", "CSV File"])
        self.mode_combo.currentIndexChanged.connect(self._update_mode_ui)
        mode_row.addWidget(self.mode_combo)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        # Image folder controls
        self.img_grp = QWidget()
        img_row = QHBoxLayout(self.img_grp)
        img_row.setContentsMargins(0, 0, 0, 0)
        self.folder_edit = QLabel("No folder selected")
        self.folder_btn = QPushButton("Select Folder…")
        self.folder_btn.clicked.connect(self._pick_folder)
        self.auto_value_check = QCheckBox("Fetch market values (slower)")
        img_row.addWidget(QLabel("Folder:"))
        img_row.addWidget(self.folder_edit, 1)
        img_row.addWidget(self.folder_btn)
        img_row.addWidget(self.auto_value_check)
        layout.addWidget(self.img_grp)

        # CSV controls
        self.csv_grp = QWidget()
        csv_row = QHBoxLayout(self.csv_grp)
        csv_row.setContentsMargins(0, 0, 0, 0)
        self.csv_edit = QLabel("No file selected")
        self.csv_btn = QPushButton("Select CSV…")
        self.csv_btn.clicked.connect(self._pick_csv)
        csv_row.addWidget(QLabel("File:"))
        csv_row.addWidget(self.csv_edit, 1)
        csv_row.addWidget(self.csv_btn)
        self.csv_grp.setVisible(False)
        layout.addWidget(self.csv_grp)

        # Action buttons
        act_row = QHBoxLayout()
        self.start_btn = QPushButton("Start Import")
        self.start_btn.setMinimumHeight(38)
        self.start_btn.setStyleSheet(
            "background-color: #276749; color: white; font-weight: bold; border-radius: 6px;"
        )
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        act_row.addWidget(self.start_btn)
        act_row.addWidget(self.stop_btn)
        act_row.addStretch()
        layout.addLayout(act_row)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        # Log
        layout.addWidget(QLabel("Import Log:"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(220)
        layout.addWidget(self.log)

        self._folder_path: str | None = None
        self._csv_path: str | None = None

    def _update_mode_ui(self):
        is_csv = self.mode_combo.currentIndex() == 1
        self.img_grp.setVisible(not is_csv)
        self.csv_grp.setVisible(is_csv)

    # ------------------------------------------------------------------
    # File picking
    # ------------------------------------------------------------------

    def _pick_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Image Folder")
        if path:
            self._folder_path = path
            self.folder_edit.setText(path)

    def _pick_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select CSV", "", "CSV (*.csv)")
        if path:
            self._csv_path = path
            self.csv_edit.setText(path)

    # ------------------------------------------------------------------
    # Import logic
    # ------------------------------------------------------------------

    def _start(self):
        is_csv = self.mode_combo.currentIndex() == 1
        self.log.clear()
        self.progress_bar.setValue(0)

        if is_csv:
            if not self._csv_path:
                QMessageBox.warning(self, "No File", "Select a CSV file first.")
                return
            from ui.dialogs import CsvMappingDialog
            dlg = CsvMappingDialog(self._csv_path, self)
            if dlg.exec() != 1:
                return
            self._worker = _CsvBatchWorker(self._csv_path, self.db, dlg.mapping)
        else:
            if not self._folder_path:
                QMessageBox.warning(self, "No Folder", "Select an image folder first.")
                return
            folder = Path(self._folder_path)
            paths = sorted(
                str(p) for ext in ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.tiff", "*.tif")
                for p in folder.glob(ext)
            )
            if not paths:
                QMessageBox.information(self, "No Images",
                                        "No image files found in the selected folder.")
                return
            self._log(f"Found {len(paths)} image(s).")
            self._worker = _ImageBatchWorker(
                paths, self.db, self.scanner, self.inspector,
                self.identifier, self.valuator,
                self.auto_value_check.isChecked(),
            )

        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def _stop(self):
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._log("Import stopped by user.")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _on_progress(self, message: str, pct: int):
        self.progress_bar.setValue(pct)
        self._log(message)

    def _on_finished(self, count: int):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setValue(100)
        self._log(f"\nDone! {count} card(s) imported.")
        if count > 0:
            self.cards_added.emit()
        QMessageBox.information(self, "Import Complete", f"{count} card(s) imported successfully.")

    def _log(self, message: str):
        self.log.append(message)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())
