import copy
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
    build_review_pricing,
    calculate_pricing,
    commit_quote,
    configuration_to_quote_request,
    create_quote,
    derive_status_label,
    format_money,
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


def test_format_money_formats_consistently():
    assert format_money(45000) == "$45,000"
    assert format_money(3750, signed=True) == "+$3,750"
    assert format_money(-2630, signed=True) == "-$2,630"
    assert format_money(0, signed=True) == "$0"


def test_review_model_reads_committed_quote_version():
    context = DealContext(customer_name="Acme", deal_type=DealType.NEW_BUSINESS)
    configuration = _configuration(users=8, premium_support=True)
    result = calculate_pricing(context.customer_name, configuration, RULES)
    quote = create_quote(context, configuration, result)

    review = build_review_pricing(quote)

    assert review.quote_id == quote.quote_id
    assert review.version_number == quote.current_version.version_number
    assert review.configuration is quote.current_version.configuration_snapshot
    assert review.adjustments is quote.current_version.pricing_snapshot.adjustments
    assert review.final_price == quote.current_version.pricing_snapshot.final_price
    assert review.rule_version == quote.current_version.pricing_snapshot.rule_version


def test_review_configuration_does_not_use_live_draft():
    context = DealContext(customer_name="Acme", deal_type=DealType.NEW_BUSINESS)
    committed_configuration = _configuration(tier="core", users=5)
    result = calculate_pricing(context.customer_name, committed_configuration, RULES)
    quote = create_quote(context, committed_configuration, result)

    # A draft the user is experimenting with back on Configure -- never
    # passed to build_review_pricing, which only ever takes `quote`.
    draft_configuration = _configuration(tier="enterprise", users=50)
    assert draft_configuration != committed_configuration

    review = build_review_pricing(quote)

    assert review.configuration.tier == "core"
    assert review.configuration.users == 5


def test_review_status_within_authority():
    context = DealContext(customer_name="Acme", deal_type=DealType.NEW_BUSINESS)
    configuration = _configuration(requested_discount_percent=5)
    result = calculate_pricing(context.customer_name, configuration, RULES)
    quote = create_quote(context, configuration, result)

    review = build_review_pricing(quote)

    assert review.approval_required is False
    assert review.status_label == "PRICED"
    assert review.self_service_threshold_percent == RULES["discount_policy"]["max_self_service_percent"]


def test_review_status_requires_approval():
    context = DealContext(customer_name="Acme", deal_type=DealType.NEW_BUSINESS)
    configuration = _configuration(tier="growth", requested_discount_percent=15)
    result = calculate_pricing(context.customer_name, configuration, RULES)
    quote = create_quote(context, configuration, result)

    review = build_review_pricing(quote)

    assert review.approval_required is True
    assert review.status_label == "NEEDS APPROVAL"
    assert review.approval_reason == result.approval_reason
    assert review.approval_reason is not None


def test_price_bridge_uses_snapshot_values_without_recalculation():
    context = DealContext(customer_name="Acme", deal_type=DealType.NEW_BUSINESS)
    configuration = _configuration(users=8, coverage="north_america", history_years=3)
    result = calculate_pricing(context.customer_name, configuration, RULES)
    quote = create_quote(context, configuration, result)

    review = build_review_pricing(quote)
    snapshot = quote.current_version.pricing_snapshot

    assert review.base_price == snapshot.base_price == result.list_price
    assert review.subtotal_before_discount == snapshot.subtotal_before_discount == result.subtotal_before_discount
    assert review.discount_amount == snapshot.discount_amount == result.discount_amount
    assert review.final_price == snapshot.final_price == result.final_price
    assert [a.amount for a in review.adjustments] == [a.amount for a in result.adjustments]
    # the base price plus every adjustment reconciles to the recorded subtotal --
    # proving these are the engine's own numbers, not UI-side arithmetic
    assert review.base_price + sum(a.amount for a in review.adjustments) == pytest.approx(
        review.subtotal_before_discount
    )


def test_proposal_is_blocked_when_approval_required():
    context = DealContext(customer_name="Acme", deal_type=DealType.NEW_BUSINESS)
    configuration = _configuration(tier="growth", requested_discount_percent=15)
    result = calculate_pricing(context.customer_name, configuration, RULES)
    quote = create_quote(context, configuration, result)

    review = build_review_pricing(quote)

    assert review.proposal_available is False


def test_proposal_is_available_when_within_authority():
    context = DealContext(customer_name="Acme", deal_type=DealType.NEW_BUSINESS)
    configuration = _configuration(requested_discount_percent=5)
    result = calculate_pricing(context.customer_name, configuration, RULES)
    quote = create_quote(context, configuration, result)

    review = build_review_pricing(quote)

    assert review.proposal_available is True


def test_build_review_pricing_reads_thresholds_from_the_historical_snapshot():
    """Review Pricing must derive approval-policy context solely from the
    committed QuoteVersion -- build_review_pricing takes no `rules`
    argument at all, so there is no way for it to consult current policy."""
    context = DealContext(customer_name="Acme", deal_type=DealType.NEW_BUSINESS)
    configuration = _configuration(requested_discount_percent=5)
    result = calculate_pricing(context.customer_name, configuration, RULES)
    quote = create_quote(context, configuration, result)

    review = build_review_pricing(quote)

    snapshot = quote.current_version.pricing_snapshot
    assert review.self_service_threshold_percent == snapshot.self_service_threshold_percent
    assert review.max_allowed_discount_percent == snapshot.max_allowed_discount_percent


def test_review_pricing_thresholds_are_immune_to_later_rule_changes():
    context = DealContext(customer_name="Acme", deal_type=DealType.NEW_BUSINESS)
    configuration = _configuration(requested_discount_percent=5)
    result = calculate_pricing(context.customer_name, configuration, RULES)
    quote = create_quote(context, configuration, result)

    review_before = build_review_pricing(quote)

    # Simulate the active pricing policy changing after this quote was
    # committed -- a newer rule version with tighter discount authority.
    changed_rules = copy.deepcopy(RULES)
    changed_rules["version"] = "0.2.0"
    changed_rules["discount_policy"]["max_self_service_percent"] = 2
    changed_rules["discount_policy"]["max_allowed_percent"] = 20

    # Recalculating a brand new quote under the changed policy shows the
    # new thresholds are real and different...
    new_result = calculate_pricing(context.customer_name, configuration, changed_rules)
    assert new_result.self_service_threshold_percent == 2
    assert new_result.max_allowed_discount_percent == 20

    # ...but the already-committed quote's review is completely unaffected,
    # because build_review_pricing has no `rules` parameter to receive them.
    review_after = build_review_pricing(quote)
    assert review_after.self_service_threshold_percent == review_before.self_service_threshold_percent
    assert review_after.max_allowed_discount_percent == review_before.max_allowed_discount_percent
    assert review_after.rule_version == review_before.rule_version == RULES["version"]
