from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pricing_engine import QuoteRequest, calculate_quote, load_rules
from quotes import (
    ConfigurationSnapshot,
    NegotiationContext,
    PricingSnapshot,
    Quote,
    QuoteVersion,
    QuoteVersionSource,
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


def _snapshot(configuration: QuoteRequest) -> PricingSnapshot:
    result = calculate_quote(configuration, RULES)
    return PricingSnapshot.from_pricing_result(result)


def test_create_quote_with_initial_version():
    configuration = _configuration()
    snapshot = _snapshot(configuration)

    quote = Quote.create(
        quote_id="Q-00124",
        customer_name="Acme",
        owner="vinnie",
        configuration=configuration,
        pricing_snapshot=snapshot,
    )

    assert quote.quote_id == "Q-00124"
    assert quote.current_version.version_number == 1
    assert quote.current_version.source == QuoteVersionSource.INITIAL
    assert quote.current_version is quote.versions[0]


def test_add_revision_creates_next_version():
    configuration = _configuration()
    snapshot = _snapshot(configuration)
    quote = Quote.create(
        quote_id="Q-00124",
        customer_name="Acme",
        owner="vinnie",
        configuration=configuration,
        pricing_snapshot=snapshot,
    )

    revised_configuration = _configuration(requested_discount_percent=5)
    revised_snapshot = _snapshot(revised_configuration)

    new_version = quote.add_version(
        configuration=revised_configuration,
        pricing_snapshot=revised_snapshot,
        source=QuoteVersionSource.MANUAL_REVISION,
    )

    assert new_version.version_number == 2
    assert quote.current_version is new_version
    assert len(quote.versions) == 2


def test_previous_versions_remain_unchanged():
    configuration_v1 = _configuration()
    snapshot_v1 = _snapshot(configuration_v1)
    quote = Quote.create(
        quote_id="Q-00124",
        customer_name="Acme",
        owner="vinnie",
        configuration=configuration_v1,
        pricing_snapshot=snapshot_v1,
    )
    original_version = quote.current_version

    configuration_v2 = _configuration(tier="growth", requested_discount_percent=10)
    snapshot_v2 = _snapshot(configuration_v2)
    quote.add_version(
        configuration=configuration_v2,
        pricing_snapshot=snapshot_v2,
        source=QuoteVersionSource.MANUAL_REVISION,
    )

    v1 = quote.versions[0]
    assert v1 is original_version
    assert v1.configuration_snapshot.tier == "core"
    assert v1.pricing_snapshot.final_price == snapshot_v1.final_price

    with pytest.raises(ValidationError):
        v1.version_number = 99


def test_pricing_snapshot_preserves_rule_version():
    configuration = _configuration()
    result = calculate_quote(configuration, RULES)
    snapshot = PricingSnapshot.from_pricing_result(result)

    assert snapshot.rule_version == RULES["version"]
    assert snapshot.rule_version == result.rule_version


def test_quote_version_can_capture_negotiation_context():
    configuration = _configuration()
    snapshot = _snapshot(configuration)
    quote = Quote.create(
        quote_id="Q-00124",
        customer_name="Acme",
        owner="vinnie",
        configuration=configuration,
        pricing_snapshot=snapshot,
    )

    context = NegotiationContext(
        target_budget=45000,
        required_attributes=["Growth package", "North America", "At least 24 months history"],
        flexible_attributes=["User count", "Support level", "Contract term"],
    )
    revised_configuration = _configuration(requested_discount_percent=8)
    revised_snapshot = _snapshot(revised_configuration)

    quote.add_version(
        configuration=revised_configuration,
        pricing_snapshot=revised_snapshot,
        source=QuoteVersionSource.MANUAL_REVISION,
        negotiation_context=context,
    )

    saved_context = quote.current_version.negotiation_context
    assert saved_context.target_budget == 45000
    assert "Growth package" in saved_context.required_attributes
    assert "User count" in saved_context.flexible_attributes


def test_budget_fit_version_source_can_be_recorded():
    configuration = _configuration()
    snapshot = _snapshot(configuration)
    quote = Quote.create(
        quote_id="Q-00124",
        customer_name="Acme",
        owner="vinnie",
        configuration=configuration,
        pricing_snapshot=snapshot,
    )

    budget_fit_configuration = _configuration(tier="core", users=3)
    budget_fit_snapshot = _snapshot(budget_fit_configuration)

    version = quote.add_version(
        configuration=budget_fit_configuration,
        pricing_snapshot=budget_fit_snapshot,
        source=QuoteVersionSource.BUDGET_FIT,
    )

    assert version.source == QuoteVersionSource.BUDGET_FIT
    assert version.source.value == "budget_fit"


def test_stored_configuration_cannot_be_mutated():
    configuration = _configuration()
    snapshot = _snapshot(configuration)
    quote = Quote.create(
        quote_id="Q-00124",
        customer_name="Acme",
        owner="vinnie",
        configuration=configuration,
        pricing_snapshot=snapshot,
    )

    stored = quote.current_version.configuration_snapshot
    assert isinstance(stored, ConfigurationSnapshot)
    with pytest.raises(ValidationError):
        stored.tier = "growth"


def test_external_request_mutation_does_not_change_stored_version():
    configuration = _configuration()
    snapshot = _snapshot(configuration)
    quote = Quote.create(
        quote_id="Q-00124",
        customer_name="Acme",
        owner="vinnie",
        configuration=configuration,
        pricing_snapshot=snapshot,
    )

    configuration.tier = "growth"
    configuration.users = 999

    stored = quote.current_version.configuration_snapshot
    assert stored.tier == "core"
    assert stored.users == 5


def test_version_collection_cannot_be_mutated_in_place():
    configuration = _configuration()
    snapshot = _snapshot(configuration)
    quote = Quote.create(
        quote_id="Q-00124",
        customer_name="Acme",
        owner="vinnie",
        configuration=configuration,
        pricing_snapshot=snapshot,
    )

    assert isinstance(quote.versions, tuple)
    with pytest.raises(AttributeError):
        quote.versions.append(quote.current_version)
    with pytest.raises(AttributeError):
        quote.versions.clear()
    with pytest.raises(TypeError):
        quote.versions[0] = quote.current_version

    # confirmed history is untouched by the failed mutation attempts
    assert len(quote.versions) == 1


def test_quote_requires_at_least_one_version():
    configuration = _configuration()
    snapshot = _snapshot(configuration)
    version = QuoteVersion(
        version_number=1,
        configuration_snapshot=ConfigurationSnapshot.from_request(configuration),
        pricing_snapshot=snapshot,
        source=QuoteVersionSource.INITIAL,
    )

    with pytest.raises(ValidationError):
        Quote(quote_id="Q-00124", customer_name="Acme", owner="vinnie", versions=())

    # sanity check: a non-empty, sequential history is accepted
    quote = Quote(
        quote_id="Q-00124", customer_name="Acme", owner="vinnie", versions=(version,)
    )
    assert quote.current_version.version_number == 1


def test_quote_rejects_non_sequential_version_history():
    configuration = _configuration()
    snapshot = _snapshot(configuration)
    out_of_order_version = QuoteVersion(
        version_number=5,
        configuration_snapshot=ConfigurationSnapshot.from_request(configuration),
        pricing_snapshot=snapshot,
        source=QuoteVersionSource.INITIAL,
    )

    with pytest.raises(ValidationError):
        Quote(
            quote_id="Q-00124",
            customer_name="Acme",
            owner="vinnie",
            versions=(out_of_order_version,),
        )


def test_pricing_snapshot_adjustments_are_immutable():
    configuration = _configuration(users=20)
    snapshot = _snapshot(configuration)

    assert isinstance(snapshot.adjustments, tuple)
    assert len(snapshot.adjustments) > 0
    with pytest.raises(ValidationError):
        snapshot.adjustments[0].amount = 0
    with pytest.raises(AttributeError):
        snapshot.adjustments.append(snapshot.adjustments[0])


def test_negotiation_context_attributes_are_immutable():
    context = NegotiationContext(
        target_budget=45000,
        required_attributes=["Growth package"],
        flexible_attributes=["User count"],
    )

    assert isinstance(context.required_attributes, tuple)
    assert isinstance(context.flexible_attributes, tuple)
    with pytest.raises(AttributeError):
        context.required_attributes.append("New requirement")
    with pytest.raises(ValidationError):
        context.required_attributes = ("Different requirement",)


def test_pricing_snapshot_preserves_self_service_threshold():
    configuration = _configuration()
    snapshot = _snapshot(configuration)

    assert snapshot.self_service_threshold_percent == RULES["discount_policy"]["max_self_service_percent"]


def test_pricing_snapshot_preserves_max_allowed_discount_threshold():
    configuration = _configuration()
    snapshot = _snapshot(configuration)

    assert snapshot.max_allowed_discount_percent == RULES["discount_policy"]["max_allowed_percent"]


def test_pricing_snapshot_policy_thresholds_are_immutable():
    configuration = _configuration()
    snapshot = _snapshot(configuration)

    with pytest.raises(ValidationError):
        snapshot.self_service_threshold_percent = 0
    with pytest.raises(ValidationError):
        snapshot.max_allowed_discount_percent = 0
