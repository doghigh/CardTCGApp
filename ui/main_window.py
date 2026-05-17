# ui/main_window.py
import sys
import os
from pathlib import Path

from PyQt6.QtWidgets import QMainWindow, QTabWidget, QStatusBar, QAction, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut

from core.database import Database
from core.scanner import ScannerInterface
from core.inspector import CardInspector
from core.identifier import CardIdentifier
from core.valuator import CardValuator
from core.auth import AuthManager, WindowsHelloAuth, LoginDialog

from ui.scan_tab import ScanTab
from ui.batch_tab import BatchTab
from ui.collection_tab import CollectionTab
from ui.reports_tab import ReportsTab
from ui.dialogs import CardDetailDialog   # if needed


APP_DIR = Path(os.environ.get('APPDATA', Path.home())) / "TradingCardManager"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.auth = AuthManager()
        self.hello_auth = WindowsHelloAuth()

        # Login
        if self.auth.has_password() or (hasattr(self.auth, 'totp_secret_file') and self.auth.totp_secret_file.exists()):
            dlg = LoginDialog(self.auth, self.hello_auth, self)
            if dlg.exec() != 1:
                sys.exit(0)

        self.setWindowTitle("Trading Card Manager v1.1.0")
        self.resize(1580, 960)

        self.db = Database(APP_DIR / "cards.db")
        self.scanner = ScannerInterface()
        self.inspector = CardInspector()
        self.identifier = CardIdentifier()
        self.valuator = CardValuator()

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.scan_tab = ScanTab(self.db, self.scanner, self.inspector, self.identifier, self.valuator)
        self.batch_tab = BatchTab(self.db, self.scanner, self.inspector, self.identifier, self.valuator)
        self.collection_tab = CollectionTab(self.db, self.valuator)
        self.reports_tab = ReportsTab(self.db)

        self.scan_tab.card_added.connect(self.collection_tab.refresh)
        self.batch_tab.cards_added.connect(self.collection_tab.refresh)
        self.scan_tab.card_added.connect(self.reports_tab.refresh)
        self.batch_tab.cards_added.connect(self.reports_tab.refresh)

        self.tabs.addTab(self.scan_tab, "🃏 Scan & Add")
        self.tabs.addTab(self.batch_tab, "📦 Batch Import")
        self.tabs.addTab(self.collection_tab, "📦 Collection")
        self.tabs.addTab(self.reports_tab, "📊 Reports")

        self.setCentralWidget(self.tabs)

        self._setup_shortcuts()
        self._setup_menu()

        sb = QStatusBar()
        self.setStatusBar(sb)
        sb.showMessage("Ready • F1 for shortcuts")

    def _setup_shortcuts(self):
        for i in range(4):
            QShortcut(QKeySequence(f"Ctrl+{i+1}"), self, lambda idx=i: self.tabs.setCurrentIndex(idx))

        QShortcut(QKeySequence("Ctrl+N"), self, self._new_card)
        QShortcut(QKeySequence("Ctrl+Shift+N"), self, lambda: getattr(self.scan_tab, '_start_continuous_scan', lambda: None)())
        QShortcut(QKeySequence("Ctrl+F"), self, self._focus_search)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_current_card)
        QShortcut(QKeySequence("F5"), self, self._refresh_all)
        QShortcut(QKeySequence("F1"), self, self._show_help)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.close)

    def _new_card(self):
        self.tabs.setCurrentIndex(0)
        if hasattr(self.scan_tab, '_reset'):
            self.scan_tab._reset()

    def _focus_search(self):
        if self.tabs.currentIndex() == 2 and hasattr(self.collection_tab, 'search_edit'):
            self.collection_tab.search_edit.setFocus()

    def _save_current_card(self):
        if self.tabs.currentIndex() == 0 and hasattr(self.scan_tab, '_save_card'):
            self.scan_tab._save_card()

    def _refresh_all(self):
        if hasattr(self.collection_tab, 'refresh'):
            self.collection_tab.refresh()
        if hasattr(self.reports_tab, 'refresh'):
            self.reports_tab.refresh()

    def _show_help(self):
        # Full help text from previous version
        QMessageBox.information(self, "Keyboard Shortcuts", "...")  # paste full table if needed

    def _setup_menu(self):
        # File and Help menus from previous version
        pass