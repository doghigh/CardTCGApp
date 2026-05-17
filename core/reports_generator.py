from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from core.database import Database

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    )
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


class ReportGenerator:
    """Generates professional monthly PDF collection reports."""

    def __init__(self, db: Database):
        self.db = db

    def generate_monthly(self, year: int, month: int) -> Optional[Path]:
        """Generate a PDF report for a specific month."""
        if not HAS_REPORTLAB:
            return None

        # Calculate period
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

        # Output path
        out_path = Path.home() / "TradingCardManager" / "reports" / f"collection_report_{year}_{month:02d}.pdf"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(out_path),
            pagesize=letter,
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'TitleCenter',
            parent=styles['Title'],
            alignment=1,
            textColor=colors.HexColor('#1a365d')
        )
        h2_style = ParagraphStyle(
            'H2',
            parent=styles['Heading2'],
            textColor=colors.HexColor('#2c5282')
        )

        story = []

        # Header
        story.append(Paragraph("Trading Card Collection Report", title_style))
        story.append(Paragraph(start.strftime('%B %Y'), styles['Heading2']))
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
        story.append(Spacer(1, 0.3 * inch))

        # Summary
        story.append(Paragraph("Collection Summary", h2_style))
        summary_data = [
            ['Metric', 'Value'],
            ['Total Unique Cards', f"{stats.get('total_cards', 0):,}"],
            ['Total Quantity', f"{stats.get('total_quantity', 0):,}"],
            ['Total Estimated Value', f"${stats.get('total_value', 0):,.2f}"],
            ['Total Cost Basis', f"${stats.get('total_cost', 0):,.2f}"],
            ['Net Position', f"${stats.get('total_value', 0) - stats.get('total_cost', 0):,.2f}"],
            ['Average Condition Score', f"{stats.get('avg_condition', 0):.1f}/100"],
        ]

        t = Table(summary_data, colWidths=[3*inch, 2.5*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f7fafc'), colors.white]),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3 * inch))

        # This month's activity
        period_value = sum((c.get('estimated_value') or 0) * (c.get('quantity') or 1) for c in period_cards)
        story.append(Paragraph("This Month's Activity", h2_style))
        story.append(Paragraph(
            f"Cards added this month: <b>{len(period_cards)}</b><br/>"
            f"Value added this month: <b>${period_value:,.2f}</b>",
            styles['Normal']
        ))
        story.append(Spacer(1, 0.2 * inch))

        # Top cards this month
        if period_cards:
            data = [['Name', 'Set', 'Grade', 'Qty', 'Value']]
            for c in period_cards[:25]:
                data.append([
                    (c.get('name') or '')[:30],
                    (c.get('set_name') or '')[:20],
                    c.get('condition_grade') or '-',
                    str(c.get('quantity', 1)),
                    f"${(c.get('estimated_value') or 0):.2f}",
                ])
            t = Table(data, colWidths=[2.2*inch, 1.6*inch, 1.0*inch, 0.5*inch, 0.9*inch])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f7fafc'), colors.white]),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
            ]))
            story.append(Paragraph("Cards Added This Month", h2_style))
            story.append(t)
            story.append(Spacer(1, 0.3 * inch))

        # Full collection table
        story.append(PageBreak())
        story.append(Paragraph("Full Collection", h2_style))

        if all_cards:
            col_data = [['Name', 'Set', 'Grade', 'Score', 'Qty', 'Value', 'Added']]
            for c in all_cards[:200]:
                qty = c.get('quantity', 1) or 1
                val = c.get('estimated_value', 0) or 0
                col_data.append([
                    (c.get('name') or '')[:28],
                    (c.get('set_name') or '')[:18],
                    c.get('condition_grade') or '-',
                    f"{c.get('condition_score', 0):.0f}",
                    str(qty),
                    f"${val:.2f}",
                    str(c.get('created_at', ''))[:10],
                ])
            ct = Table(col_data, colWidths=[
                2.0*inch, 1.5*inch, 0.9*inch, 0.5*inch, 0.4*inch, 0.7*inch, 0.9*inch
            ])
            ct.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f7fafc'), colors.white]),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
            ]))
            story.append(ct)

        doc.build(story)

        # Record in DB
        total_value = stats.get('total_value', 0)
        total_cards = stats.get('total_cards', 0)
        self.db.save_report(
            start.strftime('%Y-%m-%d'),
            end.strftime('%Y-%m-%d'),
            total_cards,
            total_value,
            str(out_path),
        )

        return out_path
