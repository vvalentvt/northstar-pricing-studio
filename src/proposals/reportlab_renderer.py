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
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing, Polygon
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import ProposalSnapshot

# Same palette as frontend/src/styles/tokens.css -- the PDF and the
# React app are deliberately one brand, not two (Phase 7B).
_MUTED = colors.HexColor("#636b7d")
_QUIET = colors.HexColor("#8891a6")
_RULE = colors.HexColor("#dde1e8")
_TEXT = colors.HexColor("#161a24")
_ACCENT = colors.HexColor("#3347c9")
_INK = colors.HexColor("#10131c")
_QUIET_HEX = "#8891a6"

_MARGIN = 0.9 * inch

#: The exact four-point star geometry drawn in
#: frontend/src/brand/NorthstarMark.tsx (viewBox 0 0 24 24), redrawn
#: here as a deterministic ReportLab vector shape -- never a loaded
#: image file, so the app and the PDF share one mark with zero binary
#: asset duplication.
_MARK_POINTS = (12, 1, 14.97, 9.03, 23, 12, 14.97, 14.97, 12, 23, 9.03, 14.97, 1, 12, 9.03, 9.03)


def _northstar_mark(size: float) -> Drawing:
    scale = size / 24
    points = [coordinate * scale for coordinate in _MARK_POINTS]
    drawing = Drawing(size, size)
    drawing.add(Polygon(points, fillColor=_ACCENT, strokeColor=None))
    return drawing


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
            textColor=_INK, letterSpacing=1.2,
        ),
        "brandSub": ParagraphStyle(
            "brandSub", parent=base["Normal"], fontName="Helvetica", fontSize=7.5,
            textColor=_MUTED, letterSpacing=1.8, spaceAfter=0,
        ),
        "eyebrow": ParagraphStyle(
            "eyebrow", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9,
            textColor=_ACCENT, letterSpacing=2, spaceAfter=6,
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


def _numbered_heading(number: str, text: str, style: ParagraphStyle) -> Paragraph:
    """An understated section number ahead of a heading -- improves
    document orientation without a heavy numbering treatment."""
    return Paragraph(f'<font color="{_QUIET_HEX}">{number}</font>&nbsp;&nbsp;{text}', style)


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

        wordmark = Paragraph(
            f'NORTHSTAR<br/><font size="7.5" color="{_QUIET_HEX}">PRICING STUDIO</font>',
            styles["brand"],
        )
        brand_lockup = Table(
            [[_northstar_mark(16), wordmark]],
            colWidths=[0.28 * inch, 2.5 * inch],
        )
        brand_lockup.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (1, 0), (1, 0), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        story.append(brand_lockup)
        story.append(Spacer(1, 18))
        story.append(Paragraph("PRICING PROPOSAL", styles["eyebrow"]))
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

        story.append(_numbered_heading("01", "Executive Summary", styles["heading"]))
        story.append(Paragraph(_escape(snapshot.narrative.executive_summary), styles["body"]))
        story.append(Spacer(1, 20))

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
        solution_table = Table(solution_rows, colWidths=[2.3 * inch, 3.4 * inch], splitByRow=0)
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
        story.append(
            KeepTogether(
                [_numbered_heading("02", "Proposed Solution", styles["heading"]), solution_table]
            )
        )
        story.append(Spacer(1, 20))

        pricing = snapshot.pricing_snapshot
        price_rows: list[list[str]] = [["Base Price", _format_money(pricing.base_price)]]
        for adjustment in pricing.adjustments:
            price_rows.append([adjustment.name, _format_money(adjustment.amount, signed=True)])
        price_rows.append(["Subtotal", _format_money(pricing.subtotal_before_discount)])
        if pricing.discount_amount:
            price_rows.append(["Discount", _format_money(-pricing.discount_amount, signed=True)])

        # splitByRow=0: this table must never split mid-row across a
        # page boundary -- a "Base Price ... Subtotal" table missing
        # its own Final Price on the next page reads as broken, not
        # just awkward (see Phase 7B spec section 31).
        price_table = Table(price_rows, colWidths=[3.7 * inch, 2.0 * inch], splitByRow=0)
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

        final_table = Table(
            [["Final Price", _format_money(pricing.final_price)]],
            colWidths=[3.7 * inch, 2.0 * inch],
            splitByRow=0,
        )
        final_table.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 18),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                    ("TEXTCOLOR", (0, 0), (-1, -1), _ACCENT),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("LINEABOVE", (0, 0), (-1, 0), 1.2, _ACCENT),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )

        # The whole "Pricing" section -- heading through Final Price --
        # moves to the next page as one block rather than splitting:
        # Final Price must never be orphaned away from the breakdown
        # that explains it.
        story.append(
            KeepTogether(
                [
                    _numbered_heading("03", "Pricing", styles["heading"]),
                    price_table,
                    Spacer(1, 10),
                    final_table,
                ]
            )
        )
        story.append(Spacer(1, 26))

        if snapshot.narrative.commercial_notes:
            story.append(_numbered_heading("04", "Commercial Notes", styles["heading"]))
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
            canvas.setStrokeColor(_RULE)
            canvas.setLineWidth(0.5)
            canvas.line(_MARGIN, 0.78 * inch, LETTER[0] - _MARGIN, 0.78 * inch)
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(_QUIET)
            canvas.drawString(_MARGIN, 0.6 * inch, "NORTHSTAR PRICING STUDIO")
            canvas.drawCentredString(
                LETTER[0] / 2,
                0.6 * inch,
                f"{snapshot.quote_id} • v{snapshot.quote_version_number} • {proposal_id}",
            )
            canvas.drawRightString(LETTER[0] - _MARGIN, 0.6 * inch, f"Page {pdf_doc.page}")
            canvas.restoreState()

        doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
        return buffer.getvalue()
