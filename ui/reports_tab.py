from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QComboBox,
    QPushButton, QListWidget, QListWidgetItem, QMessageBox
)
from PyQt6.QtCore import Qt

from core.database import Database
from core.report_generator import ReportGenerator   # We'll need this next if not created yet


class ReportsTab(QWidget):
    """Monthly PDF reports tab."""

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.report_gen = ReportGenerator(db)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Report generation controls
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Year:"))

        self.year_spin = QSpinBox()
        self.year_spin.setRange(2000, 2100)
        self.year_spin.setValue(datetime.now().year)
        controls.addWidget(self.year_spin)

        controls.addWidget(QLabel("Month:"))
        self.month_combo = QComboBox()
        months = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']
        for i, month in enumerate(months, 1):
            self.month_combo.addItem(month, i)
        self.month_combo.setCurrentIndex(datetime.now().month - 1)
        controls.addWidget(self.month_combo)

        self.gen_btn = QPushButton("📄 Generate Monthly PDF Report")
        self.gen_btn.setMinimumHeight(40)
        self.gen_btn.clicked.connect(self._generate_report)
        controls.addWidget(self.gen_btn)
        controls.addStretch()
        layout.addLayout(controls)

        # Past reports list
        layout.addWidget(QLabel("📚 Past Reports (double-click to open):"))
        self.report_list = QListWidget()
        self.report_list.itemDoubleClicked.connect(self._open_report)
        layout.addWidget(self.report_list)

    def refresh(self):
        """Refresh the list of saved reports."""
        self.report_list.clear()
        reports = self.db.get_reports()
        for r in reports:
            text = (f"{r['period_start']} → {r['period_end']}  •  "
                    f"{r['total_cards']} cards  •  "
                    f"${r['total_value']:,.2f}  •  {Path(r['file_path']).name}")
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, r['file_path'])
            self.report_list.addItem(item)

    def _generate_report(self):
        """Generate a new monthly report."""
        year = self.year_spin.value()
        month = self.month_combo.currentData()

        try:
            path = self.report_gen.generate_monthly(year, month)
            if path:
                QMessageBox.information(self, "Report Generated",
                    f"Monthly report saved to:\n{path}")
                self.refresh()

                # Auto-open the PDF
                if hasattr(os, 'startfile'):
                    os.startfile(str(path))
            else:
                QMessageBox.warning(self, "Generation Failed", "Report generation returned no file.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate report:\n{str(e)}")

    def _open_report(self, item: QListWidgetItem):
        """Open a saved report PDF."""
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and Path(path).exists():
            if hasattr(os, 'startfile'):
                os.startfile(path)
            else:
                QMessageBox.information(self, "Path", f"Report location:\n{path}")
        else:
            QMessageBox.warning(self, "Not Found", f"Report file not found:\n{path}")
