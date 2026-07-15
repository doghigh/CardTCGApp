"""
Scan & Add Tab - Single Scan Card + Manual Rotate Buttons
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None  # type: ignore[assignment]
    np = None   # type: ignore[assignment]

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
    QFormLayout, QSplitter, QMessageBox, QFileDialog, QDialog, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage

from core.scanner import ScannerInterface
from core.inspector import CardInspector
from core.identifier import CardIdentifier
from core.valuator import CardValuator
from core.database import Database


from core.paths import SCANS_DIR
SCANS_DIR.mkdir(parents=True, exist_ok=True)


logger = logging.getLogger(__name__)

class ScanWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, scanner: ScannerInterface, source_name: Optional[str] = None,
                 dpi: int = 300, file_path: Optional[str] = None, duplex: bool = False):
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
            QLabel { background: #13151f; color: #4a4d60;
                     border: 2px dashed #2a2d3e; border-radius: 10px; font-size: 13px; }
        """)
        self._placeholder = placeholder
        self.setText(placeholder)

    def set_image(self, img: "Optional[np.ndarray]"):
        if img is None or cv2 is None or np is None:
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
    open_settings_requested = pyqtSignal()
    key_setup_requested = pyqtSignal(str)

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

        self._accumulated_images = []   # pages collected across multiple scan runs
        self._last_identify = None

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # No-API-key banner (hidden once a key is present)
        self.api_key_banner = QFrame()
        self.api_key_banner.setStyleSheet(
            "background-color: #3a2f1a; border: 1px solid #6b5324; border-radius: 8px;"
        )
        banner_layout = QHBoxLayout(self.api_key_banner)
        banner_layout.setContentsMargins(12, 8, 12, 8)
        banner_label = QLabel(
            "No Anthropic API key set — auto-identify on scan is disabled. "
            "You can still scan and enter card details manually."
        )
        banner_label.setWordWrap(True)
        banner_label.setStyleSheet("color: #e8eaf0;")
        banner_layout.addWidget(banner_label, 1)
        settings_link_btn = QPushButton("Set Up Key…")
        settings_link_btn.clicked.connect(self.open_settings_requested.emit)
        banner_layout.addWidget(settings_link_btn)
        layout.addWidget(self.api_key_banner)
        self.refresh_api_key_banner()

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
        self.scan_card_btn.setProperty("primary", True)
        self.scan_card_btn.clicked.connect(self._scan_card)

        self.load_front_btn = QPushButton("📂 Load Front")
        self.load_back_btn = QPushButton("📂 Load Back")
        for btn in [self.load_front_btn, self.load_back_btn]:
            btn.setMinimumHeight(36)
        self.load_front_btn.clicked.connect(lambda: self._load_file('front'))
        self.load_back_btn.clicked.connect(lambda: self._load_file('back'))

        bar.addWidget(QLabel("Scanner:"))
        bar.addWidget(self.source_combo)
        bar.addWidget(self.dpi_spin)
        bar.addWidget(self.duplex_check)
        bar.addWidget(self.scan_card_btn)
        bar.addWidget(self.load_front_btn)
        bar.addWidget(self.load_back_btn)
        bar.addStretch()
        layout.addLayout(bar)

        # Images with Rotate buttons
        splitter = QSplitter(Qt.Orientation.Horizontal)
        img_widget = QWidget()
        img_widget.setContentsMargins(0, 0, 0, 0)
        img_layout = QHBoxLayout(img_widget)
        img_layout.setSpacing(10)
        img_layout.setContentsMargins(0, 0, 0, 0)

        # FRONT
        front_box = QGroupBox("Front")
        fl = QVBoxLayout(front_box)
        fl.setContentsMargins(8, 8, 8, 8)
        fl.setSpacing(6)
        self.front_view = ImageViewer("Front side\nNot scanned yet")
        self.front_view.setAccessibleName("Front card image preview")
        fl.addWidget(self.front_view)
        fl.addLayout(self._make_rotate_bar('front'))

        # BACK
        back_box = QGroupBox("Back")
        bl = QVBoxLayout(back_box)
        bl.setContentsMargins(8, 8, 8, 8)
        bl.setSpacing(6)
        self.back_view = ImageViewer("Back side\nNot scanned yet")
        self.back_view.setAccessibleName("Back card image preview")
        bl.addWidget(self.back_view)
        bl.addLayout(self._make_rotate_bar('back'))

        img_layout.addWidget(front_box)
        img_layout.addWidget(back_box)
        splitter.addWidget(img_widget)

        # Right panel — scrollable so nothing clips on smaller screens
        right_panel = QWidget()
        right_panel.setMinimumWidth(340)
        right_outer = QVBoxLayout(right_panel)
        right_outer.setContentsMargins(0, 0, 0, 0)
        right_outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_content = QWidget()
        right_layout = QVBoxLayout(scroll_content)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(10)
        scroll.setWidget(scroll_content)
        right_outer.addWidget(scroll, 1)

        details_group = QGroupBox("Card Details")
        form = QFormLayout(details_group)
        form.setContentsMargins(10, 8, 10, 10)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.name_edit = QLineEdit()
        self.set_edit = QLineEdit()
        self.number_edit = QLineEdit()
        self.rarity_edit = QLineEdit()
        self.game_combo = QComboBox()
        self.game_combo.setEditable(True)
        self.game_combo.addItems([
            "Magic: The Gathering", "Pokémon", "Yu-Gi-Oh!", "One Piece",
            "Lorcana", "Flesh and Blood", "Baseball", "Basketball",
            "Football", "Hockey", "Sports Cards", "Non-Sport", "Other"
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
        self.notes_edit.setMinimumHeight(80)
        self.notes_edit.setMaximumHeight(120)

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
        defects_layout.setContentsMargins(10, 8, 10, 10)
        self.defects_text = QTextEdit()
        self.defects_text.setReadOnly(True)
        self.defects_text.setMinimumHeight(90)
        self.defects_text.setMaximumHeight(140)
        self.defects_text.setPlainText("No inspection yet")
        defects_layout.addWidget(self.defects_text)
        right_layout.addWidget(defects_group)

        right_layout.addStretch()

        # Save button — outside scroll, always visible at the bottom
        save_btn = QPushButton("💾 Save Card")
        save_btn.setProperty("primary", True)
        save_btn.setMinimumHeight(44)
        save_btn.clicked.connect(self._save_card)
        right_outer.addWidget(save_btn)

        splitter.addWidget(right_panel)
        layout.addWidget(splitter, 1)

        self.status_label = QLabel("Ready.")
        layout.addWidget(self.status_label)

    def refresh_api_key_banner(self):
        """Show/hide the no-API-key banner based on current env state."""
        self.api_key_banner.setVisible(not os.environ.get('ANTHROPIC_API_KEY'))

    def _scan_card(self):
        source = self.source_combo.currentText()
        if "no TWAIN" in source.lower():
            QMessageBox.warning(self, "No Scanner", "Use Load buttons or connect a TWAIN scanner.")
            return

        duplex = self.duplex_check.isChecked()
        self.scan_card_btn.setEnabled(False)
        self.status_label.setText(f"Scanning{'  (Duplex)' if duplex else ''}...")

        self._worker = ScanWorker(
            self.scanner, source_name=source, dpi=self.dpi_spin.value(), duplex=duplex
        )
        self._worker.finished.connect(self._scan_done)
        self._worker.error.connect(self._scan_error)
        self._worker.start()

    def _scan_done(self, result):
        self.scan_card_btn.setEnabled(True)

        images = result if isinstance(result, list) else ([result] if result is not None else [])
        if not images:
            self.status_label.setText("No images received from scanner.")
            return

        self._accumulated_images.extend(images)

        duplex = self.duplex_check.isChecked()
        pages_per_card = 2 if duplex else 1
        card_count = len(self._accumulated_images) // pages_per_card

        self.status_label.setText(
            f"✅ {len(images)} page(s) scanned — {card_count} card(s) total so far."
        )

        # Ask whether to scan more or process what we have
        dlg = _ScanMoreDialog(card_count, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # Scan more — trigger another scan run
            self._scan_card()
        else:
            # Done — process everything accumulated
            self._finish_scanning()

    def _load_card_images(self, images: list):
        if len(images) >= 2:
            self.current_front_img = images[0]
            self.current_back_img = images[1]
            self.front_view.set_image(images[0])
            self.back_view.set_image(images[1])
        elif len(images) == 1:
            self.current_front_img = images[0]
            self.current_back_img = None
            self.front_view.set_image(images[0])
            self.back_view.set_image(None)

    def _finish_scanning(self):
        """Split accumulated pages into per-card chunks and open batch review."""
        images = self._accumulated_images
        self._accumulated_images = []

        duplex = self.duplex_check.isChecked()
        pages_per_card = 2 if duplex else 1
        chunks = [images[i:i + pages_per_card]
                  for i in range(0, len(images), pages_per_card)]

        if len(chunks) == 1:
            # Single card — auto-straighten, then load into the viewer
            from utils.image_ops import deskew
            chunk = [deskew(im) for im in chunks[0]]
            self._load_card_images(chunk)
            self._auto_identify()
            self._inspect()
            self.status_label.setText("✅ Card ready — review and save.")
            return

        # Multiple cards — open batch review dialog
        from ui.batch_review_dialog import BatchReviewDialog
        dlg = BatchReviewDialog(
            chunks, self.db, self.identifier,
            self.inspector, self.valuator, self
        )
        dlg.exec()
        self.status_label.setText("✅ Batch session complete.")
        self.card_added.emit()

    def _make_rotate_bar(self, side: str):
        """Build a row of transform buttons (CCW, 180, CW, deskew) for a side."""
        bar = QHBoxLayout()
        bar.setSpacing(4)
        buttons = [
            ("↺ 90°",     'ccw',    f"Rotate {side} 90 degrees counter-clockwise"),
            ("↻ 180°",    '180',    f"Rotate {side} 180 degrees"),
            ("↻ 90°",     'cw',     f"Rotate {side} 90 degrees clockwise"),
            ("📐 Straighten", 'deskew', f"Auto-straighten the {side} image"),
        ]
        for label, op, a11y in buttons:
            btn = QPushButton(label)
            btn.setMinimumHeight(32)
            btn.setToolTip(a11y)
            btn.setAccessibleName(a11y)          # announced by Narrator
            btn.clicked.connect(lambda _=False, o=op: self._transform(side, o))
            bar.addWidget(btn)
        return bar

    def _transform(self, side: str, op: str):
        """Apply a rotation/deskew transform to the front or back image."""
        from utils import image_ops
        img = self.current_front_img if side == 'front' else self.current_back_img
        if img is None:
            return

        ops = {
            'cw':     (image_ops.rotate_90_cw,  "rotated 90° CW"),
            'ccw':    (image_ops.rotate_90_ccw, "rotated 90° CCW"),
            '180':    (image_ops.rotate_180,    "rotated 180°"),
            'deskew': (image_ops.deskew,        "straightened"),
        }
        fn, desc = ops[op]
        result = fn(img)

        if side == 'front':
            self.current_front_img = result
            self.front_view.set_image(result)
        else:
            self.current_back_img = result
            self.back_view.set_image(result)

        self.status_label.setText(f"✅ {side.capitalize()} {desc}")

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
        self.scan_card_btn.setEnabled(True)
        self.status_label.setText(f"Error: {msg}")
        QMessageBox.critical(self, "Scan Error", msg)

    def _auto_identify(self):
        if self.current_front_img is None:
            return
        try:
            info = self.identifier.identify_card(self.current_front_img, self.current_back_img)
            self._last_identify = info

            source = (info or {}).get('source', '')
            if source.startswith('trial_'):
                self.status_label.setText(
                    "Free trial used — add your own key to keep auto-identifying."
                )
                self.key_setup_requested.emit(source)
                return

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
            from core.grading import resolve_condition
            self.current_inspection = resolve_condition(
                getattr(self, '_last_identify', None), self.current_front_img, self.inspector)
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
            name      = self.name_edit.text().strip()
            set_name  = self.set_edit.text().strip()
            game      = self.game_combo.currentText().strip()
            grade     = self.current_inspection['grade'] if self.current_inspection else None
            score     = self.current_inspection['score'] if self.current_inspection else 85.0

            # Fetch value from eBay before saving
            self.status_label.setText("💰 Fetching market value...")
            try:
                valuation = self.valuator.value_summary(name, set_name, game, grade, score)
                estimated = valuation.get('estimated', 0.0)
                val_source = valuation.get('source', '')
                val_sample = valuation.get('sample', 0)
            except Exception:
                estimated = 0.0
                val_source = ''
                val_sample = 0

            card_data = {
                'name': name,
                'set_name': set_name,
                'card_number': self.number_edit.text().strip(),
                'rarity': self.rarity_edit.text().strip(),
                'game': game,
                'year': self.year_spin.value(),
                'language': self.lang_edit.text().strip() or "English",
                'foil': 1 if self.foil_check.isChecked() else 0,
                'front_scan_path': front_path,
                'back_scan_path': back_path,
                'purchase_price': float(self.purchase_spin.value()),
                'quantity': int(self.qty_spin.value()),
                'notes': self.notes_edit.toPlainText().strip(),
                'condition_grade': grade,
                'condition_score': score,
                'defects': self.current_inspection.get('defects', []) if self.current_inspection else [],
                'estimated_value': estimated,
            }

            # Detect whether this will merge into an existing card
            existing_id = self.db.find_duplicate(card_data)
            card_id = self.db.add_card(card_data)

            val_msg = (f"\n💰 Est. value: ${estimated:.2f} ({val_source}, {val_sample} sales)"
                       if estimated > 0 else "\n💰 No market data found")
            if existing_id is not None:
                merged = self.db.get_card(card_id)
                qty = merged.get('quantity', '?') if merged else '?'
                QMessageBox.information(self, "Quantity Updated",
                    f"🔁 Duplicate of an existing card — quantity is now {qty}.\n"
                    f"{name}{val_msg}")
            else:
                QMessageBox.information(self, "Success",
                    f"✅ Card saved!\nID: {card_id}  •  {name}{val_msg}")

            # Clear form for next card
            self._reset_form()
            self.card_added.emit()  # Refresh collection tab

        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Error saving card:\n{str(e)}")
            logger.warning("Save error: %s", e)
            
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


class _ScanMoreDialog(QDialog):
    """After each scan run: Scan More Cards or End Scanning."""

    def __init__(self, card_count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scan Complete")
        self.setMinimumWidth(340)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        msg = QLabel(
            f"<b>{card_count} card(s)</b> scanned so far.<br><br>"
            "Add more cards to the feeder and scan again,<br>"
            "or end scanning to review and save."
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        btn_row = QHBoxLayout()

        more_btn = QPushButton("📷 Scan More Cards")
        more_btn.setProperty("primary", True)
        more_btn.setMinimumHeight(40)
        more_btn.clicked.connect(self.accept)

        end_btn = QPushButton("✅ End Scanning")
        end_btn.setMinimumHeight(40)
        end_btn.clicked.connect(self.reject)

        btn_row.addWidget(more_btn)
        btn_row.addWidget(end_btn)
        layout.addLayout(btn_row)


