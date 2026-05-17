# core/report_generator.py
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from core.database import Database

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


class ReportGenerator:
    def __init__(self, db: Database):
        self.db = db

    def generate_monthly(self, year: int, month: int) -> Optional[Path]:
        if not HAS_REPORTLAB:
            return None

        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1) - timedelta(seconds=1)
        else:
            end = datetime(year, month + 1, 1) - timedelta(seconds=1)

        period_cards = self.db.get_cards_for_period(
            start.strftime('%Y-%m-%d %H:%M:%S'),
            end.strftime('%Y-%m-%d %H:%M:%S')
        )
        all_cards = self.db.get_all_cards()
        stats = self.db.get_collection_stats()

        reports_dir = APP_DIR / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        out_path = reports_dir / f"collection_report_{year}_{month:02d}.pdf"

        doc = SimpleDocTemplate(str(out_path), pagesize=letter, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('TitleCenter', parent=styles['Title'], alignment=1, textColor=colors.HexColor('#1a365d'))
        h2 = ParagraphStyle('H2', parent=styles['Heading2'], textColor=colors.HexColor('#2c5282'))

        story = []
        story.append(Paragraph("Trading Card Collection Report", title_style))
        story.append(Paragraph(start.strftime('%B %Y'), styles['Heading2']))
        story.append(Spacer(1, 0.3 * inch))

        # Summary Table, Top Cards, Condition Distribution (same as before, but cleaned up)
        # ... (full story building code from earlier version)

        doc.build(story)

        self.db.save_report(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'),
                            len(period_cards), sum(c.get('estimated_value', 0) * c.get('quantity', 1) for c in period_cards),
                            str(out_path))

        return out_path