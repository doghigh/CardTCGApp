"""
Help Center dialog — searchable topic list on the left, Markdown content on
the right (rendered natively via QTextBrowser.setMarkdown, no dependencies).
"""

from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QTextBrowser, QLabel, QPushButton,
)
from PyQt6.QtCore import Qt

from ui.help_content import HELP_TOPICS


class HelpDialog(QDialog):
    """Offline help / wiki for the app."""

    def __init__(self, parent=None, topic: str = None):
        super().__init__(parent)
        self.setWindowTitle("Help Center — Trading Card Manager")
        self.resize(880, 620)
        self._build_ui()
        # Open a specific topic if requested, else the first
        if topic and topic in HELP_TOPICS:
            self._select_topic(topic)
        elif self.topic_list.count():
            self.topic_list.setCurrentRow(0)

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(14, 14, 14, 14)

        # Left: search + topic list
        left = QVBoxLayout()
        left.setSpacing(8)
        title = QLabel("❓ Help Center")
        title.setStyleSheet("font-size:16px;font-weight:600;")
        left.addWidget(title)

        self.search = QLineEdit()
        self.search.setPlaceholderText("🔎 Search help…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        self.search.setAccessibleName("Search help topics")
        left.addWidget(self.search)

        self.topic_list = QListWidget()
        self.topic_list.setMinimumWidth(230)
        self.topic_list.setAccessibleName("Help topics")
        for name in HELP_TOPICS:
            self.topic_list.addItem(QListWidgetItem(name))
        self.topic_list.currentItemChanged.connect(self._on_topic)
        left.addWidget(self.topic_list, 1)
        root.addLayout(left)

        # Right: content
        right = QVBoxLayout()
        right.setSpacing(8)
        self.viewer = QTextBrowser()
        self.viewer.setOpenExternalLinks(True)
        self.viewer.setAccessibleName("Help content")
        right.addWidget(self.viewer, 1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        right.addLayout(close_row)
        root.addLayout(right, 1)

    def _on_topic(self, current, _previous):
        if current is None:
            return
        md = HELP_TOPICS.get(current.text(), "")
        self.viewer.setMarkdown(md)

    def _select_topic(self, topic: str):
        items = self.topic_list.findItems(topic, Qt.MatchFlag.MatchExactly)
        if items:
            self.topic_list.setCurrentItem(items[0])

    def _filter(self, text: str):
        """Show topics whose title or body contains the query."""
        q = text.strip().lower()
        first_visible = None
        for i in range(self.topic_list.count()):
            item = self.topic_list.item(i)
            name = item.text()
            hit = (not q) or q in name.lower() or q in HELP_TOPICS.get(name, "").lower()
            item.setHidden(not hit)
            if hit and first_visible is None:
                first_visible = item
        # Keep a sensible selection visible
        if self.topic_list.currentItem() is None or self.topic_list.currentItem().isHidden():
            if first_visible:
                self.topic_list.setCurrentItem(first_visible)
