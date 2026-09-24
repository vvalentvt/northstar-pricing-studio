import copy
import sqlite3
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pricing_engine import QuoteRequest, calculate_quote, load_rules
from quotes import NegotiationContext, PricingSnapshot, Quote, QuoteVersionSource
from persistence import (
    DuplicateQuoteError,
    QuoteNotFoundError,
    QuoteVersionConflict,
    QuoteVersionNotFoundError,
    SQLiteQuoteRepository,
)

RULES = load_rules(ROOT / "config" / "pricing_rules.yaml")


def _configuration(**overrides) -> QuoteRequest:
    defaults = dict(
        customer_name="Acme",
        tier="core",
        users=5,
        coverage="national",
        history_years=1,
        contract_months=12,
    )
    defaults.update(overrides)
    return QuoteRequest(**defaults)


def _snapshot(configuration: QuoteRequest, rules: dict | None = None) -> PricingSnapshot:
    result = calculate_quote(configuration, rules if rules is not None else RULES)
    return PricingSnapshot.from_pricing_result(result)


def _quote(quote_id: str = "Q-00001", **overrides) -> Quote:
    configuration = _configuration(**overrides)
    snapshot = _snapshot(configuration)
    return Quote.create(
        quote_id=quote_id,
        customer_name="Acme",
        owner="vinnie",
        configuration=configuration,
        pricing_snapshot=snapshot,
    )


def _repo(tmp_path: Path) -> SQLiteQuoteRepository:
    return SQLiteQuoteRepository(tmp_path / "northstar.db")


def test_create_then_get_round_trips_identically(tmp_path):
    repo = _repo(tmp_path)
    quote = _quote()

    repo.create(quote)
    loaded = repo.get(quote.quote_id)

    assert loaded == quote


def test_create_duplicate_quote_id_raises(tmp_path):
    repo = _repo(tmp_path)
    quote = _quote()
    repo.create(quote)

    with pytest.raises(DuplicateQuoteError):
        repo.create(quote)


def test_get_missing_quote_raises_not_found(tmp_path):
    repo = _repo(tmp_path)

    with pytest.raises(QuoteNotFoundError):
        repo.get("Q-does-not-exist")


def test_exists_true_and_false(tmp_path):
    repo = _repo(tmp_path)
    quote = _quote()
    repo.create(quote)

    assert repo.exists(quote.quote_id) is True
    assert repo.exists("Q-does-not-exist") is False


def test_get_version_returns_single_historical_version(tmp_path):
    repo = _repo(tmp_path)
    quote = _quote()
    repo.create(quote)

    version = repo.get_version(quote.quote_id, 1)

    assert version == quote.versions[0]


def test_get_version_missing_quote_raises_not_found(tmp_path):
    repo = _repo(tmp_path)

    with pytest.raises(QuoteNotFoundError):
        repo.get_version("Q-does-not-exist", 1)


def test_get_version_missing_version_raises_version_not_found(tmp_path):
    repo = _repo(tmp_path)
    quote = _quote()
    repo.create(quote)

    with pytest.raises(QuoteVersionNotFoundError):
        repo.get_version(quote.quote_id, 2)


def test_append_version_persists_second_version(tmp_path):
    repo = _repo(tmp_path)
    quote = _quote()
    repo.create(quote)

    revised_configuration = _configuration(requested_discount_percent=10)
    revised_snapshot = _snapshot(revised_configuration)
    new_version = quote.add_version(
        configuration=revised_configuration,
        pricing_snapshot=revised_snapshot,
        source=QuoteVersionSource.MANUAL_REVISION,
    )

    repo.append_version(quote.quote_id, new_version, expected_current_version=1)

    reloaded = repo.get(quote.quote_id)
    assert reloaded.current_version.version_number == 2
    assert reloaded.current_version == new_version
    assert reloaded.versions[0] == quote.versions[0]


def test_append_version_is_never_an_update(tmp_path):
    repo = _repo(tmp_path)
    quote = _quote()
    repo.create(quote)

    revised_configuration = _configuration(requested_discount_percent=10)
    revised_snapshot = _snapshot(revised_configuration)
    new_version = quote.add_version(
        configuration=revised_configuration,
        pricing_snapshot=revised_snapshot,
        source=QuoteVersionSource.MANUAL_REVISION,
    )
    repo.append_version(quote.quote_id, new_version, expected_current_version=1)

    reloaded = repo.get(quote.quote_id)
    assert len(reloaded.versions) == 2
    assert reloaded.versions[0].version_number == 1
    assert reloaded.versions[1].version_number == 2


def test_append_version_rejects_stale_expected_version(tmp_path):
    repo = _repo(tmp_path)
    quote = _quote()
    repo.create(quote)

    revised_configuration = _configuration(requested_discount_percent=10)
    revised_snapshot = _snapshot(revised_configuration)
    new_version = quote.add_version(
        configuration=revised_configuration,
        pricing_snapshot=revised_snapshot,
        source=QuoteVersionSource.MANUAL_REVISION,
    )

    with pytest.raises(QuoteVersionConflict):
        repo.append_version(quote.quote_id, new_version, expected_current_version=0)


def test_append_version_rejects_non_sequential_version_number(tmp_path):
    repo = _repo(tmp_path)
    quote = _quote()
    repo.create(quote)

    configuration = _configuration(requested_discount_percent=10)
    snapshot = _snapshot(configuration)
    from quotes import QuoteVersion

    skip_ahead_version = QuoteVersion(
        version_number=3,
        configuration_snapshot=quote.versions[0].configuration_snapshot.__class__.from_request(configuration),
        pricing_snapshot=snapshot,
        source=QuoteVersionSource.MANUAL_REVISION,
    )

    with pytest.raises(QuoteVersionConflict):
        repo.append_version(quote.quote_id, skip_ahead_version, expected_current_version=1)


def test_append_version_missing_quote_raises_not_found(tmp_path):
    repo = _repo(tmp_path)
    configuration = _configuration()
    snapshot = _snapshot(configuration)
    quote = Quote.create(
        quote_id="Q-ghost",
        customer_name="Acme",
        owner="vinnie",
        configuration=configuration,
        pricing_snapshot=snapshot,
    )

    with pytest.raises(QuoteNotFoundError):
        repo.append_version(quote.quote_id, quote.versions[0], expected_current_version=0)


def test_negotiation_context_round_trips(tmp_path):
    repo = _repo(tmp_path)
    configuration = _configuration()
    snapshot = _snapshot(configuration)
    context = NegotiationContext(
        target_budget=20000,
        required_attributes=("national",),
        flexible_attributes=("contract_months",),
    )
    quote = Quote.create(
        quote_id="Q-neg",
        customer_name="Acme",
        owner="vinnie",
        configuration=configuration,
        pricing_snapshot=snapshot,
        negotiation_context=context,
    )
    repo.create(quote)

    loaded = repo.get(quote.quote_id)

    assert loaded.versions[0].negotiation_context == context


def test_persistence_survives_across_repository_instances(tmp_path):
    """The Persistence Survival Test: a second, independently-opened
    repository against the same SQLite file must see exactly what the
    first repository wrote -- proving data lives in the file, not in
    any in-process cache or connection state."""
    db_path = tmp_path / "northstar.db"
    quote = _quote()

    repo_a = SQLiteQuoteRepository(db_path)
    repo_a.create(quote)
    del repo_a

    repo_b = SQLiteQuoteRepository(db_path)
    loaded = repo_b.get(quote.quote_id)

    assert loaded == quote
    assert loaded.versions[0] == quote.versions[0]


def test_historical_version_unaffected_by_later_rule_changes(tmp_path):
    """The Historical Rule Change Test: once a PricingSnapshot is
    persisted, changing the in-memory pricing rules afterward must never
    alter what gets read back -- final price, approval state, discount
    authority thresholds, and rule_version must all stay exactly as they
    were calculated at persist time."""
    repo = _repo(tmp_path)
    configuration = _configuration()
    original_snapshot = _snapshot(configuration, RULES)
    quote = Quote.create(
        quote_id="Q-history",
        customer_name="Acme",
        owner="vinnie",
        configuration=configuration,
        pricing_snapshot=original_snapshot,
    )
    repo.create(quote)

    mutated_rules = copy.deepcopy(RULES)
    mutated_rules["version"] = "9.9.9"
    mutated_rules["tiers"]["core"]["base_price"] = 999999
    mutated_rules["discount_policy"]["max_self_service_percent"] = 0
    mutated_rules["discount_policy"]["max_allowed_percent"] = 0

    reloaded = repo.get(quote.quote_id)
    reloaded_snapshot = reloaded.current_version.pricing_snapshot

    assert reloaded_snapshot.rule_version == original_snapshot.rule_version
    assert reloaded_snapshot.final_price == original_snapshot.final_price
    assert reloaded_snapshot.approval_required == original_snapshot.approval_required
    assert (
        reloaded_snapshot.self_service_threshold_percent
        == original_snapshot.self_service_threshold_percent
    )
    assert (
        reloaded_snapshot.max_allowed_discount_percent
        == original_snapshot.max_allowed_discount_percent
    )
    assert reloaded_snapshot.base_price == original_snapshot.base_price


def test_schema_is_idempotent_across_repeated_init(tmp_path):
    db_path = tmp_path / "northstar.db"
    SQLiteQuoteRepository(db_path)
    SQLiteQuoteRepository(db_path)

    quote = _quote()
    repo = SQLiteQuoteRepository(db_path)
    repo.create(quote)
    assert repo.get(quote.quote_id) == quote


def test_foreign_keys_are_enforced(tmp_path):
    db_path = tmp_path / "northstar.db"
    SQLiteQuoteRepository(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO quote_versions "
            "(quote_id, version_number, source, created_at, "
            " configuration_snapshot_json, pricing_snapshot_json, negotiation_context_json) "
            "VALUES ('Q-orphan', 1, 'initial', '2024-01-01T00:00:00', '{}', '{}', NULL)"
        )
    conn.close()
