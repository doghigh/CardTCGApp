# ui/dialogs.py
import io
import json
from pathlib import Path
from typing import Dict, List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextEdit, QGroupBox,
    QDialogButtonBox, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage

import cv2


class CardDetailDialog(QDialog):
    """Full card detail dialog with images and data."""

    def __init__(self, card: Dict, valuations: List[Dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Card #{card.get('id')} - {card.get('name', 'Unknown')}")
        self.resize(940, 700)

        layout = QHBoxLayout(self)

        # Images
        img_panel = QVBoxLayout()
        for label, key in [("Front", 'front_scan_path'), ("Back", 'back_scan_path')]:
            grp = QGroupBox(label)
            gl = QVBoxLayout(grp)
            view = QLabel()
            view.setMinimumSize(320, 440)
            view.setAlignment(Qt.AlignmentFlag.AlignCenter)
            view.setStyleSheet("background: #1a202c; border: 1px solid #2d3748;")

            path = card.get(key)
            if path and Path(path).exists():
                img = cv2.imread(path)
                if img is not None:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    h, w = img.shape[:2]
                    qimg = QImage(img.data, w, h, 3 * w, QImage.Format.Format_RGB888)
                    pixmap = QPixmap.fromImage(qimg).scaled(320, 440, Qt.AspectRatioMode.KeepAspectRatio)
                    view.setPixmap(pixmap)

            gl.addWidget(view)
            img_panel.addWidget(grp)

        layout.addLayout(img_panel)

        # Info
        right = QVBoxLayout()
        info = QTextEdit()
        info.setReadOnly(True)

        defects = json.loads(card.get('defects_json', '[]')) if card.get('defects_json') else []

        info.setHtml(f"""
            <h2>{card.get('name')}</h2>
            <p><b>Set:</b> {card.get('set_name')}<br>
               <b>Number:</b> {card.get('card_number')}<br>
               <b>Grade:</b> {card.get('condition_grade')} ({card.get('condition_score')}/100)</p>
            <h3>Defects</h3>
            <pre>{"\n".join([f"• {d.get('type')} @ {d.get('location')}" for d in defects]) or "None"}</pre>
            <h3>Valuations</h3>
            <pre>{"\n".join([f"• {v['source']}: ${v['value']}" for v in valuations]) or "None"}</pre>
        """)

        right.addWidget(info)
        btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn.rejected.connect(self.reject)
        right.addWidget(btn)

        layout.addLayout(right)