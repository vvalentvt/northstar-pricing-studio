"""The one concrete ProposalRenderer this phase ships: a pure-Python,
deterministic PDF built with ReportLab. No browser process, no
platform-specific executable, no external rendering service -- see
docs/adr/006-proposal-artifacts.md for why.

Every commercial figure drawn here comes from the already-frozen
ProposalSnapshot; this module contains no pricing logic and never
calls back into the pricing engine. Internal pricing-governance facts
(discount-authority thresholds, approval reason, rule version) are
deliberately never drawn -- this is a customer-facing document, not
the Review Pricing governance surface.
"""

from __future__ import annotations

import io
from datetime import datetime
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import ProposalSnapshot

_MUTED = colors.HexColor("#667085")
_QUIET = colors.HexColor("#98a2b3")
_RULE = colors.HexColor("#e5e7eb")
_TEXT = colors.HexColor("#18212f")

_MARGIN = 0.9 * inch


def _format_money(amount: float, *, signed: bool = False) -> str:
    """The one money formatter this renderer uses -- whole-dollar,
    comma-grouped, mirrors the rest of the application so a figure
    reads identically everywhere. Never lets a float artifact (e.g.
    -2630.0000000000023) reach the page."""
    rounded = round(abs(amount))
    formatted = f"${rounded:,}"
    if not signed:
        return formatted
    if amount > 0:
        return f"+{formatted}"
    if amount < 0:
        return f"-{formatted}"
    return formatted


def _format_tier(tier: str) -> str:
    return tier.replace("_", " ").title()


def _format_coverage(coverage: str) -> str:
    return coverage.replace("_", " ").title()


def _format_included(flag: bool) -> str:
    return "Included" if flag else "Not Included"


def _format_deal_context(renewal: bool) -> str:
    return "Renewal" if renewal else "New Business"


def _format_history_years(years: int) -> str:
    return f"{years} year{'s' if years != 1 else ''}"


def _format_contract_months(months: int) -> str:
    return f"{months} months"


def _escape(text: str) -> str:
    """Narrative is plain text, never customer-supplied markup -- this
    escapes it for ReportLab's minimal paragraph markup and turns
    literal newlines into real line breaks."""
    return _xml_escape(text).replace("\n", "<br/>")


def _build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle(
            "brand", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=14,
            textColor=_TEXT, letterSpacing=1.2,
        ),
        "brandSub": ParagraphStyle(
            "brandSub", parent=base["Normal"], fontName="Helvetica", fontSize=8,
            textColor=_MUTED, letterSpacing=1.5, spaceAfter=0,
        ),
        "title": ParagraphStyle(
            "title", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=22,
            textColor=_TEXT,
        ),
        "heading": ParagraphStyle(
            "heading", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=12,
            textColor=_TEXT, spaceAfter=8,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontName="Helvetica", fontSize=10.5,
            textColor=_TEXT, leading=15,
        ),
        "footnote": ParagraphStyle(
            "footnote", parent=base["Normal"], fontName="Helvetica-Oblique", fontSize=9,
            textColor=_MUTED,
        ),
    }


class ReportLabProposalRenderer:
    """See ProposalRenderer (src/proposals/renderer.py) for the
    interface contract this implements."""

    def render(
        self,
        snapshot: ProposalSnapshot,
        *,
        proposal_id: str,
        template_version: str,
        generated_at: datetime,
    ) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=LETTER,
            topMargin=_MARGIN,
            bottomMargin=_MARGIN,
            leftMargin=_MARGIN,
            rightMargin=_MARGIN,
            title=snapshot.narrative.proposal_title,
        )
        styles = _build_styles()
        story = []

        story.append(Paragraph("NORTHSTAR", styles["brand"]))
        story.append(Paragraph("PRICING STUDIO", styles["brandSub"]))
        story.append(Spacer(1, 20))
        story.append(Paragraph(_escape(snapshot.narrative.proposal_title), styles["title"]))
        story.append(Spacer(1, 16))

        meta_rows = [
            ["Prepared for", snapshot.customer_name],
            ["Quote", snapshot.quote_id],
            ["Pricing Version", f"v{snapshot.quote_version_number}"],
            ["Prepared by", snapshot.owner],
            ["Generated", generated_at.strftime("%B %d, %Y")],
        ]
        meta_table = Table(meta_rows, colWidths=[1.7 * inch, 4.0 * inch])
        meta_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("TEXTCOLOR", (0, 0), (0, -1), _MUTED),
                    ("TEXTCOLOR", (1, 0), (1, -1), _TEXT),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(meta_table)
        story.append(Spacer(1, 26))

        story.append(Paragraph("Executive Summary", styles["heading"]))
        story.append(Paragraph(_escape(snapshot.narrative.executive_summary), styles["body"]))
        story.append(Spacer(1, 20))

        story.append(Paragraph("Proposed Solution", styles["heading"]))
        config = snapshot.configuration_snapshot
        solution_rows = [
            ["Tier", _format_tier(config.tier)],
            ["Users", str(config.users)],
            ["Coverage", _format_coverage(config.coverage)],
            ["Historical Data", _format_history_years(config.history_years)],
            ["Premium Support", _format_included(config.premium_support)],
            ["Implementation Services", _format_included(config.implementation_services)],
            ["Contract Term", _format_contract_months(config.contract_months)],
            ["Commercial Context", _format_deal_context(config.renewal)],
        ]
        solution_table = Table(solution_rows, colWidths=[2.3 * inch, 3.4 * inch])
        solution_table.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("TEXTCOLOR", (0, 0), (0, -1), _MUTED),
                    ("TEXTCOLOR", (1, 0), (1, -1), _TEXT),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.5, _RULE),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(solution_table)
        story.append(Spacer(1, 20))

        story.append(Paragraph("Pricing", styles["heading"]))
        pricing = snapshot.pricing_snapshot
        price_rows: list[list[str]] = [["Base Price", _format_money(pricing.base_price)]]
        for adjustment in pricing.adjustments:
            price_rows.append([adjustment.name, _format_money(adjustment.amount, signed=True)])
        price_rows.append(["Subtotal", _format_money(pricing.subtotal_before_discount)])
        if pricing.discount_amount:
            price_rows.append(["Discount", _format_money(-pricing.discount_amount, signed=True)])

        price_table = Table(price_rows, colWidths=[3.7 * inch, 2.0 * inch])
        price_table.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("TEXTCOLOR", (0, 0), (-1, -1), _TEXT),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.5, _RULE),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(price_table)
        story.append(Spacer(1, 10))

        final_table = Table(
            [["Final Price", _format_money(pricing.final_price)]], colWidths=[3.7 * inch, 2.0 * inch]
        )
        final_table.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 17),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                    ("TEXTCOLOR", (0, 0), (-1, -1), _TEXT),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(final_table)
        story.append(Spacer(1, 26))

        if snapshot.narrative.commercial_notes:
            story.append(Paragraph("Commercial Notes", styles["heading"]))
            story.append(Paragraph(_escape(snapshot.narrative.commercial_notes), styles["body"]))
            story.append(Spacer(1, 20))

        if snapshot.narrative.valid_through:
            story.append(
                Paragraph(
                    f"This proposal is valid through "
                    f"{snapshot.narrative.valid_through.strftime('%B %d, %Y')}.",
                    styles["footnote"],
                )
            )

        def _draw_footer(canvas, pdf_doc) -> None:
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(_QUIET)
            canvas.drawString(_MARGIN, 0.6 * inch, "Northstar Pricing Studio")
            canvas.drawCentredString(
                LETTER[0] / 2,
                0.6 * inch,
                f"{snapshot.quote_id} • v{snapshot.quote_version_number} • {proposal_id}",
            )
            canvas.drawRightString(LETTER[0] - _MARGIN, 0.6 * inch, f"Page {pdf_doc.page}")
            canvas.restoreState()

        doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
        return buffer.getvalue()
