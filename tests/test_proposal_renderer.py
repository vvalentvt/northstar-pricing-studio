from datetime import date, datetime, timezone
from pathlib import Path
import sys

from pypdf import PdfReader
import io

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quotes import AdjustmentSnapshot, ConfigurationSnapshot, PricingSnapshot
from proposals import ProposalNarrative, ProposalSnapshot, ReportLabProposalRenderer

RENDERER = ReportLabProposalRenderer()


def _configuration(**overrides) -> ConfigurationSnapshot:
    defaults = dict(
        customer_name="Acme Test",
        tier="growth",
        users=8,
        coverage="north_america",
        history_years=3,
        contract_months=24,
        premium_support=True,
        implementation_services=False,
        renewal=False,
        requested_discount_percent=0,
    )
    defaults.update(overrides)
    return ConfigurationSnapshot(**defaults)


def _pricing(**overrides) -> PricingSnapshot:
    defaults = dict(
        rule_version="0.1.0",
        base_price=45000,
        adjustments=(
            AdjustmentSnapshot(
                name="Additional users", amount=3750, explanation="3 users above included"
            ),
            AdjustmentSnapshot(
                name="Contract term adjustment",
                amount=-2630.0000000000023,
                explanation="24-month term adjustment",
            ),
        ),
        subtotal_before_discount=63120,
        discount_amount=0,
        final_price=63120,
        approval_required=False,
        approval_reason=None,
        self_service_threshold_percent=10,
        max_allowed_discount_percent=25,
    )
    defaults.update(overrides)
    return PricingSnapshot(**defaults)


def _narrative(**overrides) -> ProposalNarrative:
    defaults = dict(
        proposal_title="Pricing Proposal",
        executive_summary="Northstar is pleased to provide this pricing proposal for Acme Test.",
    )
    defaults.update(overrides)
    return ProposalNarrative(**defaults)


def _snapshot(**overrides) -> ProposalSnapshot:
    defaults = dict(
        quote_id="Q-12345",
        quote_version_number=1,
        customer_name="Acme Test",
        owner="Vincent",
        narrative=_narrative(),
        configuration_snapshot=_configuration(),
        pricing_snapshot=_pricing(),
    )
    defaults.update(overrides)
    return ProposalSnapshot(**defaults)


def _render(snapshot: ProposalSnapshot) -> bytes:
    return RENDERER.render(
        snapshot,
        proposal_id="P-00001",
        template_version="northstar-proposal-v1",
        generated_at=datetime(2026, 10, 27, tzinfo=timezone.utc),
    )


def _extract_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() for page in reader.pages)


def test_returns_non_empty_bytes():
    pdf_bytes = _render(_snapshot())

    assert len(pdf_bytes) > 0


def test_output_begins_with_valid_pdf_signature():
    pdf_bytes = _render(_snapshot())

    assert pdf_bytes[:5] == b"%PDF-"


def test_renders_successfully_with_no_commercial_notes():
    snapshot = _snapshot(narrative=_narrative(commercial_notes=None))

    pdf_bytes = _render(snapshot)

    assert pdf_bytes[:5] == b"%PDF-"
    text = _extract_text(pdf_bytes)
    assert "Commercial Notes" not in text


def test_renders_successfully_with_long_narrative():
    long_summary = "This is a long paragraph. " * 100
    snapshot = _snapshot(narrative=_narrative(executive_summary=long_summary))

    pdf_bytes = _render(snapshot)

    assert pdf_bytes[:5] == b"%PDF-"


def test_negative_adjustment_formats_without_float_artifacts():
    pdf_bytes = _render(_snapshot())
    text = _extract_text(pdf_bytes)

    assert "-$2,630" in text
    assert "2630.0000000000023" not in text
    assert "2630.00" not in text


def test_positive_adjustment_formats_with_sign():
    pdf_bytes = _render(_snapshot())
    text = _extract_text(pdf_bytes)

    assert "+$3,750" in text


def test_final_price_comes_from_snapshot():
    snapshot = _snapshot(pricing_snapshot=_pricing(final_price=59964))
    pdf_bytes = _render(snapshot)
    text = _extract_text(pdf_bytes)

    assert "$59,964" in text


def test_discount_renders_when_present():
    snapshot = _snapshot(
        pricing_snapshot=_pricing(discount_amount=3156, final_price=59964)
    )
    pdf_bytes = _render(snapshot)
    text = _extract_text(pdf_bytes)

    assert "-$3,156" in text


def test_human_readable_configuration_formatting():
    pdf_bytes = _render(_snapshot())
    text = _extract_text(pdf_bytes)

    assert "Growth" in text
    assert "North America" in text
    assert "Included" in text
    assert "Not Included" in text
    assert "New Business" in text
    assert "3 years" in text
    assert "24 months" in text


def test_renewal_configuration_shows_renewal_context():
    snapshot = _snapshot(configuration_snapshot=_configuration(renewal=True))
    pdf_bytes = _render(snapshot)
    text = _extract_text(pdf_bytes)

    assert "Renewal" in text


def test_internal_governance_fields_never_rendered():
    """The PDF must never leak discount-authority thresholds, approval
    state/reason, or rule_version -- those belong on the internal
    Review Pricing surface, not a customer-facing document."""
    snapshot = _snapshot(
        pricing_snapshot=_pricing(
            self_service_threshold_percent=10,
            max_allowed_discount_percent=25,
            approval_required=True,
            approval_reason="Discount exceeds the 10% self-service threshold",
        )
    )
    pdf_bytes = _render(snapshot)
    text = _extract_text(pdf_bytes).lower()

    assert "threshold" not in text
    assert "approval" not in text
    assert "self-service" not in text
    assert "0.1.0" not in text


def test_valid_through_renders_when_present():
    snapshot = _snapshot(narrative=_narrative(valid_through=date(2026, 12, 31)))
    pdf_bytes = _render(snapshot)
    text = _extract_text(pdf_bytes)

    assert "December 31, 2026" in text


def test_quote_and_version_and_proposal_id_appear_in_footer():
    pdf_bytes = _render(_snapshot())
    text = _extract_text(pdf_bytes)

    assert "Q-12345" in text
    assert "P-00001" in text


def test_brand_lockup_and_eyebrow_appear_on_the_first_page():
    pdf_bytes = _render(_snapshot())
    reader = PdfReader(io.BytesIO(pdf_bytes))
    first_page_text = reader.pages[0].extract_text()

    assert "NORTHSTAR" in first_page_text
    assert "PRICING STUDIO" in first_page_text
    assert "PRICING PROPOSAL" in first_page_text


def test_section_headings_are_numbered_for_document_orientation():
    pdf_bytes = _render(_snapshot(narrative=_narrative(commercial_notes="Notes.")))
    text = _extract_text(pdf_bytes)

    assert "01" in text and "Executive Summary" in text
    assert "02" in text and "Proposed Solution" in text
    assert "03" in text and "Pricing" in text
    assert "04" in text and "Commercial Notes" in text


def test_footer_carries_the_northstar_brand_name():
    pdf_bytes = _render(_snapshot())
    text = _extract_text(pdf_bytes)

    assert "NORTHSTAR PRICING STUDIO" in text
