from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pricing_engine import QuoteRequest, calculate_quote, load_rules
from quotes import ConfigurationSnapshot

from budget_fit import (
    BudgetFitConstraints,
    BudgetFitField,
    BudgetFitRequest,
    find_budget_fit,
)

RULES = load_rules(ROOT / "config" / "pricing_rules.yaml")


def _configuration(**overrides) -> ConfigurationSnapshot:
    defaults = dict(
        customer_name="Acme",
        tier="enterprise",
        users=10,
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


def _baseline_price(configuration: ConfigurationSnapshot) -> float:
    return calculate_quote(QuoteRequest(**configuration.model_dump()), RULES).final_price


def test_budget_fit_rejects_non_positive_budget():
    baseline = _configuration()
    with pytest.raises(ValidationError):
        BudgetFitRequest(target_budget=0, baseline_configuration=baseline)
    with pytest.raises(ValidationError):
        BudgetFitRequest(target_budget=-100, baseline_configuration=baseline)


def test_budget_fit_uses_committed_configuration_as_baseline():
    baseline = _configuration(tier="growth", users=7)
    request = BudgetFitRequest(target_budget=1, baseline_configuration=baseline)

    assert request.baseline_configuration is baseline
    assert request.baseline_configuration.tier == "growth"
    assert request.baseline_configuration.users == 7


def test_budget_fit_derives_rule_backed_options_from_pricing_configuration():
    baseline = _configuration(tier="core")
    baseline_price = _baseline_price(baseline)
    request = BudgetFitRequest(target_budget=baseline_price * 3, baseline_configuration=baseline)

    result = find_budget_fit(request, RULES)

    seen_tiers = {rec.configuration_snapshot.tier for rec in result.recommendations}
    seen_tiers |= {
        change.candidate_value
        for rec in result.recommendations
        for change in rec.changed_fields
        if change.field is BudgetFitField.TIER
    }
    # Whatever tiers appear, every one must be a real rule-defined tier --
    # proving the search space came from rules, not a hardcoded list.
    for rec in result.recommendations:
        assert rec.configuration_snapshot.tier in RULES["tiers"]
        assert rec.configuration_snapshot.coverage in RULES["coverage"]
        assert rec.configuration_snapshot.history_years in RULES["history_years"]
        assert rec.configuration_snapshot.contract_months in RULES["contract_term"]


def test_budget_fit_uses_canonical_pricing_engine():
    baseline = _configuration(tier="core")
    baseline_price = _baseline_price(baseline)
    request = BudgetFitRequest(target_budget=baseline_price * 3, baseline_configuration=baseline)

    result = find_budget_fit(request, RULES)

    assert result.recommendations
    for rec in result.recommendations:
        recomputed = calculate_quote(
            QuoteRequest(**rec.configuration_snapshot.model_dump()), RULES
        )
        assert rec.pricing_snapshot.final_price == recomputed.final_price
        assert rec.pricing_snapshot.rule_version == recomputed.rule_version


def test_budget_fit_never_returns_over_budget_candidate():
    baseline = _configuration(tier="enterprise", users=10, coverage="global", history_years=5)
    target_budget = 45000.0
    request = BudgetFitRequest(target_budget=target_budget, baseline_configuration=baseline)

    result = find_budget_fit(request, RULES)

    assert result.recommendations
    for rec in result.recommendations:
        assert rec.pricing_snapshot.final_price <= target_budget


def test_budget_fit_preserves_locked_fields():
    baseline = _configuration(coverage="north_america")
    request = BudgetFitRequest(
        target_budget=_baseline_price(baseline) * 3,
        baseline_configuration=baseline,
        constraints=BudgetFitConstraints(locked_fields=frozenset({BudgetFitField.COVERAGE})),
    )

    result = find_budget_fit(request, RULES)

    assert result.recommendations
    for rec in result.recommendations:
        assert rec.configuration_snapshot.coverage == "north_america"
        assert not any(c.field is BudgetFitField.COVERAGE for c in rec.changed_fields)


def test_budget_fit_respects_minimum_user_constraint():
    baseline = _configuration(users=10)
    request = BudgetFitRequest(
        target_budget=_baseline_price(baseline) * 3,
        baseline_configuration=baseline,
        constraints=BudgetFitConstraints(minimum_users=6),
    )

    result = find_budget_fit(request, RULES)

    assert result.recommendations
    for rec in result.recommendations:
        assert rec.configuration_snapshot.users >= 6


def test_budget_fit_preserves_required_service():
    baseline = _configuration(premium_support=False)
    request = BudgetFitRequest(
        target_budget=_baseline_price(baseline) * 3,
        baseline_configuration=baseline,
        constraints=BudgetFitConstraints(required_premium_support=True),
    )

    result = find_budget_fit(request, RULES)

    assert result.recommendations
    for rec in result.recommendations:
        assert rec.configuration_snapshot.premium_support is True


def test_budget_fit_does_not_increase_discount_to_force_fit():
    baseline = _configuration(requested_discount_percent=0)
    # A tight budget that cannot be met by configuration changes alone
    # under the cheapest possible product combination without discount.
    cheapest_possible = calculate_quote(
        QuoteRequest(
            customer_name="Acme", tier="core", users=1, coverage="national",
            history_years=1, contract_months=36, premium_support=False,
            implementation_services=False, renewal=False, requested_discount_percent=0,
        ),
        RULES,
    ).final_price
    request = BudgetFitRequest(
        target_budget=cheapest_possible + 1, baseline_configuration=baseline
    )

    result = find_budget_fit(request, RULES)

    for rec in result.recommendations:
        assert rec.configuration_snapshot.requested_discount_percent == baseline.requested_discount_percent
        assert not any(c.field.value == "requested_discount_percent" for c in rec.changed_fields)


def test_budget_fit_can_return_approval_required_candidate():
    baseline = _configuration(requested_discount_percent=15)
    assert calculate_quote(QuoteRequest(**baseline.model_dump()), RULES).approval_required is True
    request = BudgetFitRequest(
        target_budget=_baseline_price(baseline) * 3, baseline_configuration=baseline
    )

    result = find_budget_fit(request, RULES)

    assert result.recommendations
    # Preserving the 15% discount means every candidate keeps that
    # discount, so every candidate remains approval-required -- proving
    # Budget Fit did not discard them for that reason.
    assert all(rec.pricing_snapshot.approval_required for rec in result.recommendations)


def test_budget_fit_returns_no_fit_result_for_impossible_budget():
    baseline = _configuration()
    request = BudgetFitRequest(target_budget=1000, baseline_configuration=baseline)

    result = find_budget_fit(request, RULES)

    assert result.recommendations == ()
    assert result.feasible_candidate_count == 0
    assert result.no_fit_reason is not None
    assert result.evaluated_candidate_count > 0


def test_budget_fit_returns_baseline_when_baseline_already_fits():
    baseline = _configuration(tier="core", users=5, coverage="national", history_years=1, premium_support=False)
    baseline_price = _baseline_price(baseline)
    request = BudgetFitRequest(target_budget=baseline_price + 5000, baseline_configuration=baseline)

    result = find_budget_fit(request, RULES)

    assert len(result.recommendations) == 1
    recommendation = result.recommendations[0]
    assert recommendation.is_baseline is True
    assert recommendation.change_count == 0
    assert recommendation.pricing_snapshot.final_price == baseline_price
    assert result.baseline_price == baseline_price


def test_budget_fit_baseline_shortcut_still_enforces_required_service():
    """A baseline that already fits on price but violates a hard
    requirement (e.g. the customer now requires premium support the
    committed configuration doesn't have) must not be returned unchanged
    -- hard constraints are gates everywhere, including the baseline-fits
    shortcut."""
    baseline = _configuration(tier="enterprise", premium_support=False)
    baseline_price = _baseline_price(baseline)
    request = BudgetFitRequest(
        target_budget=baseline_price + 50000,
        baseline_configuration=baseline,
        constraints=BudgetFitConstraints(required_premium_support=True),
    )

    result = find_budget_fit(request, RULES)

    assert result.recommendations
    for rec in result.recommendations:
        assert rec.configuration_snapshot.premium_support is True
        if rec.is_baseline:
            # Only acceptable if the baseline itself happened to satisfy
            # the requirement -- which it does not here.
            assert False, "baseline should not have been returned unchanged"


def test_budget_fit_ranking_is_deterministic():
    baseline = _configuration(tier="enterprise", users=10, coverage="global", history_years=5, implementation_services=True)
    request = BudgetFitRequest(target_budget=30000, baseline_configuration=baseline)

    first = find_budget_fit(request, RULES)
    second = find_budget_fit(request, RULES)

    assert len(first.recommendations) == len(second.recommendations) > 0
    for a, b in zip(first.recommendations, second.recommendations):
        assert a.configuration_snapshot.model_dump() == b.configuration_snapshot.model_dump()
        assert a.rank == b.rank


def test_budget_fit_prefers_higher_capability_score():
    baseline = _configuration(tier="enterprise", users=10, coverage="global", history_years=5, implementation_services=True)
    request = BudgetFitRequest(target_budget=30000, baseline_configuration=baseline)

    result = find_budget_fit(request, RULES)

    scores = [rec.capability_score for rec in result.recommendations]
    assert scores == sorted(scores, reverse=True)


def test_budget_fit_uses_budget_utilization_as_secondary_signal():
    baseline = _configuration(tier="enterprise", users=10, coverage="global", history_years=5)
    target_budget = 45000.0
    request = BudgetFitRequest(target_budget=target_budget, baseline_configuration=baseline)

    result = find_budget_fit(request, RULES)

    assert result.recommendations
    for rec in result.recommendations:
        assert rec.budget_utilization == pytest.approx(
            rec.pricing_snapshot.final_price / target_budget
        )
        assert rec.budget_utilization <= 1.0


def test_budget_fit_reports_changed_fields():
    baseline = _configuration(tier="enterprise", coverage="global")
    request = BudgetFitRequest(target_budget=30000, baseline_configuration=baseline)

    result = find_budget_fit(request, RULES)

    assert result.recommendations
    for rec in result.recommendations:
        changed_names = {c.field for c in rec.changed_fields}
        preserved_names = set(rec.preserved_fields)
        assert changed_names.isdisjoint(preserved_names)
        assert changed_names | preserved_names == set(BudgetFitField)
        for change in rec.changed_fields:
            assert change.baseline_value != change.candidate_value


def test_budget_fit_returns_at_most_requested_recommendation_count():
    baseline = _configuration(tier="enterprise", users=10, coverage="global", history_years=5)
    request = BudgetFitRequest(
        target_budget=45000, baseline_configuration=baseline, max_recommendations=2
    )

    result = find_budget_fit(request, RULES)

    assert len(result.recommendations) <= 2


def test_budget_fit_recommendations_are_meaningfully_distinct_when_possible():
    baseline = _configuration(tier="enterprise", users=10, coverage="global", history_years=5)
    request = BudgetFitRequest(
        target_budget=45000, baseline_configuration=baseline, max_recommendations=3
    )

    result = find_budget_fit(request, RULES)

    assert len(result.recommendations) >= 2
    change_signatures = [
        frozenset(c.field for c in rec.changed_fields) for rec in result.recommendations
    ]
    assert len(change_signatures) == len(set(change_signatures))


def test_budget_fit_does_not_modify_quote_history():
    from quotes import Quote

    baseline = _configuration(tier="core")
    baseline_result = calculate_quote(QuoteRequest(**baseline.model_dump()), RULES)
    from quotes import PricingSnapshot

    quote = Quote.create(
        quote_id="Q-1",
        customer_name="Acme",
        owner="Owner",
        configuration=QuoteRequest(**baseline.model_dump()),
        pricing_snapshot=PricingSnapshot.from_pricing_result(baseline_result),
    )
    versions_before = tuple(quote.versions)

    request = BudgetFitRequest(target_budget=baseline_result.final_price * 3, baseline_configuration=baseline)
    find_budget_fit(request, RULES)

    assert tuple(quote.versions) == versions_before
    assert len(quote.versions) == 1


def test_budget_fit_does_not_mutate_baseline_configuration():
    baseline = _configuration(tier="enterprise", users=10)
    baseline_copy = baseline.model_dump()
    request = BudgetFitRequest(target_budget=30000, baseline_configuration=baseline)

    find_budget_fit(request, RULES)

    assert baseline.model_dump() == baseline_copy


def test_budget_fit_integration_realistic_negotiation_scenario():
    """Section 24's example: a committed Enterprise quote the customer
    can no longer afford, negotiated down to a fixed budget while
    preserving coverage and a minimum seat count. Nothing here is
    hard-coded to a pre-computed dollar figure -- every expectation is
    derived from the actual pricing engine and the request itself."""
    from quotes import PricingSnapshot, Quote

    baseline = _configuration(
        tier="enterprise",
        users=10,
        coverage="north_america",
        history_years=3,
        premium_support=True,
        implementation_services=False,
        contract_months=24,
        renewal=False,
        requested_discount_percent=0,
    )
    committed_result = calculate_quote(QuoteRequest(**baseline.model_dump()), RULES)
    quote = Quote.create(
        quote_id="Q-INTEGRATION",
        customer_name="Acme",
        owner="Owner",
        configuration=QuoteRequest(**baseline.model_dump()),
        pricing_snapshot=PricingSnapshot.from_pricing_result(committed_result),
    )
    original_version = quote.current_version

    target_budget = 45000.0
    assert committed_result.final_price > target_budget

    request = BudgetFitRequest(
        target_budget=target_budget,
        baseline_configuration=baseline,
        constraints=BudgetFitConstraints(
            locked_fields=frozenset({BudgetFitField.COVERAGE}),
            minimum_users=5,
        ),
    )

    result = find_budget_fit(request, RULES)

    assert result.recommendations, "expected at least one feasible recommendation"
    for rec in result.recommendations:
        assert rec.pricing_snapshot.final_price <= target_budget
        assert rec.configuration_snapshot.coverage == "north_america"
        assert rec.configuration_snapshot.users >= 5
        assert rec.configuration_snapshot.requested_discount_percent == baseline.requested_discount_percent

    # Ranking determinism, re-run against the same request.
    repeat = find_budget_fit(request, RULES)
    assert [r.configuration_snapshot.model_dump() for r in result.recommendations] == [
        r.configuration_snapshot.model_dump() for r in repeat.recommendations
    ]

    # The original committed QuoteVersion is completely untouched.
    assert quote.current_version is original_version
    assert len(quote.versions) == 1
    assert quote.current_version.pricing_snapshot.final_price == committed_result.final_price

    print(
        f"\n[integration] evaluated={result.evaluated_candidate_count} "
        f"feasible={result.feasible_candidate_count} "
        f"recommended={len(result.recommendations)}"
    )
