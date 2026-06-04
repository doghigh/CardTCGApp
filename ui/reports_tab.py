from datetime import datetime
from pathlib import Path
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QComboBox,
    QPushButton, QListWidget, QListWidgetItem, QMessageBox, QGroupBox, QFrame
)
from PyQt6.QtCore import Qt

from core.reports_generator import ReportGenerator


class ReportsTab(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.report_gen = ReportGenerator(db)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header
        title = QLabel("📊 Reports")
        title.setStyleSheet("font-size: 20px; font-weight: 600; color: #e8eaf0;")
        layout.addWidget(title)

        # Stats bar
        self.stats_bar = QLabel("Loading collection stats...")
        self.stats_bar.setStyleSheet(
            "background-color: #1c1f2e; border: 1px solid #2a2d3e; border-radius: 8px;"
            "padding: 12px 16px; font-size: 13px; color: #e8eaf0;"
        )
        self.stats_bar.setWordWrap(True)
        layout.addWidget(self.stats_bar)

        # Generate group
        gen_group = QGroupBox("Generate Report")
        gg = QVBoxLayout(gen_group)
        gg.setContentsMargins(12, 24, 12, 12)
        gg.setSpacing(10)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        controls.addWidget(QLabel("Year:"))
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2000, 2100)
        self.year_spin.setValue(datetime.now().year)
        self.year_spin.setFixedWidth(80)
        controls.addWidget(self.year_spin)

        controls.addWidget(QLabel("Month:"))
        self.month_combo = QComboBox()
        months = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']
        for i, month in enumerate(months, 1):
            self.month_combo.addItem(month, i)
        self.month_combo.setCurrentIndex(datetime.now().month - 1)
        self.month_combo.setFixedWidth(130)
        controls.addWidget(self.month_combo)

        self.gen_btn = QPushButton("📄 Generate PDF Report")
        self.gen_btn.setMinimumHeight(38)
        self.gen_btn.setProperty("primary", True)
        self.gen_btn.clicked.connect(self._generate_report)
        controls.addWidget(self.gen_btn)
        controls.addStretch()
        gg.addLayout(controls)
        layout.addWidget(gen_group)

        # Past reports group
        history_group = QGroupBox("Past Reports")
        hg = QVBoxLayout(history_group)
        hg.setContentsMargins(10, 24, 10, 10)

        self.report_list = QListWidget()
        self.report_list.setMinimumHeight(200)
        self.report_list.itemDoubleClicked.connect(self._open_report)
        self.report_list.setStyleSheet(
            "QListWidget { border: none; background-color: transparent; }"
            "QListWidget::item { padding: 10px 12px; border-radius: 6px; }"
            "QListWidget::item:hover { background-color: #252840; }"
            "QListWidget::item:selected { background-color: #252840; color: #e8eaf0; }"
        )

        hint = QLabel("Double-click a report to open it")
        hint.setStyleSheet("color: #4a4d60; font-size: 11px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignRight)

        hg.addWidget(self.report_list)
        hg.addWidget(hint)
        layout.addWidget(history_group, 1)

    def refresh(self):
        self.report_list.clear()
        reports = self.db.get_reports()
        for r in reports:
            text = (f"  {r['period_start']}  →  {r['period_end']}"
                    f"    •    {r['total_cards']} cards"
                    f"    •    ${r['total_value']:,.2f}")
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, r['file_path'])
            self.report_list.addItem(item)

        # Update stats bar
        self._refresh_stats()

    def _refresh_stats(self):
        try:
            cards = self.db.get_all_cards()
            if not cards:
                self.stats_bar.setText("No cards in collection yet.")
                return
            total = sum(c.get('quantity', 1) for c in cards)
            unique = len(cards)
            value = sum((c.get('estimated_value') or 0) * (c.get('quantity') or 1) for c in cards)
            cost = sum((c.get('purchase_price') or 0) * (c.get('quantity') or 1) for c in cards)
            net = value - cost
            sign = "+" if net >= 0 else ""
            self.stats_bar.setText(
                f"🃏  {unique} unique  •  {total} total cards  "
                f"   |   💰  Est. value  ${value:,.2f}  "
                f"   |   🧾  Cost  ${cost:,.2f}  "
                f"   |   📈  Net  {sign}${net:,.2f}"
            )
        except Exception:
            self.stats_bar.setText("Collection stats unavailable.")

    def _generate_report(self):
        year = self.year_spin.value()
        month = self.month_combo.currentData()
        try:
            path = self.report_gen.generate_monthly(year, month)
            if path:
                QMessageBox.information(self, "Success", f"Report generated:\n{path}")
                self.refresh()
                if hasattr(os, 'startfile'):
                    os.startfile(str(path))
            else:
                QMessageBox.warning(self, "Failed", "Report generation failed.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate report:\n{str(e)}")

    def _open_report(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and Path(path).exists():
            if hasattr(os, 'startfile'):
                os.startfile(path)
        else:
            QMessageBox.warning(self, "Not Found", f"Report file not found:\n{path}")
