import sys
import json
import secrets
import base64
import random
import io
from pathlib import Path
from typing import Optional, Dict

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox,
    QDialogButtonBox, QMessageBox, QFormLayout, QInputDialog, QPushButton
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage

import qrcode
import pyotp

from core.auth import AuthManager, WindowsHelloAuth


class LoginDialog(QDialog):
    """Modern login dialog with Windows Hello + optional TOTP."""

    def __init__(self, auth: AuthManager, hello_auth: WindowsHelloAuth, parent=None):
        super().__init__(parent)
        self.auth = auth
        self.hello_auth = hello_auth
        self.setWindowTitle("Trading Card Manager - Login")
        self.setFixedSize(520, 460)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(18)

        title = QLabel("🔐 Welcome Back")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Windows Hello
        self.hello_btn = QPushButton("🪪 Sign in with Windows Hello")
        self.hello_btn.setMinimumHeight(55)
        self.hello_btn.setStyleSheet("font-size: 15px;")
        self.hello_btn.clicked.connect(self.try_hello_login)
        if not self.hello_auth.is_available():
            self.hello_btn.setEnabled(False)
            self.hello_btn.setText("🪪 Windows Hello not available")
        layout.addWidget(self.hello_btn)

        layout.addWidget(QLabel("— or use Authenticator App —"))

        # TOTP
        self.totp_edit = QLineEdit()
        self.totp_edit.setPlaceholderText("Enter 6-digit code from Authenticator")
        self.totp_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.totp_edit.setStyleSheet("font-size: 18px; padding: 8px;")
        layout.addWidget(self.totp_edit)

        self.totp_btn = QPushButton("✅ Verify Code")
        self.totp_btn.clicked.connect(self.try_totp_login)
        layout.addWidget(self.totp_btn)

        setup_btn = QPushButton("📱 Setup Authenticator App")
        setup_btn.clicked.connect(self.setup_totp_qr)
        layout.addWidget(setup_btn)

        # Master Password fallback
        pw_btn = QPushButton("🔑 Use Master Password")
        pw_btn.clicked.connect(self.try_password_login)
        layout.addWidget(pw_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

        self.status = QLabel("")
        self.status.setStyleSheet("color: #f56565;")
        layout.addWidget(self.status)

    def try_hello_login(self):
        self.status.setText("Waiting for Windows Hello...")
        QApplication.processEvents()
        if self.hello_auth.request_biometric_login():
            self.accept()
        else:
            self.status.setText("Windows Hello failed.\nTry another method.")

    def try_totp_login(self):
        code = self.totp_edit.text().strip()
        if code and self.auth.verify_totp(code):
            self.accept()
        else:
            self.status.setText("❌ Invalid or expired code")

    def try_password_login(self):
        pw, ok = QInputDialog.getText(self, "Master Password", 
            "Enter master password:", QLineEdit.EchoMode.Password)
        if ok and pw and self.auth.check_password(pw):
            self.accept()
        else:
            self.status.setText("❌ Incorrect password")

    def setup_totp_qr(self):
        uri = self.auth.setup_totp()
        if not uri:
            QMessageBox.warning(self, "Error", "Could not generate TOTP secret")
            return

        # Generate QR
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # Show dialog
        qr_dialog = QDialog(self)
        qr_dialog.setWindowTitle("Scan with Authenticator App")
        qr_layout = QVBoxLayout(qr_dialog)

        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        qimg = QImage.fromData(img_byte_arr.getvalue())
        pixmap = QPixmap.fromImage(qimg)

        qr_label = QLabel()
        qr_label.setPixmap(pixmap.scaled(340, 340, Qt.AspectRatioMode.KeepAspectRatio))
        qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_layout.addWidget(qr_label)

        qr_layout.addWidget(QLabel(
            "1. Open Google Authenticator, Authy, or Microsoft Authenticator\n"
            "2. Scan this QR code\n"
            "3. Enter the 6-digit code above to test"
        ))

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(qr_dialog.accept)
        qr_layout.addWidget(close_btn)

        qr_dialog.exec()


class CsvMappingDialog(QDialog):
    """Dialog for mapping CSV columns to app fields."""

    def __init__(self, csv_path: Path, parent=None):
        super().__init__(parent)
        self.csv_path = csv_path
        self.setWindowTitle("CSV Column Mapping")
        self.resize(820, 620)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"Preview of: {csv_path.name}"))
        self.preview_table = QTableWidget()
        self.preview_table.setMinimumHeight(220)
        layout.addWidget(self.preview_table)

        # Mapping form
        form = QFormLayout()
        self.field_combos = {}

        fields = [
            ("name", "Card Name *", True),
            ("set_name", "Set Name", False),
            ("card_number", "Card Number", False),
            ("rarity", "Rarity", False),
            ("game", "Game", False),
            ("year", "Year", False),
            ("condition_grade", "Condition Grade", False),
            ("condition_score", "Condition Score", False),
            ("estimated_value", "Estimated Value", False),
            ("purchase_price", "Purchase Price", False),
            ("quantity", "Quantity", False),
            ("foil", "Foil/Holo", False),
            ("notes", "Notes", False),
        ]

        self.headers = self._load_headers()

        for field_key, label, required in fields:
            combo = QComboBox()
            combo.addItem("(Skip / No column)", None)
            for h in self.headers:
                combo.addItem(h, h)

            # Auto-match
            best = self._find_best_match(field_key, self.headers)
            if best:
                idx = combo.findData(best)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

            form.addRow(f"{label}:", combo)
            self.field_combos[field_key] = combo

        layout.addLayout(form)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | 
                                  QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self._load_preview()

    def _load_headers(self):
        try:
            with open(self.csv_path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                return list(reader.fieldnames) or []
        except:
            return []

    def _find_best_match(self, field: str, headers: list) -> Optional[str]:
        fl = field.lower()
        for h in headers:
            hl = h.lower().replace(" ", "_").replace("-", "")
            if fl in hl or hl in fl:
                return h
        return None

    def _load_preview(self):
        try:
            with open(self.csv_path, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)[:6]

            if not rows:
                return

            self.preview_table.setColumnCount(len(rows[0]))
            self.preview_table.setRowCount(len(rows))
            self.preview_table.setHorizontalHeaderLabels(rows[0])

            for r, row in enumerate(rows):
                for c, value in enumerate(row):
                    self.preview_table.setItem(r, c, QTableWidgetItem(str(value)))
        except Exception as e:
            QMessageBox.warning(self, "Preview Error", str(e))

    def get_mapping(self) -> Dict:
        mapping = {}
        for field, combo in self.field_combos.items():
            data = combo.currentData()
            if data:
                mapping[field] = data
        return mapping