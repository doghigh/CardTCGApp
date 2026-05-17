import csv
import io
import json
import os
from pathlib import Path
from typing import Dict, List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit, QGroupBox,
    QDialogButtonBox, QMessageBox, QInputDialog, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QFileDialog
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
        except Exception:
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


class LoginDialog(QDialog):
    """Authentication dialog supporting password, TOTP, Windows Hello, and recovery codes."""

    def __init__(self, auth, hello_auth=None, parent=None):
        super().__init__(parent)
        self.auth = auth
        self.hello_auth = hello_auth
        self.setWindowTitle("Trading Card Manager - Login")
        self.setFixedSize(400, 300)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)

        title = QLabel("Trading Card Manager")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 17px; font-weight: bold; margin-bottom: 4px;")
        layout.addWidget(title)

        sub = QLabel("Enter your credentials to continue.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color: #a0aec0; font-size: 12px;")
        layout.addWidget(sub)

        if self.auth.has_password():
            layout.addWidget(QLabel("Password:"))
            self.pw_edit = QLineEdit()
            self.pw_edit.setPlaceholderText("Master password")
            self.pw_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.pw_edit.returnPressed.connect(self._try_login)
            layout.addWidget(self.pw_edit)
        else:
            self.pw_edit = None

        has_totp = hasattr(self.auth, 'totp_secret_file') and self.auth.totp_secret_file.exists()
        if has_totp:
            layout.addWidget(QLabel("Authenticator Code (6 digits):"))
            self.totp_edit = QLineEdit()
            self.totp_edit.setPlaceholderText("123456")
            self.totp_edit.setMaxLength(6)
            self.totp_edit.returnPressed.connect(self._try_login)
            layout.addWidget(self.totp_edit)
        else:
            self.totp_edit = None

        if self.hello_auth and self.hello_auth.is_available():
            hello_btn = QPushButton("Use Windows Hello")
            hello_btn.clicked.connect(self._try_hello)
            layout.addWidget(hello_btn)

        login_btn = QPushButton("Login")
        login_btn.setDefault(True)
        login_btn.setMinimumHeight(36)
        login_btn.clicked.connect(self._try_login)
        layout.addWidget(login_btn)

        recovery_btn = QPushButton("Use recovery code")
        recovery_btn.setFlat(True)
        recovery_btn.setStyleSheet("color: #63b3ed; text-decoration: underline;")
        recovery_btn.clicked.connect(self._try_recovery)
        layout.addWidget(recovery_btn)

    def _try_login(self):
        if self.pw_edit and not self.auth.check_password(self.pw_edit.text()):
            QMessageBox.warning(self, "Wrong Password", "Incorrect password. Try again.")
            self.pw_edit.clear()
            self.pw_edit.setFocus()
            return
        if self.totp_edit and not self.auth.verify_totp(self.totp_edit.text()):
            QMessageBox.warning(self, "Invalid Code", "Authenticator code is incorrect or expired.")
            self.totp_edit.clear()
            self.totp_edit.setFocus()
            return
        self.accept()

    def _try_hello(self):
        if self.hello_auth and self.hello_auth.request_biometric_login():
            self.accept()
        else:
            QMessageBox.warning(self, "Authentication Failed", "Windows Hello authentication did not succeed.")

    def _try_recovery(self):
        code, ok = QInputDialog.getText(self, "Recovery Code", "Enter your recovery code:")
        if ok:
            if self.auth.verify_recovery_code(code.strip()):
                self.accept()
            else:
                QMessageBox.warning(self, "Invalid Code", "Recovery code not recognized or already used.")


class CsvMappingDialog(QDialog):
    """Maps CSV columns to card database fields for batch import."""

    FIELDS = [
        'name', 'set_name', 'card_number', 'rarity', 'game', 'year',
        'language', 'foil', 'quantity', 'estimated_value', 'purchase_price',
        'condition_grade', 'condition_score', 'notes', 'front_scan_path',
    ]

    def __init__(self, csv_path: str, parent=None):
        super().__init__(parent)
        self.csv_path = csv_path
        self.mapping: Dict[str, str] = {}
        self.setWindowTitle("CSV Column Mapping")
        self.resize(560, 480)
        self._load_headers()
        self._build_ui()

    def _load_headers(self):
        try:
            with open(self.csv_path, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                self.headers = next(reader, [])
        except Exception:
            self.headers = []

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"File: {Path(self.csv_path).name}"))
        layout.addWidget(QLabel("Map CSV columns to card fields:"))

        self.combos: Dict[str, QComboBox] = {}
        table = QTableWidget(len(self.FIELDS), 2)
        table.setHorizontalHeaderLabels(["Card Field", "CSV Column"])
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        for i, field in enumerate(self.FIELDS):
            table.setItem(i, 0, QTableWidgetItem(field))
            combo = QComboBox()
            combo.addItem("(skip)")
            combo.addItems(self.headers)
            # Auto-match by name
            for j, h in enumerate(self.headers):
                if h.lower().replace(' ', '_') == field.lower():
                    combo.setCurrentIndex(j + 1)
                    break
            self.combos[field] = combo
            table.setCellWidget(i, 1, combo)

        layout.addWidget(table)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_accept(self):
        self.mapping = {
            field: combo.currentText()
            for field, combo in self.combos.items()
            if combo.currentText() != "(skip)"
        }
        self.accept()
