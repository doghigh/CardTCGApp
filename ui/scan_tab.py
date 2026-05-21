"""
Scan & Add Tab - Full implementation with Duplex support.
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
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from core.scanner import ScannerInterface
from core.inspector import CardInspector
from core.identifier import CardIdentifier
from core.valuator import CardValuator
from core.database import Database


SCANS_DIR = Path(os.environ.get('APPDATA', Path.home())) / "TradingCardManager" / "scans"
SCANS_DIR.mkdir(parents=True, exist_ok=True)


class ScanWorker(QThread):
    """Background thread for scanning and file loading."""
    finished = pyqtSignal(object)   # Now accepts list or single image
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
                self.finished.emit(images)   # list for duplex
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

        # === NEW: Duplex Checkbox ===
        self.duplex_check = QCheckBox("Enable Duplex (both sides)")
        self.duplex_check.setChecked(False)

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
        bar.addWidget(self.duplex_check)          # ← Added here
        bar.addWidget(self.scan_front_btn)
        bar.addWidget(self.scan_back_btn)
        bar.addWidget(self.load_front_btn)
        bar.addWidget(self.load_back_btn)
        bar.addWidget(self.continuous_btn)
        bar.addStretch()
        layout.addLayout(bar)

        # ... (rest of the UI stays the same - images, details, etc.)
        # [The rest of _build_ui, _scan, _scan_done, etc. remains unchanged except for duplex passing]

        # Images, right panel, etc. (omitted for brevity - copy from your current file)
        # Just make sure to keep everything after the bar layout.

    def _scan(self, side: str):
        source = self.source_combo.currentText()
        if "no TWAIN" in source.lower():
            QMessageBox.warning(self, "No Scanner", "Use Load buttons or connect a TWAIN scanner.")
            return

        duplex = self.duplex_check.isChecked() and side == 'front'  # Only on front scan for duplex

        self.status_label.setText(f"Scanning {side}... {'(Duplex)' if duplex else ''}")
        self._worker = ScanWorker(
            self.scanner,
            source_name=source,
            dpi=self.dpi_spin.value(),
            duplex=duplex
        )
        self._worker.finished.connect(lambda imgs: self._scan_done(side, imgs))
        self._worker.error.connect(self._scan_error)
        self._worker.start()

    def _scan_done(self, side: str, result):
        """Handle single image or list from duplex."""
        if isinstance(result, list) and len(result) >= 2:
            # Duplex returned front + back
            self.current_front_img = result[0]
            self.current_back_img = result[1]
            self.front_view.set_image(result[0])
            self.back_view.set_image(result[1])
            self.status_label.setText("Both sides scanned via Duplex!")
        elif isinstance(result, list) and len(result) == 1:
            img = result[0]
            self._set_side_image(side, img)
        else:
            self._set_side_image(side, result)

        self._auto_identify()
        if side == 'front' or (isinstance(result, list) and len(result) > 0):
            self._inspect()
        self.status_label.setText(f"{side.capitalize()} captured.")

    def _set_side_image(self, side: str, img):
        if side == 'front':
            self.current_front_img = img
            self.front_view.set_image(img)
        else:
            self.current_back_img = img
            self.back_view.set_image(img)

    # ... keep all other methods (_load_file, _scan_error, _auto_identify, etc.) as they are