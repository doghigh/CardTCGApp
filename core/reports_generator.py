"""
Report Generator - Full implementation with clean PDF creation.
Fixed: Better error handling, proper path handling, and safe operations.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import os

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


# Global APP_DIR for consistency
from core.paths import APP_DIR


class ReportGenerator:
    """Generates professional monthly PDF reports."""

    def __init__(self, db: Database):
        self.db = db

    def generate_monthly(self, year: int, month: int) -> Optional[Path]:
        """Generate a monthly collection report PDF."""
        if not HAS_REPORTLAB:
            return None

        # Calculate date range
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
        reports_dir = APP_DIR / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        out_path = reports_dir / f"collection_report_{year}_{month:02d}.pdf"

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

        # Title
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
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3 * inch))

        # This month's activity
        period_value = sum((c.get('estimated_value') or 0) * (c.get('quantity') or 1) for c in period_cards)
        story.append(Paragraph("This Month's Activity", h2_style))
        story.append(Paragraph(
            f"Cards added: <b>{len(period_cards)}</b><br/>"
            f"Value added: <b>${period_value:,.2f}</b>",
            styles['Normal']
        ))
        story.append(Spacer(1, 0.2 * inch))

        # Top cards this month
        if period_cards:
            data = [['Name', 'Set', 'Grade', 'Qty', 'Value']]
            for c in period_cards[:30]:
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
                ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
            ]))
            story.append(t)

        story.append(PageBreak())

        # Top 25 overall
        story.append(Paragraph("Top 25 Cards by Value", h2_style))
        sorted_cards = sorted(
            all_cards,
            key=lambda c: (c.get('estimated_value') or 0) * (c.get('quantity') or 1),
            reverse=True
        )[:25]

        if sorted_cards:
            data = [['#', 'Name', 'Set', 'Grade', 'Qty', 'Unit', 'Total']]
            for i, c in enumerate(sorted_cards, 1):
                qty = c.get('quantity', 1) or 1
                val = c.get('estimated_value', 0) or 0
                data.append([
                    str(i),
                    (c.get('name') or '')[:25],
                    (c.get('set_name') or '')[:18],
                    c.get('condition_grade') or '-',
                    str(qty),
                    f"${val:.2f}",
                    f"${val * qty:.2f}",
                ])
            t = Table(data, colWidths=[0.4*inch, 2*inch, 1.4*inch, 0.9*inch, 0.5*inch, 0.8*inch, 0.9*inch])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
                ('ALIGN', (5, 0), (-1, -1), 'RIGHT'),
            ]))
            story.append(t)

        # Condition Distribution
        story.append(Spacer(1, 0.3 * inch))
        story.append(Paragraph("Condition Distribution", h2_style))
        grade_counts = {}
        for c in all_cards:
            g = c.get('condition_grade') or 'Ungraded'
            grade_counts[g] = grade_counts.get(g, 0) + (c.get('quantity') or 1)

        if grade_counts:
            data = [['Grade', 'Count']]
            for g, count in sorted(grade_counts.items(), key=lambda x: -x[1]):
                data.append([g, str(count)])
            t = Table(data, colWidths=[3*inch, 1.5*inch])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
            ]))
            story.append(t)

        # Build PDF
        doc.build(story)

        # Save to database
        self.db.save_report(
            start.strftime('%Y-%m-%d'),
            end.strftime('%Y-%m-%d'),
            len(period_cards),
            period_value,
            str(out_path)
        )

        return out_path