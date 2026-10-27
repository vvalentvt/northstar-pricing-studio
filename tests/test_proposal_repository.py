import copy
from datetime import date, datetime, timezone
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pricing_engine import QuoteRequest, calculate_quote, load_rules
from quotes import PricingSnapshot, Quote, QuoteVersionSource, ScenarioWorkspace
from proposals import Proposal, ProposalNarrative, ProposalSnapshot
from persistence import (
    DuplicateProposalError,
    ProposalNotFoundError,
    SQLiteProposalRepository,
    SQLiteQuoteRepository,
    SQLiteScenarioRepository,
)

RULES = load_rules(ROOT / "config" / "pricing_rules.yaml")


def _configuration(**overrides) -> QuoteRequest:
    defaults = dict(
        customer_name="Acme",
        tier="growth",
        users=8,
        coverage="north_america",
        history_years=3,
        contract_months=24,
        premium_support=True,
    )
    defaults.update(overrides)
    return QuoteRequest(**defaults)


def _seed_quote(db_path: Path, quote_id: str = "Q-00001", **config_overrides) -> Quote:
    repo = SQLiteQuoteRepository(db_path)
    configuration = _configuration(**config_overrides)
    result = calculate_quote(configuration, RULES)
    snapshot = PricingSnapshot.from_pricing_result(result)
    quote = Quote.create(
        quote_id=quote_id, customer_name="Acme", owner="vinnie",
        configuration=configuration, pricing_snapshot=snapshot,
    )
    repo.create(quote)
    return quote


def _narrative(**overrides) -> ProposalNarrative:
    defaults = dict(
        proposal_title="Pricing Proposal",
        executive_summary="Northstar is pleased to provide this pricing proposal for Acme.",
        commercial_notes=None,
        valid_through=None,
    )
    defaults.update(overrides)
    return ProposalNarrative(**defaults)


def _proposal(quote: Quote, proposal_id: str = "P-00001", **overrides) -> Proposal:
    version = quote.current_version
    snapshot = ProposalSnapshot(
        quote_id=quote.quote_id,
        quote_version_number=version.version_number,
        customer_name=quote.customer_name,
        owner=quote.owner,
        narrative=_narrative(),
        configuration_snapshot=version.configuration_snapshot,
        pricing_snapshot=version.pricing_snapshot,
    )
    defaults = dict(
        proposal_id=proposal_id,
        quote_id=quote.quote_id,
        quote_version_number=version.version_number,
        created_at=datetime.now(timezone.utc),
        template_version="northstar-proposal-v1",
        filename=f"Northstar_Proposal_Acme_{quote.quote_id}_v{version.version_number}.pdf",
        snapshot=snapshot,
    )
    defaults.update(overrides)
    return Proposal(**defaults)


_FAKE_PDF_BYTES = b"%PDF-1.4 fake pdf content for tests\n%%EOF"


def test_proposal_round_trips_preserving_identity(tmp_path):
    db_path = tmp_path / "northstar.db"
    quote = _seed_quote(db_path)
    repo = SQLiteProposalRepository(db_path)
    proposal = _proposal(quote)

    repo.create(proposal, _FAKE_PDF_BYTES)
    loaded = repo.get(proposal.proposal_id)

    assert loaded.proposal_id == proposal.proposal_id
    assert loaded.quote_id == quote.quote_id
    assert loaded.quote_version_number == 1


def test_snapshot_preserves_quote_and_version(tmp_path):
    db_path = tmp_path / "northstar.db"
    quote = _seed_quote(db_path)
    repo = SQLiteProposalRepository(db_path)
    proposal = _proposal(quote)
    repo.create(proposal, _FAKE_PDF_BYTES)

    loaded = repo.get(proposal.proposal_id)

    assert loaded.snapshot.quote_id == quote.quote_id
    assert loaded.snapshot.quote_version_number == 1


def test_pricing_snapshot_preserved_exactly(tmp_path):
    db_path = tmp_path / "northstar.db"
    quote = _seed_quote(db_path)
    repo = SQLiteProposalRepository(db_path)
    proposal = _proposal(quote)
    repo.create(proposal, _FAKE_PDF_BYTES)

    loaded = repo.get(proposal.proposal_id)

    assert loaded.snapshot.pricing_snapshot == quote.current_version.pricing_snapshot


def test_configuration_snapshot_preserved_exactly(tmp_path):
    db_path = tmp_path / "northstar.db"
    quote = _seed_quote(db_path, tier="enterprise", users=20, coverage="global")
    repo = SQLiteProposalRepository(db_path)
    proposal = _proposal(quote)
    repo.create(proposal, _FAKE_PDF_BYTES)

    loaded = repo.get(proposal.proposal_id)

    assert loaded.snapshot.configuration_snapshot == quote.current_version.configuration_snapshot
    assert loaded.snapshot.configuration_snapshot.tier == "enterprise"


def test_narrative_preserved(tmp_path):
    db_path = tmp_path / "northstar.db"
    quote = _seed_quote(db_path)
    repo = SQLiteProposalRepository(db_path)
    narrative = _narrative(
        proposal_title="Custom Title",
        executive_summary="Custom summary text.",
        commercial_notes="Multi-year discount available.",
        valid_through=date(2026, 12, 31),
    )
    proposal = _proposal(quote)
    proposal = proposal.model_copy(
        update={"snapshot": proposal.snapshot.model_copy(update={"narrative": narrative})}
    )
    repo.create(proposal, _FAKE_PDF_BYTES)

    loaded = repo.get(proposal.proposal_id)

    assert loaded.snapshot.narrative == narrative
    assert loaded.snapshot.narrative.commercial_notes == "Multi-year discount available."
    assert loaded.snapshot.narrative.valid_through == date(2026, 12, 31)


def test_template_version_preserved(tmp_path):
    db_path = tmp_path / "northstar.db"
    quote = _seed_quote(db_path)
    repo = SQLiteProposalRepository(db_path)
    proposal = _proposal(quote, template_version="northstar-proposal-v2")
    repo.create(proposal, _FAKE_PDF_BYTES)

    loaded = repo.get(proposal.proposal_id)

    assert loaded.template_version == "northstar-proposal-v2"


def test_pdf_bytes_preserved_exactly(tmp_path):
    db_path = tmp_path / "northstar.db"
    quote = _seed_quote(db_path)
    repo = SQLiteProposalRepository(db_path)
    proposal = _proposal(quote)
    pdf_bytes = b"%PDF-1.4 " + bytes(range(256)) + b"\n%%EOF"
    repo.create(proposal, pdf_bytes)

    loaded_bytes = repo.get_pdf(proposal.proposal_id)

    assert loaded_bytes == pdf_bytes


def test_repository_survives_recreation(tmp_path):
    db_path = tmp_path / "northstar.db"
    quote = _seed_quote(db_path)
    repo_a = SQLiteProposalRepository(db_path)
    proposal = _proposal(quote)
    repo_a.create(proposal, _FAKE_PDF_BYTES)
    del repo_a

    repo_b = SQLiteProposalRepository(db_path)
    loaded = repo_b.get(proposal.proposal_id)
    loaded_pdf = repo_b.get_pdf(proposal.proposal_id)

    assert loaded == proposal
    assert loaded_pdf == _FAKE_PDF_BYTES


def test_list_for_quote_ordered_deterministically(tmp_path):
    db_path = tmp_path / "northstar.db"
    quote = _seed_quote(db_path)
    repo = SQLiteProposalRepository(db_path)
    first = _proposal(quote, proposal_id="P-00001", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    second = _proposal(quote, proposal_id="P-00002", created_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    repo.create(first, _FAKE_PDF_BYTES)
    repo.create(second, _FAKE_PDF_BYTES)

    listed_once = repo.list_for_quote(quote.quote_id)
    listed_twice = repo.list_for_quote(quote.quote_id)

    assert [p.proposal_id for p in listed_once] == ["P-00001", "P-00002"]
    assert listed_once == listed_twice


def test_multiple_proposals_can_exist_for_one_quote_version(tmp_path):
    db_path = tmp_path / "northstar.db"
    quote = _seed_quote(db_path)
    repo = SQLiteProposalRepository(db_path)
    repo.create(_proposal(quote, proposal_id="P-00001"), _FAKE_PDF_BYTES)
    repo.create(_proposal(quote, proposal_id="P-00002"), _FAKE_PDF_BYTES)

    listed = repo.list_for_quote(quote.quote_id)

    assert len(listed) == 2
    assert all(p.quote_version_number == 1 for p in listed)


def test_proposal_cannot_overwrite_another_proposal(tmp_path):
    db_path = tmp_path / "northstar.db"
    quote = _seed_quote(db_path)
    repo = SQLiteProposalRepository(db_path)
    repo.create(_proposal(quote, proposal_id="P-00001"), _FAKE_PDF_BYTES)

    with pytest.raises(DuplicateProposalError):
        repo.create(_proposal(quote, proposal_id="P-00001"), b"different bytes")


def test_get_missing_proposal_raises(tmp_path):
    db_path = tmp_path / "northstar.db"
    _seed_quote(db_path)
    repo = SQLiteProposalRepository(db_path)

    with pytest.raises(ProposalNotFoundError):
        repo.get("P-does-not-exist")


def test_get_pdf_missing_proposal_raises(tmp_path):
    db_path = tmp_path / "northstar.db"
    _seed_quote(db_path)
    repo = SQLiteProposalRepository(db_path)

    with pytest.raises(ProposalNotFoundError):
        repo.get_pdf("P-does-not-exist")


def test_clearing_scenario_workspace_does_not_affect_proposal(tmp_path):
    db_path = tmp_path / "northstar.db"
    quote = _seed_quote(db_path)
    proposal_repo = SQLiteProposalRepository(db_path)
    scenario_repo = SQLiteScenarioRepository(db_path)
    proposal = _proposal(quote)
    proposal_repo.create(proposal, _FAKE_PDF_BYTES)
    scenario_repo.create_workspace(ScenarioWorkspace(quote_id=quote.quote_id, base_version_number=1))

    scenario_repo.clear_workspace(quote.quote_id)

    assert proposal_repo.get(proposal.proposal_id) == proposal
    assert proposal_repo.get_pdf(proposal.proposal_id) == _FAKE_PDF_BYTES


def test_proposals_for_v1_remain_after_quote_advances_to_v2(tmp_path):
    db_path = tmp_path / "northstar.db"
    quote = _seed_quote(db_path)
    quote_repo = SQLiteQuoteRepository(db_path)
    proposal_repo = SQLiteProposalRepository(db_path)
    p1 = _proposal(quote, proposal_id="P-00001")
    proposal_repo.create(p1, _FAKE_PDF_BYTES)

    v2 = quote.add_version(
        configuration=quote.current_version.configuration_snapshot,
        pricing_snapshot=quote.current_version.pricing_snapshot,
        source=QuoteVersionSource.MANUAL_REVISION,
    )
    quote_repo.append_version(quote.quote_id, v2, expected_current_version=1)

    reloaded_p1 = proposal_repo.get("P-00001")
    assert reloaded_p1.quote_version_number == 1
    assert reloaded_p1.snapshot.pricing_snapshot == quote.versions[0].pricing_snapshot


def test_historical_fidelity_survives_rule_change_and_quote_revision(tmp_path):
    """The critical fidelity test (Phase 6F spec section 32): a
    Proposal generated from v1 must be byte-identical in its stored
    facts even after pricing rules change in memory and the Quote
    advances to v2."""
    db_path = tmp_path / "northstar.db"
    quote = _seed_quote(db_path)
    quote_repo = SQLiteQuoteRepository(db_path)
    proposal_repo = SQLiteProposalRepository(db_path)

    original_pricing = quote.current_version.pricing_snapshot
    original_configuration = quote.current_version.configuration_snapshot
    p1 = _proposal(quote, proposal_id="P-00001", template_version="northstar-proposal-v1")
    proposal_repo.create(p1, _FAKE_PDF_BYTES)

    # Mutate in-memory rules -- must have zero effect on the already-persisted Proposal.
    mutated_rules = copy.deepcopy(RULES)
    mutated_rules["version"] = "9.9.9"
    mutated_rules["tiers"]["growth"]["base_price"] = 999999

    # Advance the Quote to v2 (a different template version is used for
    # a hypothetical later proposal, just to prove it doesn't leak backward).
    v2 = quote.add_version(
        configuration=quote.current_version.configuration_snapshot,
        pricing_snapshot=quote.current_version.pricing_snapshot,
        source=QuoteVersionSource.MANUAL_REVISION,
    )
    quote_repo.append_version(quote.quote_id, v2, expected_current_version=1)
    p2 = _proposal(quote_repo.get(quote.quote_id), proposal_id="P-00002", template_version="northstar-proposal-v2")
    proposal_repo.create(p2, b"%PDF-1.4 different bytes\n%%EOF")

    reloaded_p1 = proposal_repo.get("P-00001")
    reloaded_p1_pdf = proposal_repo.get_pdf("P-00001")

    assert reloaded_p1.quote_version_number == 1
    assert reloaded_p1.template_version == "northstar-proposal-v1"
    assert reloaded_p1.snapshot.configuration_snapshot == original_configuration
    assert reloaded_p1.snapshot.pricing_snapshot == original_pricing
    assert reloaded_p1.snapshot.pricing_snapshot.final_price == original_pricing.final_price
    assert reloaded_p1_pdf == _FAKE_PDF_BYTES

    reloaded_p2 = proposal_repo.get("P-00002")
    assert reloaded_p2.quote_version_number == 2
    assert reloaded_p2.template_version == "northstar-proposal-v2"
