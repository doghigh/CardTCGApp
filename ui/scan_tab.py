import os
import cv2
import numpy as np
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
    QFormLayout, QSplitter, QMessageBox, QFileDialog, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage

from core.scanner import ScannerInterface
from core.inspector import CardInspector
from core.identifier import CardIdentifier
from core.valuator import CardValuator
from core.database import Database

APP_DIR = Path(os.environ.get('APPDATA', Path.home())) / "TradingCardManager"
SCANS_DIR = APP_DIR / "scans"


class _Worker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self.finished.emit(self._fn() or {})
        except Exception as e:
            self.error.emit(str(e))


class ImageViewer(QLabel):
    """Displays a card image with aspect-ratio-preserving scaling."""

    def __init__(self, placeholder: str = "No image"):
        super().__init__()
        self.setMinimumSize(250, 340)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "background: #1a202c; color: #718096; "
            "border: 2px dashed #2d3748; border-radius: 8px; font-size: 13px;"
        )
        self._placeholder = placeholder
        self.setText(placeholder)

    def set_image(self, img: np.ndarray | None):
        if img is None:
            self.clear()
            self.setText(self._placeholder)
            return
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        h, w = img.shape[:2]
        qimg = QImage(img.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        self.setPixmap(pixmap.scaled(
            self.width() or 250, self.height() or 340,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))


class ScanTab(QWidget):
    """Scan & Add tab — scan or load card images, inspect, identify, and save."""

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

        self._front_img: np.ndarray | None = None
        self._back_img: np.ndarray | None = None
        self._front_path: str | None = None
        self._back_path: str | None = None
        self._inspection: dict = {}
        self._estimated_value: float = 0.0
        self._worker: _Worker | None = None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # --- Scanner toolbar ---
        bar = QHBoxLayout()

        self.source_combo = QComboBox()
        self.source_combo.setMinimumWidth(200)
        sources = self.scanner.list_sources()
        self.source_combo.addItems(sources or ["(No TWAIN scanner detected)"])

        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 1200)
        self.dpi_spin.setValue(300)
        self.dpi_spin.setSuffix(" DPI")

        btn_sf = QPushButton("Scan Front")
        btn_sf.clicked.connect(lambda: self._scan("front"))
        btn_sb = QPushButton("Scan Back")
        btn_sb.clicked.connect(lambda: self._scan("back"))
        btn_lf = QPushButton("Load Front")
        btn_lf.clicked.connect(lambda: self._load_file("front"))
        btn_lb = QPushButton("Load Back")
        btn_lb.clicked.connect(lambda: self._load_file("back"))

        for b in [btn_sf, btn_sb, btn_lf, btn_lb]:
            b.setMinimumHeight(34)

        bar.addWidget(QLabel("Scanner:"))
        bar.addWidget(self.source_combo)
        bar.addWidget(self.dpi_spin)
        bar.addWidget(btn_sf)
        bar.addWidget(btn_sb)
        bar.addWidget(btn_lf)
        bar.addWidget(btn_lb)
        bar.addStretch()
        root.addLayout(bar)

        # --- Main splitter (images | form) ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: images + inspect
        left_widget = QWidget()
        left = QVBoxLayout(left_widget)
        left.setContentsMargins(0, 0, 0, 0)

        img_row = QHBoxLayout()
        self.front_viewer = ImageViewer("Front image")
        self.back_viewer = ImageViewer("Back image")
        for title, viewer in [("Front", self.front_viewer), ("Back", self.back_viewer)]:
            vb = QVBoxLayout()
            vb.addWidget(QLabel(f"<b>{title}</b>"))
            vb.addWidget(viewer)
            img_row.addLayout(vb)
        left.addLayout(img_row)

        # Inspect row
        inspect_row = QHBoxLayout()
        self.inspect_btn = QPushButton("Auto-Inspect & Identify")
        self.inspect_btn.setMinimumHeight(36)
        self.inspect_btn.clicked.connect(self._run_inspect)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        inspect_row.addWidget(self.inspect_btn)
        inspect_row.addWidget(self.progress_bar)
        left.addLayout(inspect_row)

        self.grade_label = QLabel("Grade: —")
        self.grade_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px;")
        left.addWidget(self.grade_label)

        self.defects_label = QLabel("Defects: —")
        self.defects_label.setWordWrap(True)
        self.defects_label.setStyleSheet(
            "padding: 6px; background: #2d3748; border-radius: 4px; font-size: 12px;"
        )
        left.addWidget(self.defects_label)

        splitter.addWidget(left_widget)

        # Right: form
        right_widget = QWidget()
        right = QVBoxLayout(right_widget)
        right.setContentsMargins(0, 0, 0, 0)

        form_grp = QGroupBox("Card Information")
        form = QFormLayout(form_grp)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Required")
        form.addRow("Name *:", self.name_edit)

        self.set_edit = QLineEdit()
        self.set_edit.setPlaceholderText("e.g. Base Set")
        form.addRow("Set:", self.set_edit)

        self.number_edit = QLineEdit()
        self.number_edit.setPlaceholderText("e.g. 25/102")
        form.addRow("Card #:", self.number_edit)

        self.rarity_edit = QLineEdit()
        form.addRow("Rarity:", self.rarity_edit)

        self.game_combo = QComboBox()
        self.game_combo.setEditable(True)
        self.game_combo.addItems([
            "Pokemon", "Magic: The Gathering", "Yu-Gi-Oh!",
            "Dragon Ball Super", "One Piece", "Digimon", "Other",
        ])
        form.addRow("Game:", self.game_combo)

        self.year_spin = QSpinBox()
        self.year_spin.setRange(1990, datetime.now().year + 1)
        self.year_spin.setValue(datetime.now().year)
        form.addRow("Year:", self.year_spin)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems([
            "English", "Japanese", "French", "German",
            "Spanish", "Italian", "Portuguese", "Korean",
        ])
        form.addRow("Language:", self.lang_combo)

        self.foil_check = QCheckBox("Foil / Holographic")
        form.addRow("", self.foil_check)

        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 9999)
        self.qty_spin.setValue(1)
        form.addRow("Quantity:", self.qty_spin)

        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0, 999999)
        self.price_spin.setDecimals(2)
        self.price_spin.setPrefix("$")
        form.addRow("Purchase Price:", self.price_spin)

        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(64)
        self.notes_edit.setPlaceholderText("Notes…")
        form.addRow("Notes:", self.notes_edit)

        right.addWidget(form_grp)

        # Value row
        val_row = QHBoxLayout()
        self.fetch_val_btn = QPushButton("Fetch Market Value")
        self.fetch_val_btn.clicked.connect(self._fetch_value)
        self.value_label = QLabel("Est. Value: $0.00")
        self.value_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        val_row.addWidget(self.fetch_val_btn)
        val_row.addWidget(self.value_label)
        right.addLayout(val_row)

        # Action buttons
        act_row = QHBoxLayout()
        self.save_btn = QPushButton("Save to Collection")
        self.save_btn.setMinimumHeight(40)
        self.save_btn.setStyleSheet(
            "background-color: #276749; color: white; font-weight: bold; border-radius: 6px;"
        )
        self.save_btn.clicked.connect(self._save_card)
        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self._reset)
        act_row.addWidget(self.save_btn, 2)
        act_row.addWidget(reset_btn, 1)
        right.addLayout(act_row)

        splitter.addWidget(right_widget)
        splitter.setSizes([540, 560])
        root.addWidget(splitter)

    # ------------------------------------------------------------------
    # Image helpers
    # ------------------------------------------------------------------

    def _scan(self, side: str):
        src = self.source_combo.currentText()
        src_name = None if "(No TWAIN" in src else src
        dpi = self.dpi_spin.value()
        img = self.scanner.scan(src_name, dpi)
        if img is None:
            QMessageBox.warning(self, "Scan Failed",
                                "Scanner returned no image. Check device connection.")
            return
        self._set_image(side, img, None)

    def _load_file(self, side: str):
        path, _ = QFileDialog.getOpenFileName(
            self, f"Load {side.title()} Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff *.tif)",
        )
        if not path:
            return
        img = self.scanner.scan_from_file(path)
        if img is None:
            QMessageBox.warning(self, "Load Failed", "Could not read the image file.")
            return
        self._set_image(side, img, path)

    def _set_image(self, side: str, img: np.ndarray, path: str | None):
        if side == "front":
            self._front_img = img
            self._front_path = path
            self.front_viewer.set_image(img)
        else:
            self._back_img = img
            self._back_path = path
            self.back_viewer.set_image(img)

    # ------------------------------------------------------------------
    # Inspect / Identify
    # ------------------------------------------------------------------

    def _run_inspect(self):
        if self._front_img is None:
            QMessageBox.information(self, "No Image", "Load or scan a front image first.")
            return
        self._set_busy(True)

        front = self._front_img
        back = self._back_img
        inspector = self.inspector
        identifier = self.identifier

        def work():
            result = inspector.inspect(front)
            front_text = identifier.extract_text(front)
            back_text = identifier.extract_text(back) if back is not None else ""
            info = identifier.parse_card_info(front_text, back_text)
            return {"inspection": result, "info": info}

        self._worker = _Worker(work)
        self._worker.finished.connect(self._on_inspect_done)
        self._worker.error.connect(
            lambda e: (self._set_busy(False), QMessageBox.critical(self, "Inspect Error", e))
        )
        self._worker.start()

    def _set_busy(self, busy: bool):
        self.inspect_btn.setEnabled(not busy)
        self.progress_bar.setVisible(busy)

    def _on_inspect_done(self, result: dict):
        self._set_busy(False)
        insp = result.get("inspection", {})
        info = result.get("info", {})
        self._inspection = insp

        grade = insp.get("grade", "—")
        score = insp.get("score", 0)
        self.grade_label.setText(f"Grade: {grade}  ({score:.1f}/100)")

        defects = insp.get("defects", [])
        if defects:
            lines = [
                f"• [{d['severity'].upper()}] {d['type'].replace('_', ' ').title()} @ {d['location']}"
                for d in defects
            ]
            self.defects_label.setText("Defects:\n" + "\n".join(lines))
        else:
            self.defects_label.setText("Defects: None detected")

        if info.get("name") and not self.name_edit.text():
            self.name_edit.setText(info["name"])
        if info.get("set_name") and not self.set_edit.text():
            self.set_edit.setText(info["set_name"])
        if info.get("card_number") and not self.number_edit.text():
            self.number_edit.setText(info["card_number"])
        if info.get("rarity") and not self.rarity_edit.text():
            self.rarity_edit.setText(info["rarity"])

    # ------------------------------------------------------------------
    # Valuation
    # ------------------------------------------------------------------

    def _fetch_value(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.information(self, "No Name", "Enter a card name first.")
            return
        self.fetch_val_btn.setEnabled(False)
        self.fetch_val_btn.setText("Fetching…")

        set_name = self.set_edit.text().strip() or None
        score = self._inspection.get("score", 85.0) or 85.0
        valuator = self.valuator

        def work():
            results = valuator.fetch_all_values(name, set_name)
            estimate = valuator.compute_estimate(results, score)
            return {"estimate": estimate}

        self._worker = _Worker(work)
        self._worker.finished.connect(self._on_value_done)
        self._worker.error.connect(lambda _: (
            self.fetch_val_btn.setEnabled(True),
            self.fetch_val_btn.setText("Fetch Market Value"),
        ))
        self._worker.start()

    def _on_value_done(self, result: dict):
        self.fetch_val_btn.setEnabled(True)
        self.fetch_val_btn.setText("Fetch Market Value")
        self._estimated_value = result.get("estimate", 0.0)
        self.value_label.setText(f"Est. Value: ${self._estimated_value:.2f}")

    # ------------------------------------------------------------------
    # Save / Reset
    # ------------------------------------------------------------------

    def _save_card(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Required Field", "Card name is required.")
            self.name_edit.setFocus()
            return

        SCANS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        front_path = self._front_path
        back_path = self._back_path

        if self._front_img is not None and front_path is None:
            front_path = str(SCANS_DIR / f"front_{ts}.png")
            cv2.imwrite(front_path, cv2.cvtColor(self._front_img, cv2.COLOR_RGB2BGR))

        if self._back_img is not None and back_path is None:
            back_path = str(SCANS_DIR / f"back_{ts}.png")
            cv2.imwrite(back_path, cv2.cvtColor(self._back_img, cv2.COLOR_RGB2BGR))

        card = {
            "name": name,
            "set_name": self.set_edit.text().strip() or None,
            "card_number": self.number_edit.text().strip() or None,
            "rarity": self.rarity_edit.text().strip() or None,
            "game": self.game_combo.currentText(),
            "year": self.year_spin.value(),
            "language": self.lang_combo.currentText(),
            "foil": int(self.foil_check.isChecked()),
            "front_scan_path": front_path,
            "back_scan_path": back_path,
            "condition_grade": self._inspection.get("grade"),
            "condition_score": self._inspection.get("score"),
            "defects": self._inspection.get("defects", []),
            "estimated_value": self._estimated_value,
            "purchase_price": self.price_spin.value(),
            "notes": self.notes_edit.toPlainText().strip() or None,
            "quantity": self.qty_spin.value(),
        }

        try:
            card_id = self.db.add_card(card)
            QMessageBox.information(self, "Saved", f"'{name}' saved to collection (ID: {card_id}).")
            self.card_added.emit()
            self._reset()
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", str(e))

    def _reset(self):
        self._front_img = None
        self._back_img = None
        self._front_path = None
        self._back_path = None
        self._inspection = {}
        self._estimated_value = 0.0

        self.front_viewer.set_image(None)
        self.back_viewer.set_image(None)
        self.grade_label.setText("Grade: —")
        self.defects_label.setText("Defects: —")
        self.value_label.setText("Est. Value: $0.00")
        self.name_edit.clear()
        self.set_edit.clear()
        self.number_edit.clear()
        self.rarity_edit.clear()
        self.game_combo.setCurrentIndex(0)
        self.year_spin.setValue(datetime.now().year)
        self.lang_combo.setCurrentIndex(0)
        self.foil_check.setChecked(False)
        self.qty_spin.setValue(1)
        self.price_spin.setValue(0)
        self.notes_edit.clear()

    def _start_continuous_scan(self):
        """Entry point for Ctrl+Shift+N — starts a front scan."""
        self._scan("front")
