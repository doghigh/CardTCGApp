"""
Dashboard Tab — at-a-glance overview of the collection.

KPIs (cards, value, cost, net P&L, avg condition), breakdowns by game and
grade (relative bars), most valuable cards, and recent additions. Uses only
built-in widgets styled to the app theme — no extra dependencies.
"""

from typing import List, Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QGroupBox, QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
    QScrollArea, QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from core.database import Database

ACCENT = "#5865f2"
GREEN  = "#43b581"
RED    = "#ed4245"
AMBER  = "#faa61a"
MUTED  = "#8b8fa8"

GRADE_COLORS = {
    "Gem Mint": GREEN, "Mint": GREEN, "Near Mint": GREEN,
    "Excellent": AMBER, "Very Good": AMBER,
    "Good": RED, "Played": RED, "Poor": RED, "Ungraded": MUTED,
}


class _KpiCard(QFrame):
    """A single big-number stat card."""
    def __init__(self, caption: str):
        super().__init__()
        self.setObjectName("kpiCard")
        self.setStyleSheet(
            "#kpiCard{background:#1a1d2e;border:1px solid #2a2d3e;"
            "border-radius:10px;}"
        )
        self.setMinimumHeight(88)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(2)
        self.value_lbl = QLabel("—")
        self.value_lbl.setStyleSheet("font-size:24px;font-weight:700;color:#e8eaf0;")
        cap = QLabel(caption)
        cap.setStyleSheet(f"font-size:12px;color:{MUTED};")
        lay.addWidget(self.value_lbl)
        lay.addWidget(cap)

    def set_value(self, text: str, color: str = "#e8eaf0"):
        self.value_lbl.setText(text)
        self.value_lbl.setStyleSheet(
            f"font-size:24px;font-weight:700;color:{color};")


class DashboardTab(QWidget):
    """Collection overview / home screen."""

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self._build_ui()
        self.refresh()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        header = QLabel("📊 Dashboard")
        header.setStyleSheet("font-size:22px;font-weight:600;color:#e8eaf0;")
        layout.addWidget(header)

        # KPI row
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)
        self.kpi_cards   = _KpiCard("Unique cards")
        self.kpi_qty     = _KpiCard("Total quantity")
        self.kpi_value   = _KpiCard("Estimated value")
        self.kpi_cost    = _KpiCard("Total cost")
        self.kpi_pnl     = _KpiCard("Net P&L")
        self.kpi_cond    = _KpiCard("Avg condition")
        for c in (self.kpi_cards, self.kpi_qty, self.kpi_value,
                  self.kpi_cost, self.kpi_pnl, self.kpi_cond):
            kpi_row.addWidget(c)
        layout.addLayout(kpi_row)

        # Breakdown row: by game | by grade
        mid = QHBoxLayout()
        mid.setSpacing(12)

        self.game_box = QGroupBox("Value by Game")
        self.game_layout = QVBoxLayout(self.game_box)
        self.game_layout.setContentsMargins(14, 22, 14, 14)
        self.game_layout.setSpacing(8)
        mid.addWidget(self.game_box, 1)

        self.grade_box = QGroupBox("Cards by Grade")
        self.grade_layout = QVBoxLayout(self.grade_box)
        self.grade_layout.setContentsMargins(14, 22, 14, 14)
        self.grade_layout.setSpacing(8)
        mid.addWidget(self.grade_box, 1)
        layout.addLayout(mid)

        # Tables row: top value | recent
        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        top_box = QGroupBox("Most Valuable Cards")
        tl = QVBoxLayout(top_box)
        tl.setContentsMargins(10, 22, 10, 10)
        self.top_table = self._make_table(["Card", "Set", "Grade", "Value"])
        tl.addWidget(self.top_table)
        bottom.addWidget(top_box, 1)

        recent_box = QGroupBox("Recently Added")
        rl = QVBoxLayout(recent_box)
        rl.setContentsMargins(10, 22, 10, 10)
        self.recent_table = self._make_table(["Card", "Set", "Game", "Added"])
        rl.addWidget(self.recent_table)
        bottom.addWidget(recent_box, 1)
        layout.addLayout(bottom)

        layout.addStretch()

    def _make_table(self, headers: List[str]) -> QTableWidget:
        t = QTableWidget()
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        t.setAlternatingRowColors(True)
        t.setMinimumHeight(240)
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, len(headers)):
            t.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        return t

    def _bar_row(self, label: str, value_text: str, fraction: float,
                 color: str) -> QWidget:
        """A labelled relative bar (label · bar · value)."""
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)

        name = QLabel(label)
        name.setMinimumWidth(150)
        name.setStyleSheet("color:#e8eaf0;font-size:13px;")
        h.addWidget(name)

        bar = QProgressBar()
        bar.setTextVisible(False)
        bar.setRange(0, 1000)
        bar.setValue(int(max(0.0, min(1.0, fraction)) * 1000))
        bar.setFixedHeight(14)
        bar.setStyleSheet(
            "QProgressBar{background:#13151f;border:none;border-radius:7px;}"
            f"QProgressBar::chunk{{background:{color};border-radius:7px;}}"
        )
        h.addWidget(bar, 1)

        val = QLabel(value_text)
        val.setMinimumWidth(90)
        val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        val.setStyleSheet(f"color:{MUTED};font-size:13px;")
        h.addWidget(val)
        return row

    @staticmethod
    def _clear(layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    # ── data ───────────────────────────────────────────────────────────────────

    def refresh(self):
        stats = self.db.get_collection_stats()
        value = float(stats.get('total_value', 0) or 0)
        cost  = float(stats.get('total_cost', 0) or 0)
        pnl   = value - cost
        cond  = float(stats.get('avg_condition', 0) or 0)

        self.kpi_cards.set_value(f"{stats.get('total_cards', 0):,}")
        self.kpi_qty.set_value(f"{stats.get('total_quantity', 0):,}")
        self.kpi_value.set_value(f"${value:,.2f}", GREEN if value else "#e8eaf0")
        self.kpi_cost.set_value(f"${cost:,.2f}")
        self.kpi_pnl.set_value(f"${pnl:+,.2f}", GREEN if pnl >= 0 else RED)
        self.kpi_cond.set_value(f"{cond:.0f}/100" if cond else "—")

        self._refresh_games()
        self._refresh_grades()
        self._fill_top_table()
        self._fill_recent_table()

    def _refresh_games(self):
        self._clear(self.game_layout)
        games = self.db.get_game_breakdown()
        if not games:
            self.game_layout.addWidget(self._empty("No cards yet."))
            return
        max_val = max((g['value'] for g in games), default=0) or 1
        for g in games[:8]:
            frac = g['value'] / max_val if max_val else 0
            self.game_layout.addWidget(self._bar_row(
                g['game'], f"${g['value']:,.0f}", frac, ACCENT))

    def _refresh_grades(self):
        self._clear(self.grade_layout)
        grades = self.db.get_grade_breakdown()
        if not grades:
            self.grade_layout.addWidget(self._empty("No cards yet."))
            return
        # order by our grade scale, then by count
        order = ["Gem Mint", "Mint", "Near Mint", "Excellent", "Very Good",
                 "Good", "Played", "Poor", "Ungraded"]
        grades.sort(key=lambda x: order.index(x['grade'])
                    if x['grade'] in order else 99)
        max_cnt = max((g['quantity'] for g in grades), default=0) or 1
        for g in grades:
            frac = g['quantity'] / max_cnt if max_cnt else 0
            color = GRADE_COLORS.get(g['grade'], MUTED)
            self.grade_layout.addWidget(self._bar_row(
                g['grade'], f"{g['quantity']:,}", frac, color))

    def _fill_top_table(self):
        cards = self.db.get_top_cards(10)
        self.top_table.setRowCount(len(cards))
        for i, c in enumerate(cards):
            total = float(c.get('estimated_value', 0) or 0) * int(c.get('quantity', 1) or 1)
            self.top_table.setItem(i, 0, QTableWidgetItem(c.get('name', '') or ''))
            self.top_table.setItem(i, 1, QTableWidgetItem(c.get('set_name', '') or ''))
            self.top_table.setItem(i, 2, QTableWidgetItem(c.get('condition_grade', '') or '—'))
            val_item = QTableWidgetItem(f"${total:,.2f}")
            val_item.setForeground(QColor(GREEN if total > 0 else MUTED))
            self.top_table.setItem(i, 3, val_item)

    def _fill_recent_table(self):
        cards = self.db.get_recent_cards(10)
        self.recent_table.setRowCount(len(cards))
        for i, c in enumerate(cards):
            self.recent_table.setItem(i, 0, QTableWidgetItem(c.get('name', '') or ''))
            self.recent_table.setItem(i, 1, QTableWidgetItem(c.get('set_name', '') or ''))
            self.recent_table.setItem(i, 2, QTableWidgetItem(c.get('game', '') or ''))
            self.recent_table.setItem(i, 3, QTableWidgetItem(str(c.get('created_at', '') or '')[:10]))

    @staticmethod
    def _empty(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{MUTED};font-size:13px;")
        return lbl
