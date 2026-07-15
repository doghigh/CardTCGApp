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
    QCheckBox, QProgressBar, QTextEdit, QFileDialog, QMessageBox, QGroupBox,
    QTimeEdit, QSpinBox
)
from PyQt6.QtCore import QThread, pyqtSignal, QTime

from core.database import Database
from core.scanner import ScannerInterface
from core.inspector import CardInspector
from core.identifier import CardIdentifier
from core.valuator import CardValuator
from core.watcher import WatchConfig
from ui.dialogs import CsvMappingDialog


from core.paths import SCANS_DIR
SCANS_DIR.mkdir(parents=True, exist_ok=True)


class ImageBatchWorker(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(int)

    # pairing modes
    SINGLE      = "single"       # each image/page = one card
    SEQUENTIAL  = "sequential"   # in order: 1=front, 2=back, 3=front, ...
    FILENAME    = "filename"     # pair by *_front / *_back style names
    ORIENTATION = "orientation"  # portrait=front, landscape=back; pair adjacent

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

    # ── page discovery (images + PDF pages) ───────────────────────────────────

    @staticmethod
    def _image_size(path):
        """(width, height) without fully decoding, or None."""
        try:
            from PIL import Image
            with Image.open(path) as im:
                return im.size
        except Exception:
            try:
                arr = cv2.imread(str(path))
                if arr is not None:
                    return arr.shape[1], arr.shape[0]
            except Exception:
                pass
        return None

    def _gather_pages(self):
        """
        Build a flat, ordered list of page descriptors from the folder.
        Each descriptor: {source, page, kind, stem, side} where side is
        'front' (portrait) or 'back' (landscape) by aspect ratio.
        """
        from utils import pdf_utils
        files = sorted(
            list(self.folder.glob("*.png")) + list(self.folder.glob("*.jpg")) +
            list(self.folder.glob("*.jpeg")) + list(self.folder.glob("*.pdf"))
        )
        pages = []
        for f in files:
            if pdf_utils.is_pdf(f):
                sizes = pdf_utils.page_sizes(f)
                for idx, (w, h) in enumerate(sizes):
                    stem = f.stem if len(sizes) == 1 else f"{f.stem}_p{idx + 1}"
                    pages.append({"source": f, "page": idx, "kind": "pdf",
                                  "stem": stem,
                                  "side": "front" if h >= w else "back"})
            else:
                size = self._image_size(f)
                side = "front"
                if size:
                    side = "front" if size[1] >= size[0] else "back"
                pages.append({"source": f, "page": None, "kind": "image",
                              "stem": f.stem, "side": side})
        return pages

    # ── pairing ────────────────────────────────────────────────────────────────

    @classmethod
    def _pair_pages(cls, pages, mode: str):
        """Group page descriptors into (front, back|None) tuples."""
        if mode == cls.SINGLE:
            return [(p, None) for p in pages]

        if mode == cls.SEQUENTIAL:
            pairs = []
            for i in range(0, len(pages), 2):
                front = pages[i]
                back = pages[i + 1] if i + 1 < len(pages) else None
                pairs.append((front, back))
            return pairs

        if mode == cls.ORIENTATION:
            # Anchor on each landscape BACK and pair it with the FOLLOWING
            # portrait FRONT (vintage Topps order: back, then front). A leading
            # orphan front (its back in a prior batch) becomes a single card.
            pairs = []
            i, n = 0, len(pages)
            while i < n:
                d = pages[i]
                nxt = pages[i + 1] if i + 1 < n else None
                if d["side"] == "back" and nxt and nxt["side"] == "front":
                    pairs.append((nxt, d))          # (front, back)
                    i += 2
                else:
                    pairs.append((d, None))          # orphan front / lone back
                    i += 1
            return pairs

        # FILENAME — match *_front / *_back (also f/b, front/rear, 1/2 suffixes)
        import re
        BACK_TOKENS  = ("back", "rear", "rev", "reverse")
        FRONT_TOKENS = ("front", "frnt", "face", "obverse")

        def classify(stem: str):
            s = stem.lower()
            for t in BACK_TOKENS:
                if t in s:
                    return "back", re.sub(rf"[ _\-]*{t}", "", s)
            for t in FRONT_TOKENS:
                if t in s:
                    return "front", re.sub(rf"[ _\-]*{t}", "", s)
            m = re.search(r"[ _\-]([fb])$", s)
            if m:
                return ("front" if m.group(1) == "f" else "back"), s[:m.start()]
            m = re.search(r"[ _\-]([12])$", s)
            if m:
                return ("front" if m.group(1) == "1" else "back"), s[:m.start()]
            return None, s

        groups: dict = {}
        order = []
        for p in pages:
            side, base = classify(p["stem"])
            base = re.sub(r"[ _\-]+$", "", base).strip()
            if base not in groups:
                groups[base] = {"front": None, "back": None}
                order.append(base)
            slot = side or "front"
            if groups[base][slot] is None:
                groups[base][slot] = p
            elif groups[base]["back"] is None:
                groups[base]["back"] = p
        return [(groups[b]["front"] or groups[b]["back"],
                 groups[b]["back"] if groups[b]["front"] else None)
                for b in order]

    # ── load a page descriptor to an RGB image ────────────────────────────────

    def _load(self, desc):
        if desc is None:
            return None
        from utils import pdf_utils
        from utils.image_ops import deskew
        if desc["kind"] == "pdf":
            img = pdf_utils.render_page(desc["source"], desc["page"], dpi=300)
        else:
            img = self.scanner.scan_from_file(str(desc["source"]))
        if img is None:
            return None
        try:
            return deskew(img)
        except Exception:
            return img

    # ── run ────────────────────────────────────────────────────────────────────

    def run(self):
        pages = self._gather_pages()
        pairs = self._pair_pages(pages, self.pairing)
        added = 0
        total = max(1, len(pairs))

        for i, (front_desc, back_desc) in enumerate(pairs):
            progress_pct = int((i + 1) / total * 100)
            label = front_desc["stem"] if front_desc else "?"
            try:
                self.progress.emit(f"Processing {label}…", progress_pct)

                front = self._load(front_desc)
                if front is None:
                    continue
                back = self._load(back_desc)

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
                    'name': info.get('name') or label,
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
                    'notes': f"Batch import from {label}",
                }

                self.db.add_card(card_data)
                added += 1
                sides = "front+back" if back is not None else "front"
                self.progress.emit(f"✅ Saved: {card_data['name']} ({sides})", progress_pct)

            except Exception as e:
                self.progress.emit(f"❌ Error on {label}: {str(e)[:80]}", progress_pct)

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
                 identifier: CardIdentifier, valuator: CardValuator,
                 watch_config: WatchConfig = None, run_watch_now=None):
        super().__init__()
        self.db = db
        self.scanner = scanner
        self.inspector = inspector
        self.identifier = identifier
        self.valuator = valuator
        self.watch_config = watch_config or WatchConfig()
        self._run_watch_now = run_watch_now   # callback into main window
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
            "Front/back auto — by orientation (sideways backs)",
        ])
        self.pairing_combo.setMinimumWidth(340)
        self.pairing_combo.setToolTip(
            "How to group the files (images or PDFs) in the folder.\n"
            "• Sequential: paired in order front, back, front, back…\n"
            "• By filename: matches name_front with name_back\n"
            "• By orientation: portrait pages are fronts, landscape pages are\n"
            "  backs (e.g. vintage Topps); each back pairs with its front.")
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

        # Watch-folder auto-import
        layout.addWidget(self._build_watch_group())

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

    def _build_watch_group(self) -> QGroupBox:
        cfg = self.watch_config
        grp = QGroupBox("🕒 Auto-Import Watch Folder")
        v = QVBoxLayout(grp)
        v.setContentsMargins(12, 24, 12, 12)
        v.setSpacing(8)

        self.watch_enable = QCheckBox("Enable — automatically import images dropped in a folder")
        self.watch_enable.setChecked(cfg.enabled)
        self.watch_enable.stateChanged.connect(self._save_watch)
        v.addWidget(self.watch_enable)

        # Folder picker
        f_row = QHBoxLayout()
        self.watch_folder_btn = QPushButton("📁 Choose Watch Folder")
        self.watch_folder_btn.setMaximumWidth(220)
        self.watch_folder_btn.clicked.connect(self._choose_watch_folder)
        self.watch_folder_label = QLabel(cfg.folder or "No folder selected")
        self.watch_folder_label.setStyleSheet("color: #8b8fa8; font-size: 12px;")
        f_row.addWidget(self.watch_folder_btn)
        f_row.addWidget(self.watch_folder_label, 1)
        v.addLayout(f_row)

        # Schedule row
        s_row = QHBoxLayout()
        s_row.addWidget(QLabel("Schedule:"))
        self.watch_mode = QComboBox()
        self.watch_mode.addItems(["Daily at a set time", "Every N minutes"])
        self.watch_mode.setCurrentIndex(0 if cfg.mode == "daily" else 1)
        self.watch_mode.currentIndexChanged.connect(self._on_watch_mode_changed)
        s_row.addWidget(self.watch_mode)

        self.watch_time = QTimeEdit()
        self.watch_time.setDisplayFormat("HH:mm")
        try:
            hh, mm = (int(x) for x in cfg.time.split(":"))
        except ValueError:
            hh, mm = 2, 0
        self.watch_time.setTime(QTime(hh, mm))
        self.watch_time.timeChanged.connect(self._save_watch)
        s_row.addWidget(self.watch_time)

        self.watch_interval = QSpinBox()
        self.watch_interval.setRange(5, 1440)
        self.watch_interval.setSuffix(" min")
        self.watch_interval.setValue(cfg.interval_min)
        self.watch_interval.valueChanged.connect(self._save_watch)
        s_row.addWidget(self.watch_interval)
        s_row.addStretch()
        v.addLayout(s_row)

        # Pairing + auto-value
        p_row = QHBoxLayout()
        p_row.addWidget(QLabel("Images:"))
        self.watch_pairing = QComboBox()
        self.watch_pairing.addItems([
            "One image = one card",
            "Front/back pairs — sequential",
            "Front/back pairs — by filename",
            "Front/back auto — by orientation",
        ])
        self.watch_pairing.setCurrentIndex(
            {"single": 0, "sequential": 1, "filename": 2, "orientation": 3}
            .get(cfg.pairing, 0))
        self.watch_pairing.currentIndexChanged.connect(self._save_watch)
        p_row.addWidget(self.watch_pairing)
        self.watch_autovalue = QCheckBox("Auto-value")
        self.watch_autovalue.setChecked(cfg.auto_value)
        self.watch_autovalue.stateChanged.connect(self._save_watch)
        p_row.addWidget(self.watch_autovalue)
        p_row.addStretch()
        v.addLayout(p_row)

        # Status + Run Now
        r_row = QHBoxLayout()
        self.watch_status = QLabel(self._watch_status_text())
        self.watch_status.setStyleSheet("color: #8b8fa8; font-size: 12px;")
        r_row.addWidget(self.watch_status, 1)
        run_now = QPushButton("▶ Run Now")
        run_now.clicked.connect(self._watch_run_now)
        r_row.addWidget(run_now)
        v.addLayout(r_row)

        self._on_watch_mode_changed()
        return grp

    def _on_watch_mode_changed(self):
        is_daily = self.watch_mode.currentIndex() == 0
        self.watch_time.setVisible(is_daily)
        self.watch_interval.setVisible(not is_daily)
        self._save_watch()

    def _choose_watch_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Watch Folder")
        if folder:
            self.watch_folder_label.setText(folder)
            self._save_watch()

    def _save_watch(self, *args):
        cfg = self.watch_config
        cfg.enabled = self.watch_enable.isChecked()
        lbl = self.watch_folder_label.text()
        cfg.folder = lbl if lbl and lbl != "No folder selected" else ""
        cfg.mode = "daily" if self.watch_mode.currentIndex() == 0 else "interval"
        cfg.time = self.watch_time.time().toString("HH:mm")
        cfg.interval_min = self.watch_interval.value()
        cfg.pairing = {0: "single", 1: "sequential", 2: "filename",
                       3: "orientation"}[self.watch_pairing.currentIndex()]
        cfg.auto_value = self.watch_autovalue.isChecked()
        cfg.save()
        if hasattr(self, "watch_status"):
            self.watch_status.setText(self._watch_status_text())

    def _watch_status_text(self) -> str:
        cfg = self.watch_config
        pending = len(cfg.pending_images()) if cfg.folder else 0
        base = cfg.next_run_text()
        last = f"  •  Last run: {cfg.last_run[:16].replace('T', ' ')}" if cfg.last_run else ""
        files = f"  •  {pending} file(s) waiting" if cfg.folder else ""
        return base + files + last

    def _watch_run_now(self):
        if not self.watch_config.folder:
            QMessageBox.information(self, "No Folder",
                                   "Choose a watch folder first.")
            return
        if callable(self._run_watch_now):
            self._run_watch_now(force=True)
        self.watch_status.setText(self._watch_status_text())

    def refresh_watch_status(self):
        if hasattr(self, "watch_status"):
            self.watch_status.setText(self._watch_status_text())

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
                3: ImageBatchWorker.ORIENTATION,
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
