"""
Main Window for Lorebox
Fixed: Keyboard shortcuts, menu, login integration, and clean structure.
"""

import sys
import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QMenuBar, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut, QAction

from core.database import Database
from core.scanner import ScannerInterface
from core.inspector import CardInspector
from core.identifier import CardIdentifier
from core.valuator import CardValuator
from core.auth import AuthManager, WindowsHelloAuth, LoginDialog, AuthLockedError
from core.watcher import WatchConfig

from ui.dashboard_tab import DashboardTab
from ui.scan_tab import ScanTab
from ui.batch_tab import BatchTab, ImageBatchWorker
from ui.collection_tab import CollectionTab
from ui.reports_tab import ReportsTab


APP_DIR = Path(os.environ.get('APPDATA', Path.home())) / "Lorebox"


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()

        # Authentication
        self.auth = AuthManager()
        self.hello_auth = WindowsHelloAuth()

        # Login check
        if self.auth.has_password() or (hasattr(self.auth, 'totp_secret_file') and self.auth.totp_secret_file.exists()):
            dlg = LoginDialog(self.auth, self.hello_auth, self)
            if dlg.exec() != 1:  # Accepted
                sys.exit(0)

        # Window setup
        self.setWindowTitle("Lorebox v1.1.0")
        self.resize(1580, 960)

        # Core components
        self.db = Database(APP_DIR / "cards.db")
        self.scanner = ScannerInterface()
        self.inspector = CardInspector()
        self.identifier = CardIdentifier()
        self.valuator = CardValuator()

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(False)
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)

        # Watch-folder auto-import config (shared with the batch tab UI)
        self.watch_config = WatchConfig()
        self._watch_worker = None
        self._watch_snapshot = []

        self.dashboard_tab = DashboardTab(self.db)
        self.scan_tab = ScanTab(self.db, self.scanner, self.inspector, self.identifier, self.valuator)
        self.batch_tab = BatchTab(self.db, self.scanner, self.inspector, self.identifier,
                                  self.valuator, self.watch_config, self._run_watch_import)
        self.collection_tab = CollectionTab(self.db, self.valuator, self.identifier)
        self.reports_tab = ReportsTab(self.db)

        # Dashboard navigation
        self.dashboard_tab.navigate_collection.connect(self._dashboard_to_collection)
        self.dashboard_tab.open_card.connect(self._dashboard_open_card)

        # Connect signals — refresh dashboard, collection, and reports on changes
        self.scan_tab.card_added.connect(self.collection_tab.refresh)
        self.scan_tab.card_added.connect(self.reports_tab.refresh)
        self.scan_tab.card_added.connect(self.dashboard_tab.refresh)
        self.batch_tab.cards_added.connect(self.collection_tab.refresh)
        self.batch_tab.cards_added.connect(self.reports_tab.refresh)
        self.batch_tab.cards_added.connect(self.dashboard_tab.refresh)

        # Add tabs
        self.tabs.addTab(self.dashboard_tab, "📊 Dashboard")
        self.tabs.addTab(self.scan_tab, "🃏 Scan & Add")
        self.tabs.addTab(self.batch_tab, "📦 Batch Import")
        self.tabs.addTab(self.collection_tab, "📋 Collection")
        self.tabs.addTab(self.reports_tab, "📈 Reports")

        self.setCentralWidget(self.tabs)

        # Keep the dashboard current whenever the user switches to it
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Setup shortcuts and menu
        self._setup_shortcuts()
        self._setup_menu()

        # Status bar
        sb = QStatusBar()
        self.setStatusBar(sb)
        sb.showMessage("Ready • Press F1 for keyboard shortcuts")

        # Watch-folder timer — checks once a minute whether an auto-import is due
        self._watch_timer = QTimer(self)
        self._watch_timer.timeout.connect(self._check_watch)
        self._watch_timer.start(60_000)

        # First-run: if no Anthropic key is configured, guide the user to Settings
        self._prompt_for_keys_if_needed()

    def _prompt_for_keys_if_needed(self):
        """On first run (no API key), offer to open Settings."""
        from core.config import config
        if config.has_anthropic_key():
            return
        reply = QMessageBox.question(
            self, "Welcome to Lorebox",
            "To identify cards you'll need a free Anthropic API key "
            "(card scanning costs about $0.006 per card).\n\n"
            "Would you like to enter your API keys now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._open_settings()

    def _setup_shortcuts(self):
        """Setup global keyboard shortcuts."""
        # Tab switching
        for i in range(self.tabs.count()):
            QShortcut(QKeySequence(f"Ctrl+{i+1}"), self,
                      lambda idx=i: self.tabs.setCurrentIndex(idx))

        # New card
        QShortcut(QKeySequence("Ctrl+N"), self, self._new_card)

        # Continuous scan
        QShortcut(QKeySequence("Ctrl+Shift+N"), self, 
                  lambda: self.scan_tab._start_continuous_scan() if hasattr(self.scan_tab, '_start_continuous_scan') else None)

        # Search
        QShortcut(QKeySequence("Ctrl+F"), self, self._focus_search)

        # Save
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_current_card)

        # Refresh
        QShortcut(QKeySequence("F5"), self, self._refresh_all)

        # Help
        QShortcut(QKeySequence("F1"), self, self._open_help_center)

        # Quit
        QShortcut(QKeySequence("Ctrl+Q"), self, self.close)

    def _setup_menu(self):
        """Setup menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")
        settings_action = QAction("⚙ Settings (API Keys)…", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._open_settings)
        file_menu.addAction(settings_action)
        file_menu.addSeparator()

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
        help_center_action = QAction("Help Center\tF1", self)
        help_center_action.triggered.connect(self._open_help_center)
        help_menu.addAction(help_center_action)

        shortcuts_action = QAction("Keyboard Shortcuts", self)
        shortcuts_action.triggered.connect(self._show_help)
        help_menu.addAction(shortcuts_action)

        help_menu.addSeparator()
        about_action = QAction("About", self)
        about_action.triggered.connect(self._about)
        help_menu.addAction(about_action)

        privacy_action = QAction("Privacy Policy", self)
        privacy_action.triggered.connect(self._open_privacy)
        help_menu.addAction(privacy_action)

    def closeEvent(self, event):
        """Closing the main window exits the app (quitOnLastWindowClosed is off,
        so child dialogs closing never quit it — only this does)."""
        from PyQt6.QtWidgets import QApplication
        event.accept()
        QApplication.instance().quit()

    def _open_help_center(self, topic: str = None):
        from ui.help_dialog import HelpDialog
        HelpDialog(self, topic if isinstance(topic, str) else None).exec()

    def _open_privacy(self):
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl("https://cardtcgapp.onrender.com/privacy"))

    # ── Watch-folder auto-import ──────────────────────────────────────────────

    def _check_watch(self):
        """Called every minute — run an auto-import if one is due."""
        if self._watch_worker and self._watch_worker.isRunning():
            return
        if self.watch_config.is_due():
            self._run_watch_import()

    def _run_watch_import(self, force: bool = False):
        """Start an auto-import of the watch folder's pending images."""
        if self._watch_worker and self._watch_worker.isRunning():
            return
        cfg = self.watch_config
        if not cfg.folder:
            return
        images = cfg.pending_images()
        if not images:
            if force:
                self.statusBar().showMessage("🕒 Watch folder is empty.", 4000)
            # For interval mode, advance the clock so we don't busy-check
            if cfg.mode == "interval":
                cfg.mark_run()
            return

        self._watch_snapshot = images
        self.statusBar().showMessage(
            f"🕒 Auto-import: processing {len(images)} file(s)…")
        self._watch_worker = ImageBatchWorker(
            Path(cfg.folder), self.db, self.scanner, self.inspector,
            self.identifier, self.valuator, cfg.auto_value, cfg.pairing)
        self._watch_worker.finished.connect(self._on_watch_done)
        self._watch_worker.start()

    def _on_watch_done(self, count: int):
        cfg = self.watch_config
        # Move processed files into an "imported" subfolder so they aren't redone
        from core.watcher import IMPORTED_SUBDIR
        dest = Path(cfg.folder) / IMPORTED_SUBDIR
        try:
            dest.mkdir(exist_ok=True)
            for p in self._watch_snapshot:
                try:
                    p.rename(dest / p.name)
                except OSError:
                    pass
        except OSError:
            pass

        cfg.mark_run()
        self._watch_snapshot = []
        self.collection_tab.refresh()
        self.reports_tab.refresh()
        if hasattr(self.batch_tab, "refresh_watch_status"):
            self.batch_tab.refresh_watch_status()
        self.statusBar().showMessage(
            f"🕒 Auto-import complete — {count} card(s) added.", 6000)

    def _on_tab_changed(self, index: int):
        """Refresh the dashboard whenever it becomes the active tab."""
        if self.tabs.widget(index) is self.dashboard_tab:
            self.dashboard_tab.refresh()

    def _dashboard_to_collection(self, term: str):
        """Jump to the Collection tab filtered by a dashboard click."""
        self.tabs.setCurrentWidget(self.collection_tab)
        if hasattr(self.collection_tab, 'search_edit'):
            self.collection_tab.search_edit.setText(term)

    def _dashboard_open_card(self, card_id: int):
        """Open a card's detail dialog from the dashboard."""
        card = self.db.get_card(card_id)
        if not card:
            return
        from ui.dialogs import CardDetailDialog
        valuations = self.db.get_valuations(card_id)
        dlg = CardDetailDialog(card, valuations, self.db, self)
        if dlg.exec():
            self.dashboard_tab.refresh()
            self.collection_tab.refresh()

    def _open_settings(self):
        """Open the API-keys settings dialog and apply changes live."""
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        if dlg.exec():
            # New keys are already in os.environ — refresh the live components
            self.identifier.reload_credentials()
            self.valuator.reload_credentials()
            self.statusBar().showMessage("✅ API keys updated", 3000)

    def _new_card(self):
        """Ctrl+N - New card."""
        self.tabs.setCurrentWidget(self.scan_tab)
        if hasattr(self.scan_tab, '_reset'):
            self.scan_tab._reset()
        self.statusBar().showMessage("🆕 New card ready", 2000)

    def _focus_search(self):
        """Focus search in Collection tab."""
        if self.tabs.currentWidget() is self.collection_tab and hasattr(self.collection_tab, 'search_edit'):
            self.collection_tab.search_edit.setFocus()
            self.collection_tab.search_edit.selectAll()

    def _save_current_card(self):
        """Save current card if on Scan tab."""
        if self.tabs.currentWidget() is self.scan_tab and hasattr(self.scan_tab, '_save_card'):
            self.scan_tab._save_card()

    def _refresh_all(self):
        """Refresh all tabs."""
        if hasattr(self.dashboard_tab, 'refresh'):
            self.dashboard_tab.refresh()
        if hasattr(self.collection_tab, 'refresh'):
            self.collection_tab.refresh()
        if hasattr(self.reports_tab, 'refresh'):
            self.reports_tab.refresh()
        self.statusBar().showMessage("✅ Refreshed", 1500)

    def _show_help(self):
        """Show keyboard shortcuts help."""
        help_text = """
        <h2>Keyboard Shortcuts</h2>
        <table border="1" cellpadding="6" style="border-collapse: collapse;">
            <tr><td><b>Ctrl + 1</b></td><td>Scan & Add tab</td></tr>
            <tr><td><b>Ctrl + 2</b></td><td>Batch Import tab</td></tr>
            <tr><td><b>Ctrl + 3</b></td><td>Collection tab</td></tr>
            <tr><td><b>Ctrl + 4</b></td><td>Reports tab</td></tr>
            <tr><td><b>Ctrl + N</b></td><td>New Card</td></tr>
            <tr><td><b>Ctrl + Shift + N</b></td><td>Continuous Scan</td></tr>
            <tr><td><b>Ctrl + F</b></td><td>Focus Search</td></tr>
            <tr><td><b>Ctrl + S</b></td><td>Save Card</td></tr>
            <tr><td><b>F5</b></td><td>Refresh</td></tr>
            <tr><td><b>F1</b></td><td>This Help</td></tr>
            <tr><td><b>Ctrl + Q</b></td><td>Quit</td></tr>
        </table>
        """
        QMessageBox.information(self, "Keyboard Shortcuts", help_text)

    def _about(self):
        QMessageBox.about(self, "About Lorebox",
            f"<h2>Lorebox v1.1.0</h2>"
            "<p>Privacy-first Windows desktop app for trading card collectors.</p>"
            f"<p>Data folder: {APP_DIR}</p>")
