import io
import json
import os
from pathlib import Path
from typing import Dict, List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QGroupBox,
    QDialogButtonBox, QMessageBox, QInputDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage

import cv2


class CardDetailDialog(QDialog):
    """Detailed view of a single card with images and valuations."""

    def __init__(self, card: Dict, valuations: List[Dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Card #{card.get('id')} - {card.get('name', 'Unknown')}")
        self.resize(920, 680)

        layout = QHBoxLayout(self)

        # Images panel
        img_panel = QVBoxLayout()
        for label, key in [("Front", 'front_scan_path'), ("Back", 'back_scan_path')]:
            grp = QGroupBox(label)
            gl = QVBoxLayout(grp)
            view = QLabel()
            view.setMinimumSize(300, 420)
            view.setAlignment(Qt.AlignmentFlag.AlignCenter)
            view.setStyleSheet("background: #1a202c; border: 1px solid #2d3748;")

            path = card.get(key)
            if path and Path(path).exists():
                img = cv2.imread(path)
                if img is not None:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    h, w = img.shape[:2]
                    qimg = QImage(img.data, w, h, 3 * w, QImage.Format.Format_RGB888)
                    pixmap = QPixmap.fromImage(qimg)
                    scaled = pixmap.scaled(300, 420, Qt.AspectRatioMode.KeepAspectRatio)
                    view.setPixmap(scaled)

            gl.addWidget(view)
            img_panel.addWidget(grp)

        layout.addLayout(img_panel)

        # Information panel
        right = QVBoxLayout()
        info_text = QTextEdit()
        info_text.setReadOnly(True)

        try:
            defects = json.loads(card.get('defects_json', '[]'))
        except:
            defects = []

        defect_lines = '\n'.join([
            f"• [{d.get('severity', '?').upper()}] {d.get('type', '').replace('_', ' ').title()} @ {d.get('location', '?')}"
            for d in defects
        ]) or "No defects detected."

        val_lines = '\n'.join([
            f"• {v['source']}: ${v['value']:.2f} ({(v.get('fetched_at') or '')[:10]})"
            for v in valuations
        ]) or "No valuations recorded."

        info_text.setHtml(f"""
            <h2>{card.get('name', 'Unknown')}</h2>
            <table cellpadding="4" width="100%">
                <tr><td><b>Set:</b></td><td>{card.get('set_name') or '-'}</td></tr>
                <tr><td><b>Card #:</b></td><td>{card.get('card_number') or '-'}</td></tr>
                <tr><td><b>Rarity:</b></td><td>{card.get('rarity') or '-'}</td></tr>
                <tr><td><b>Game:</b></td><td>{card.get('game') or '-'}</td></tr>
                <tr><td><b>Year:</b></td><td>{card.get('year') or '-'}</td></tr>
                <tr><td><b>Language:</b></td><td>{card.get('language') or '-'}</td></tr>
                <tr><td><b>Foil:</b></td><td>{'Yes' if card.get('foil') else 'No'}</td></tr>
                <tr><td><b>Quantity:</b></td><td>{card.get('quantity', 1)}</td></tr>
            </table>

            <h3>Condition</h3>
            <p><b>Grade:</b> {card.get('condition_grade') or 'Ungraded'}<br>
               <b>Score:</b> {card.get('condition_score', 0):.1f}/100</p>

            <h3>Defects</h3>
            <pre>{defect_lines}</pre>

            <h3>Valuations</h3>
            <pre>{val_lines}</pre>

            <h3>Financials</h3>
            <p><b>Estimated Value:</b> ${card.get('estimated_value', 0):.2f}<br>
               <b>Purchase Price:</b> ${card.get('purchase_price', 0):.2f}<br>
               <b>Net per card:</b> ${(card.get('estimated_value', 0) - card.get('purchase_price', 0)):.2f}</p>

            <h3>Notes</h3>
            <p>{card.get('notes') or 'No notes.'}</p>
        """)

        right.addWidget(info_text)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.reject)
        right.addWidget(btn_box)

        layout.addLayout(right)


# Optional: Keep LoginDialog and CsvMappingDialog here too if you want everything in one place
# (They were provided in previous responses)import io
import json
import os
from pathlib import Path
from typing import Dict, List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QGroupBox,
    QDialogButtonBox, QMessageBox, QInputDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage

import cv2


class CardDetailDialog(QDialog):
    """Detailed view of a single card with images and valuations."""

    def __init__(self, card: Dict, valuations: List[Dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Card #{card.get('id')} - {card.get('name', 'Unknown')}")
        self.resize(920, 680)

        layout = QHBoxLayout(self)

        # Images panel
        img_panel = QVBoxLayout()
        for label, key in [("Front", 'front_scan_path'), ("Back", 'back_scan_path')]:
            grp = QGroupBox(label)
            gl = QVBoxLayout(grp)
            view = QLabel()
            view.setMinimumSize(300, 420)
            view.setAlignment(Qt.AlignmentFlag.AlignCenter)
            view.setStyleSheet("background: #1a202c; border: 1px solid #2d3748;")

            path = card.get(key)
            if path and Path(path).exists():
                img = cv2.imread(path)
                if img is not None:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    h, w = img.shape[:2]
                    qimg = QImage(img.data, w, h, 3 * w, QImage.Format.Format_RGB888)
                    pixmap = QPixmap.fromImage(qimg)
                    scaled = pixmap.scaled(300, 420, Qt.AspectRatioMode.KeepAspectRatio)
                    view.setPixmap(scaled)

            gl.addWidget(view)
            img_panel.addWidget(grp)

        layout.addLayout(img_panel)

        # Information panel
        right = QVBoxLayout()
        info_text = QTextEdit()
        info_text.setReadOnly(True)

        try:
            defects = json.loads(card.get('defects_json', '[]'))
        except:
            defects = []

        defect_lines = '\n'.join([
            f"• [{d.get('severity', '?').upper()}] {d.get('type', '').replace('_', ' ').title()} @ {d.get('location', '?')}"
            for d in defects
        ]) or "No defects detected."

        val_lines = '\n'.join([
            f"• {v['source']}: ${v['value']:.2f} ({(v.get('fetched_at') or '')[:10]})"
            for v in valuations
        ]) or "No valuations recorded."

        info_text.setHtml(f"""
            <h2>{card.get('name', 'Unknown')}</h2>
            <table cellpadding="4" width="100%">
                <tr><td><b>Set:</b></td><td>{card.get('set_name') or '-'}</td></tr>
                <tr><td><b>Card #:</b></td><td>{card.get('card_number') or '-'}</td></tr>
                <tr><td><b>Rarity:</b></td><td>{card.get('rarity') or '-'}</td></tr>
                <tr><td><b>Game:</b></td><td>{card.get('game') or '-'}</td></tr>
                <tr><td><b>Year:</b></td><td>{card.get('year') or '-'}</td></tr>
                <tr><td><b>Language:</b></td><td>{card.get('language') or '-'}</td></tr>
                <tr><td><b>Foil:</b></td><td>{'Yes' if card.get('foil') else 'No'}</td></tr>
                <tr><td><b>Quantity:</b></td><td>{card.get('quantity', 1)}</td></tr>
            </table>

            <h3>Condition</h3>
            <p><b>Grade:</b> {card.get('condition_grade') or 'Ungraded'}<br>
               <b>Score:</b> {card.get('condition_score', 0):.1f}/100</p>

            <h3>Defects</h3>
            <pre>{defect_lines}</pre>

            <h3>Valuations</h3>
            <pre>{val_lines}</pre>

            <h3>Financials</h3>
            <p><b>Estimated Value:</b> ${card.get('estimated_value', 0):.2f}<br>
               <b>Purchase Price:</b> ${card.get('purchase_price', 0):.2f}<br>
               <b>Net per card:</b> ${(card.get('estimated_value', 0) - card.get('purchase_price', 0)):.2f}</p>

            <h3>Notes</h3>
            <p>{card.get('notes') or 'No notes.'}</p>
        """)

        right.addWidget(info_text)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.reject)
        right.addWidget(btn_box)

        layout.addLayout(right)


# Optional: Keep LoginDialog and CsvMappingDialog here too if you want everything in one place
# (They were provided in previous responses)
