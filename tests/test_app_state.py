from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

from pricing_engine import calculate_quote, load_rules
from quotes import Quote, QuoteVersionSource

from app_state import (
    ConfigurationInput,
    DealContext,
    DealType,
    PricingState,
    calculate_pricing,
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
    assert derive_status_label(None) == "DRAFT"

    within_authority = _configuration(requested_discount_percent=5)
    result = calculate_pricing("Acme", within_authority, RULES)
    pricing_state = PricingState(
        result=result, customer_name="Acme", configuration=within_authority
    )
    assert derive_status_label(pricing_state) == "PRICED"

    needs_approval = _configuration(tier="growth", requested_discount_percent=15)
    result_over = calculate_pricing("Acme", needs_approval, RULES)
    pricing_state_over = PricingState(
        result=result_over, customer_name="Acme", configuration=needs_approval
    )
    assert derive_status_label(pricing_state_over) == "NEEDS APPROVAL"


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


def test_recalculation_reuses_existing_quote_id():
    context = DealContext(customer_name="Acme", deal_type=DealType.NEW_BUSINESS)
    configuration = _configuration()
    result = calculate_pricing(context.customer_name, configuration, RULES)

    first_quote = create_quote(context, configuration, result)

    revised_configuration = _configuration(users=8)
    revised_result = calculate_pricing(context.customer_name, revised_configuration, RULES)
    second_quote = create_quote(
        context, revised_configuration, revised_result, existing_quote_id=first_quote.quote_id
    )

    assert second_quote.quote_id == first_quote.quote_id
    assert second_quote.current_version.configuration_snapshot.users == 8
