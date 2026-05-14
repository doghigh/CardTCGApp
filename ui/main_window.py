import sys
import os
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QMenuBar, QAction, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
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


APP_DIR = Path(os.environ.get('APPDATA', Path.home())) / "TradingCardManager"


class MainWindow(QMainWindow):
    """Main application window with all tabs and keyboard shortcuts."""

    def __init__(self):
        super().__init__()

        # Authentication
        self.auth = AuthManager()
        self.hello_auth = WindowsHelloAuth()

        # Login check
        if self.auth.has_password() or (hasattr(self.auth, 'totp_secret_file') and self.auth.totp_secret_file.exists()):
            dlg = LoginDialog(self.auth, self.hello_auth, self)
            if dlg.exec() != 1:  # QDialog.Accepted
                sys.exit(0)

        # Window setup
        self.setWindowTitle("Trading Card Manager")
        self.resize(1580, 960)

        # Core components
        self.db = Database(APP_DIR / "cards.db")
        self.scanner = ScannerInterface()
        self.inspector = CardInspector()
        self.identifier = CardIdentifier()
        self.valuator = CardValuator()

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.scan_tab = ScanTab(self.db, self.scanner, self.inspector, self.identifier, self.valuator)
        self.batch_tab = BatchTab(self.db, self.scanner, self.inspector, self.identifier, self.valuator)
        self.collection_tab = CollectionTab(self.db, self.valuator)
        self.reports_tab = ReportsTab(self.db)

        # Signal connections
        self.scan_tab.card_added.connect(self.collection_tab.refresh)
        self.scan_tab.card_added.connect(self.reports_tab.refresh)
        self.batch_tab.cards_added.connect(self.collection_tab.refresh)
        self.batch_tab.cards_added.connect(self.reports_tab.refresh)

        # Add tabs
        self.tabs.addTab(self.scan_tab, "🃏 Scan & Add")
        self.tabs.addTab(self.batch_tab, "📦 Batch Import")
        self.tabs.addTab(self.collection_tab, "📦 Collection")
        self.tabs.addTab(self.reports_tab, "📊 Reports")

        self.setCentralWidget(self.tabs)

        # Setup shortcuts and menu
        self._setup_shortcuts()
        self._setup_menu()

        # Status bar
        sb = QStatusBar()
        self.setStatusBar(sb)
        sb.showMessage(f"Ready • Database: {APP_DIR / 'cards.db'} • Press F1 for shortcuts")

    def _setup_shortcuts(self):
        """Global keyboard shortcuts for accessibility and power use."""
        # Tab switching
        for i in range(4):
            QShortcut(QKeySequence(f"Ctrl+{i+1}"), self, 
                      lambda idx=i: self.tabs.setCurrentIndex(idx))

        # New card
        QShortcut(QKeySequence("Ctrl+N"), self, self._new_card)

        # Continuous scan
        QShortcut(QKeySequence("Ctrl+Shift+N"), self, 
                  lambda: self.scan_tab._start_continuous_scan() if hasattr(self.scan_tab, '_start_continuous_scan') else None)

        # Search focus
        QShortcut(QKeySequence("Ctrl+F"), self, self._focus_search)

        # Save current card
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_current_card)

        # Refresh
        QShortcut(QKeySequence("F5"), self, self._refresh_all)

        # Help
        QShortcut(QKeySequence("F1"), self, self._show_help)

        # Quit
        QShortcut(QKeySequence("Ctrl+Q"), self, self.close)

    def _setup_menu(self):
        """Setup menu bar."""
        menubar: QMenuBar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")
        open_data = QAction("Open Data Folder", self)
        open_data.triggered.connect(lambda: os.startfile(str(APP_DIR)) if hasattr(os, 'startfile') else None)
        file_menu.addAction(open_data)
        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self._about)
        help_menu.addAction(about_action)

        shortcuts_action = QAction("Keyboard Shortcuts", self)
        shortcuts_action.triggered.connect(self._show_help)
        help_menu.addAction(shortcuts_action)

    def _new_card(self):
        """Ctrl+N - Start a new card."""
        self.tabs.setCurrentIndex(0)  # Switch to Scan tab
        if hasattr(self.scan_tab, '_reset'):
            self.scan_tab._reset()
        self.statusBar().showMessage("🆕 New card ready", 2500)

    def _focus_search(self):
        """Focus search in Collection tab."""
        if self.tabs.currentIndex() == 2 and hasattr(self.collection_tab, 'search_edit'):
            self.collection_tab.search_edit.setFocus()
            self.collection_tab.search_edit.selectAll()

    def _save_current_card(self):
        """Save card if on Scan tab."""
        if self.tabs.currentIndex() == 0 and hasattr(self.scan_tab, '_save_card'):
            self.scan_tab._save_card()

    def _refresh_all(self):
        """Refresh Collection and Reports."""
        if hasattr(self.collection_tab, 'refresh'):
            self.collection_tab.refresh()
        if hasattr(self.reports_tab, 'refresh'):
            self.reports_tab.refresh()
        self.statusBar().showMessage("✅ Refreshed", 1500)

    def _show_help(self):
        """Show keyboard shortcuts help."""
        help_text = """
        <h2>Keyboard Shortcuts</h2>
        <table border="1" cellpadding="6" style="border-collapse: collapse; width:100%;">
            <tr><td><b>Ctrl + 1</b></td><td>Scan & Add tab</td></tr>
            <tr><td><b>Ctrl + 2</b></td><td>Batch Import tab</td></tr>
            <tr><td><b>Ctrl + 3</b></td><td>Collection tab</td></tr>
            <tr><td><b>Ctrl + 4</b></td><td>Reports tab</td></tr>
            <tr><td><b>Ctrl + N</b></td><td>New Card (Scan tab)</td></tr>
            <tr><td><b>Ctrl + Shift + N</b></td><td>Start Continuous Scan</td></tr>
            <tr><td><b>Ctrl + F</b></td><td>Focus Search (Collection)</td></tr>
            <tr><td><b>Ctrl + S</b></td><td>Save Current Card</td></tr>
            <tr><td><b>F5</b></td><td>Refresh All</td></tr>
            <tr><td><b>F1</b></td><td>Show this help</td></tr>
            <tr><td><b>Ctrl + Q</b></td><td>Quit</td></tr>
        </table>
        """
        QMessageBox.information(self, "Keyboard Shortcuts", help_text)

    def _about(self):
        QMessageBox.about(self, "About Trading Card Manager",
            f"<h2>Trading Card Manager v1.1.0</h2>"
            "<p>Privacy-first Windows desktop app for managing your trading card collection.</p>"
            "<p>Features: TWAIN scanning, AI grading, live valuations, PDF reports.</p>"
            f"<p><b>Data folder:</b> {APP_DIR}</p>")