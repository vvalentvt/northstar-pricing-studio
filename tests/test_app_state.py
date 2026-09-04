from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

from pricing_engine import calculate_quote, load_rules
from quotes import Quote, QuoteVersionSource

from app_state import (
    CommitError,
    ConfigurationInput,
    DealContext,
    DealType,
    PricingState,
    calculate_pricing,
    commit_quote,
    configuration_to_quote_request,
    create_quote,
    derive_status_label,
    is_stale,
    validate_deal_context,
)

RULES = load_rules(ROOT / "config" / "pricing_rules.yaml")


def _configuration(**overrides) -> ConfigurationInput:
    defaults = dict(
        tier="core",
        users=5,
        coverage="national",
        history_years=1,
        contract_months=12,
    )
    defaults.update(overrides)
    return ConfigurationInput(**defaults)


def test_deal_context_requires_customer():
    with pytest.raises(ValueError):
        validate_deal_context("   ", DealType.NEW_BUSINESS.value, "")

    context = validate_deal_context("Acme", DealType.NEW_BUSINESS.value, "2027 Subscription")

    assert context.customer_name == "Acme"
    assert context.deal_type == DealType.NEW_BUSINESS
    assert context.opportunity_reference == "2027 Subscription"


def test_configuration_maps_to_quote_request():
    configuration = _configuration(users=8, premium_support=True)

    request = configuration_to_quote_request("Acme", configuration)

    assert request.customer_name == "Acme"
    assert request.tier == "core"
    assert request.users == 8
    assert request.premium_support is True
    assert request.requested_discount_percent == 0.0


def test_calculation_uses_existing_pricing_engine():
    configuration = _configuration()

    result_via_app = calculate_pricing("Acme", configuration, RULES)
    result_via_engine = calculate_quote(
        configuration_to_quote_request("Acme", configuration), RULES
    )

    assert result_via_app == result_via_engine


def test_configuration_change_invalidates_previous_result():
    configuration = _configuration()
    result = calculate_pricing("Acme", configuration, RULES)
    pricing_state = PricingState(
        result=result, customer_name="Acme", configuration=configuration
    )

    assert is_stale(pricing_state, "Acme", configuration) is False

    changed_configuration = _configuration(users=10)
    assert is_stale(pricing_state, "Acme", changed_configuration) is True

    assert is_stale(pricing_state, "Different Customer", configuration) is True
    assert is_stale(None, "Acme", configuration) is False


def test_derive_status_label():
    context = DealContext(customer_name="Acme", deal_type=DealType.NEW_BUSINESS)

    assert derive_status_label(None) == "DRAFT"

    within_authority = _configuration(requested_discount_percent=5)
    result = calculate_pricing("Acme", within_authority, RULES)
    quote = create_quote(context, within_authority, result)
    assert derive_status_label(quote) == "PRICED"

    needs_approval = _configuration(tier="growth", requested_discount_percent=15)
    result_over = calculate_pricing("Acme", needs_approval, RULES)
    quote_over = create_quote(context, needs_approval, result_over)
    assert derive_status_label(quote_over) == "NEEDS APPROVAL"


def test_create_quote_reuses_existing_quote_domain_model():
    context = DealContext(customer_name="Acme", deal_type=DealType.NEW_BUSINESS)
    configuration = _configuration()
    result = calculate_pricing(context.customer_name, configuration, RULES)

    quote = create_quote(context, configuration, result)

    assert isinstance(quote, Quote)
    assert quote.customer_name == "Acme"
    assert quote.current_version.version_number == 1
    assert quote.current_version.source == QuoteVersionSource.INITIAL
    assert quote.current_version.pricing_snapshot.final_price == result.final_price


def _pricing_state(context: DealContext, configuration: ConfigurationInput) -> PricingState:
    result = calculate_pricing(context.customer_name, configuration, RULES)
    return PricingState(result=result, customer_name=context.customer_name, configuration=configuration)


def test_calculating_pricing_does_not_create_a_quote():
    """calculate_pricing (what "Calculate Quote" calls) only ever returns a
    QuoteResult -- there is no code path from it to a Quote/QuoteVersion."""
    configuration = _configuration()

    result = calculate_pricing("Acme", configuration, RULES)

    assert not isinstance(result, Quote)
    assert not hasattr(result, "current_version")


def test_recalculation_does_not_create_or_replace_quote_versions():
    context = DealContext(customer_name="Acme", deal_type=DealType.NEW_BUSINESS)
    configuration = _configuration()
    pricing_state = _pricing_state(context, configuration)

    committed = commit_quote(None, context, pricing_state, stale=False)
    assert len(committed.versions) == 1

    # Recalculating with a different configuration only produces a new
    # PricingState -- nothing here touches the already-committed Quote.
    revised_configuration = _configuration(users=10)
    _pricing_state(context, revised_configuration)  # simulates a recalculation

    assert len(committed.versions) == 1
    assert committed.current_version.configuration_snapshot.users == 5


def test_proceeding_to_review_creates_the_initial_quote_version():
    context = DealContext(customer_name="Acme", deal_type=DealType.NEW_BUSINESS)
    configuration = _configuration()
    pricing_state = _pricing_state(context, configuration)

    quote = commit_quote(None, context, pricing_state, stale=False)

    assert quote.current_version.version_number == 1
    assert quote.current_version.source == QuoteVersionSource.INITIAL


def test_committed_snapshot_matches_the_committing_pricing_state_exactly():
    context = DealContext(customer_name="Acme", deal_type=DealType.NEW_BUSINESS)
    configuration = _configuration(users=8, premium_support=True, requested_discount_percent=5)
    pricing_state = _pricing_state(context, configuration)

    quote = commit_quote(None, context, pricing_state, stale=False)

    committed_configuration = quote.current_version.configuration_snapshot
    assert committed_configuration.users == configuration.users
    assert committed_configuration.premium_support == configuration.premium_support
    assert committed_configuration.requested_discount_percent == configuration.requested_discount_percent

    committed_snapshot = quote.current_version.pricing_snapshot
    assert committed_snapshot.final_price == pricing_state.result.final_price
    assert committed_snapshot.rule_version == pricing_state.result.rule_version


def test_stale_pricing_cannot_be_committed_to_review():
    context = DealContext(customer_name="Acme", deal_type=DealType.NEW_BUSINESS)
    configuration = _configuration()
    pricing_state = _pricing_state(context, configuration)

    with pytest.raises(CommitError):
        commit_quote(None, context, pricing_state, stale=True)

    with pytest.raises(CommitError):
        commit_quote(None, context, None, stale=False)


def test_commit_quote_is_idempotent_for_an_unchanged_pricing_state():
    context = DealContext(customer_name="Acme", deal_type=DealType.NEW_BUSINESS)
    configuration = _configuration()
    pricing_state = _pricing_state(context, configuration)

    first = commit_quote(None, context, pricing_state, stale=False)
    second = commit_quote(first, context, pricing_state, stale=False)

    assert second is first
    assert len(second.versions) == 1


def test_commit_quote_refuses_to_silently_replace_committed_history():
    context = DealContext(customer_name="Acme", deal_type=DealType.NEW_BUSINESS)
    configuration = _configuration()
    pricing_state = _pricing_state(context, configuration)
    committed = commit_quote(None, context, pricing_state, stale=False)
    original_final_price = committed.current_version.pricing_snapshot.final_price

    revised_configuration = _configuration(tier="growth")
    revised_pricing_state = _pricing_state(context, revised_configuration)

    with pytest.raises(CommitError):
        commit_quote(committed, context, revised_pricing_state, stale=False)

    # the original committed history must remain exactly as it was
    assert len(committed.versions) == 1
    assert committed.current_version.pricing_snapshot.final_price == original_final_price
    assert committed.current_version.configuration_snapshot.tier == "core"
