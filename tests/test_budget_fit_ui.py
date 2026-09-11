"""Phase 4B application/UI orchestration tests.

These verify that the Streamlit layer collects intent correctly and hands
it to the existing Phase 4A engine unchanged -- never a second copy of
search, scoring, or ranking logic. Optimizer behavior itself (feasibility,
ranking, diversity, capability scoring, ...) is already covered by
tests/test_budget_fit.py and is deliberately not re-tested here.
"""

from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

from pricing_engine import load_rules
from budget_fit import BudgetFitConstraints, BudgetFitField, find_budget_fit

from app_state import (
    ConfigurationInput,
    DealContext,
    DealType,
    WorkflowStep,
    build_budget_fit_constraints,
    build_recommendation_views,
    budget_fit_inputs_changed,
    budget_fit_version_is_stale,
    calculate_pricing,
    create_quote,
    describe_preserved_capabilities,
    format_money,
    run_budget_fit,
)
from quotes import ConfigurationSnapshot, PricingSnapshot, QuoteVersionSource

RULES = load_rules(ROOT / "config" / "pricing_rules.yaml")


def _configuration(**overrides) -> ConfigurationInput:
    defaults = dict(
        tier="enterprise",
        users=10,
        coverage="north_america",
        history_years=3,
        contract_months=24,
        premium_support=True,
        implementation_services=False,
        renewal=False,
        requested_discount_percent=0.0,
    )
    defaults.update(overrides)
    return ConfigurationInput(**defaults)


def _committed_quote(configuration: ConfigurationInput, customer_name: str = "Acme"):
    context = DealContext(customer_name=customer_name, deal_type=DealType.NEW_BUSINESS)
    result = calculate_pricing(customer_name, configuration, RULES)
    return create_quote(context, configuration, result)


def _advance_quote_to_next_version(quote, configuration: ConfigurationInput):
    """Simulates the quote advancing independently of a Budget Fit run
    (e.g. a scenario promotion), using Quote.add_version directly -- the
    same pattern test_scenario_promotion.py already uses."""
    from app_state import configuration_to_quote_request

    result = calculate_pricing(quote.customer_name, configuration, RULES)
    request = configuration_to_quote_request(quote.customer_name, configuration)
    pricing_snapshot = PricingSnapshot.from_pricing_result(result)
    return quote.add_version(
        configuration=request,
        pricing_snapshot=pricing_snapshot,
        source=QuoteVersionSource.MANUAL_REVISION,
    )


def test_budget_fit_ui_uses_current_committed_version_as_baseline():
    quote = _committed_quote(_configuration(tier="enterprise", users=10))

    view_state = run_budget_fit(quote, 45000.0, BudgetFitConstraints(), RULES)

    assert view_state.request.baseline_configuration == quote.current_version.configuration_snapshot


def test_budget_fit_ui_does_not_use_configure_draft_state():
    """A dirty, uncommitted Configure/Scenario draft must never leak into
    Budget Fit's baseline -- only the committed QuoteVersion matters."""
    committed_configuration = _configuration(tier="core", users=5)
    quote = _committed_quote(committed_configuration)
    # A draft the user is mid-editing elsewhere, never committed.
    dirty_draft = _configuration(tier="enterprise", users=50)
    assert dirty_draft != committed_configuration

    view_state = run_budget_fit(quote, 100000.0, BudgetFitConstraints(), RULES)

    assert view_state.request.baseline_configuration.tier == "core"
    assert view_state.request.baseline_configuration.users == 5


def test_budget_fit_ui_builds_locked_field_constraints():
    constraints = build_budget_fit_constraints(
        lock_tier=True,
        lock_coverage=False,
        lock_history_years=True,
        lock_contract_months=False,
        lock_renewal=False,
        minimum_users=None,
        required_premium_support=False,
        required_implementation_services=False,
    )

    assert constraints.locked_fields == frozenset(
        {BudgetFitField.TIER, BudgetFitField.HISTORY_YEARS}
    )


def test_budget_fit_ui_builds_minimum_user_constraint():
    constraints = build_budget_fit_constraints(
        lock_tier=False,
        lock_coverage=False,
        lock_history_years=False,
        lock_contract_months=False,
        lock_renewal=False,
        minimum_users=6,
        required_premium_support=False,
        required_implementation_services=False,
    )

    assert constraints.minimum_users == 6


def test_budget_fit_ui_builds_required_service_constraints():
    constraints = build_budget_fit_constraints(
        lock_tier=False,
        lock_coverage=False,
        lock_history_years=False,
        lock_contract_months=False,
        lock_renewal=False,
        minimum_users=None,
        required_premium_support=True,
        required_implementation_services=True,
    )

    assert constraints.required_premium_support is True
    assert constraints.required_implementation_services is True


def test_budget_fit_ui_runs_existing_budget_fit_engine():
    """The UI orchestration must reach exactly the same result the Phase 4A
    engine would produce for the equivalent request -- proving no
    reimplementation, reranking, or independent filtering happened."""
    quote = _committed_quote(_configuration(tier="enterprise", users=10, coverage="global", history_years=5))
    constraints = BudgetFitConstraints(minimum_users=5)

    view_state = run_budget_fit(quote, 45000.0, constraints, RULES)

    direct_result = find_budget_fit(view_state.request, RULES)
    # PricingSnapshot.calculated_at is a live timestamp, so two independent
    # calls are never byte-for-byte identical -- compare the deterministic
    # facts that actually prove no reimplementation/reranking occurred.
    assert view_state.result.evaluated_candidate_count == direct_result.evaluated_candidate_count
    assert view_state.result.feasible_candidate_count == direct_result.feasible_candidate_count
    assert [r.configuration_snapshot for r in view_state.result.recommendations] == [
        r.configuration_snapshot for r in direct_result.recommendations
    ]
    assert [r.pricing_snapshot.final_price for r in view_state.result.recommendations] == [
        r.pricing_snapshot.final_price for r in direct_result.recommendations
    ]
    assert [r.capability_score for r in view_state.result.recommendations] == [
        r.capability_score for r in direct_result.recommendations
    ]


def test_budget_fit_ui_preserves_source_version_number():
    quote = _committed_quote(_configuration(tier="core"))
    _advance_quote_to_next_version(quote, _configuration(tier="growth"))
    assert quote.current_version.version_number == 2

    view_state = run_budget_fit(quote, 100000.0, BudgetFitConstraints(), RULES)

    assert view_state.source_version_number == 2


def test_budget_fit_ui_marks_result_stale_when_target_budget_changes():
    quote = _committed_quote(_configuration(tier="enterprise"))
    constraints = BudgetFitConstraints()
    view_state = run_budget_fit(quote, 45000.0, constraints, RULES)

    assert budget_fit_inputs_changed(view_state, 45000.0, constraints) is False
    assert budget_fit_inputs_changed(view_state, 50000.0, constraints) is True


def test_budget_fit_ui_marks_result_stale_when_constraints_change():
    quote = _committed_quote(_configuration(tier="enterprise"))
    original_constraints = BudgetFitConstraints()
    view_state = run_budget_fit(quote, 45000.0, original_constraints, RULES)

    changed_constraints = BudgetFitConstraints(minimum_users=5)
    assert budget_fit_inputs_changed(view_state, 45000.0, changed_constraints) is True
    assert budget_fit_inputs_changed(view_state, 45000.0, original_constraints) is False


def test_budget_fit_ui_result_is_not_stale_when_inputs_are_unchanged():
    quote = _committed_quote(_configuration(tier="enterprise"))
    constraints = BudgetFitConstraints(
        locked_fields=frozenset({BudgetFitField.COVERAGE}), minimum_users=5
    )
    view_state = run_budget_fit(quote, 45000.0, constraints, RULES)

    assert budget_fit_inputs_changed(view_state, 45000.0, constraints) is False


def test_budget_fit_ui_marks_result_stale_when_quote_version_advances():
    quote = _committed_quote(_configuration(tier="enterprise"))
    view_state = run_budget_fit(quote, 45000.0, BudgetFitConstraints(), RULES)
    assert budget_fit_version_is_stale(view_state, quote) is False

    _advance_quote_to_next_version(quote, _configuration(tier="core"))

    assert budget_fit_version_is_stale(view_state, quote) is True


def test_budget_fit_ui_does_not_mutate_quote_history():
    quote = _committed_quote(_configuration(tier="enterprise", users=10))
    versions_before = tuple(quote.versions)

    run_budget_fit(quote, 45000.0, BudgetFitConstraints(minimum_users=5), RULES)

    assert tuple(quote.versions) == versions_before
    assert len(quote.versions) == 1


def test_budget_fit_ui_handles_no_fit_result():
    quote = _committed_quote(_configuration(tier="enterprise", users=10, coverage="global", history_years=5))

    view_state = run_budget_fit(quote, 1000.0, BudgetFitConstraints(), RULES)

    assert view_state.result.recommendations == ()
    assert view_state.result.no_fit_reason is not None


def test_budget_fit_ui_handles_baseline_already_fits():
    configuration = _configuration(tier="core", users=5, coverage="national", history_years=1, premium_support=False)
    quote = _committed_quote(configuration)
    current_price = quote.current_version.pricing_snapshot.final_price

    view_state = run_budget_fit(quote, current_price + 5000, BudgetFitConstraints(), RULES)

    assert len(view_state.result.recommendations) == 1
    assert view_state.result.recommendations[0].is_baseline is True


def test_budget_fit_ui_recommendation_view_computes_price_delta_and_headroom():
    quote = _committed_quote(_configuration(tier="enterprise", users=10, coverage="north_america", history_years=3))
    view_state = run_budget_fit(
        quote, 45000.0, BudgetFitConstraints(locked_fields=frozenset({BudgetFitField.COVERAGE})), RULES
    )
    assert view_state.result.recommendations

    views = build_recommendation_views(view_state)

    for view in views:
        price = view.recommendation.pricing_snapshot.final_price
        assert view.price_delta_vs_current == pytest.approx(price - view_state.result.baseline_price)
        assert view.budget_headroom == pytest.approx(view_state.result.target_budget - price)
        assert view.budget_headroom >= -1e-6


def test_budget_fit_ui_describes_preserved_capabilities_from_baseline():
    baseline = ConfigurationSnapshot(
        customer_name="Acme", tier="enterprise", users=10, coverage="north_america",
        history_years=3, contract_months=24, premium_support=True,
        implementation_services=False, renewal=False, requested_discount_percent=0,
    )

    descriptions = describe_preserved_capabilities(
        (BudgetFitField.USERS, BudgetFitField.COVERAGE, BudgetFitField.PREMIUM_SUPPORT),
        baseline,
    )

    assert descriptions == ("10 users", "North America coverage", "Premium support")
    # A boolean the baseline never had is not surfaced even if "preserved".
    assert describe_preserved_capabilities((BudgetFitField.IMPLEMENTATION_SERVICES,), baseline) == ()


# ---------------------------------------------------------------------------
# Presentation / Streamlit smoke flow (AppTest) -- the realistic negotiation
# scenario from ADR-002 / Phase 4A's integration test, driven through the
# real page this time instead of calling find_budget_fit directly.
# ---------------------------------------------------------------------------


def _committed_realistic_quote():
    """Enterprise / 10 users / North America / 3yr / Premium support /
    24mo / 0% discount -- the same $94,320 baseline used throughout the
    Budget Fit engine's own integration test."""
    configuration = _configuration(
        tier="enterprise", users=10, coverage="north_america", history_years=3,
        contract_months=24, premium_support=True, implementation_services=False,
        renewal=False, requested_discount_percent=0.0,
    )
    context = DealContext(customer_name="Acme", deal_type=DealType.NEW_BUSINESS)
    quote = _committed_quote(configuration)
    return context, quote


def _open_fit_to_budget(at, context, quote):
    at.session_state["workflow_step"] = WorkflowStep.REVIEW_PRICING
    at.session_state["deal_context"] = context
    at.session_state["current_quote"] = quote
    at.run()
    assert not at.exception
    [b for b in at.button if b.label == "Fit to Budget"][0].click().run()
    assert not at.exception


def test_budget_fit_ui_smoke_flow_renders_recommendations():
    from streamlit.testing.v1 import AppTest

    context, quote = _committed_realistic_quote()
    committed_price = quote.current_version.pricing_snapshot.final_price
    versions_before = len(quote.versions)

    at = AppTest.from_file(str(ROOT / "app" / "pages" / "quotes.py"))
    _open_fit_to_budget(at, context, quote)

    form_key = f"{quote.quote_id}_v{quote.current_version.version_number}"
    at.get_by_key(f"budget_fit_target_{form_key}").set_value(45000.0)
    at.get_by_key(f"budget_fit_lock_coverage_{form_key}").set_value(True)
    at.get_by_key(f"budget_fit_require_min_users_{form_key}").set_value(True)
    at.run()
    at.get_by_key(f"budget_fit_min_users_{form_key}").set_value(5)
    at.run()
    [b for b in at.button if b.label == "Find Budget Fit"][0].click().run()
    assert not at.exception

    markdown_text = " ".join(m.value for m in at.markdown)
    caption_text = " ".join(c.value for c in at.caption)

    # Baseline quote context and source pricing version are visible.
    assert "Enterprise" in markdown_text
    assert f"Based on pricing version v{quote.current_version.version_number}" in caption_text

    # Recommendation #1 is visibly recommended; every price is within budget.
    assert ":blue[**RECOMMENDED**]" in markdown_text
    view_state = at.session_state["budget_fit_state"]
    assert view_state.result.recommendations
    for rec in view_state.result.recommendations:
        assert rec.pricing_snapshot.final_price <= 45000.0

    # Recommendations render horizontally: one distinct st.columns() column
    # per recommendation, each carrying its own price -- not one stacked
    # column with everything in it -- and rank order (leftmost = rank 1,
    # RECOMMENDED) matches BudgetFitResult's own order, unmodified.
    price_columns = [c for c in at.columns if any(m.value.startswith("### $") for m in c.markdown)]
    assert len(price_columns) == len(view_state.result.recommendations)
    expected_prices = [
        f"### {format_money(rec.pricing_snapshot.final_price)}"
        for rec in view_state.result.recommendations
    ]
    actual_prices = [
        next(m.value for m in column.markdown if m.value.startswith("### $"))
        for column in price_columns
    ]
    assert actual_prices == expected_prices
    assert any(":blue[**RECOMMENDED**]" in m.value for m in price_columns[0].markdown)

    # Capability preservation, budget headroom, changed fields, and
    # approval status all render (Changes/Preserved section headers are
    # captions, not markdown).
    assert "capability preserved" in markdown_text
    assert "under customer budget" in caption_text
    assert "Changes" in caption_text
    assert ":green[**PRICED**]" in markdown_text or ":orange[**NEEDS APPROVAL**]" in markdown_text

    # Read-only: no Select/Promote/Create Revision action exists.
    button_labels = {b.label for b in at.button}
    for forbidden in ("Select", "Use This Option", "Add to Quote", "Create Scenario",
                      "Create Quote Revision", "Promote", "Save Recommendation"):
        assert forbidden not in button_labels

    # Quote history is completely untouched by running Budget Fit.
    assert len(quote.versions) == versions_before
    assert quote.current_version.pricing_snapshot.final_price == committed_price


def test_budget_fit_ui_smoke_flow_stale_inputs_after_budget_change():
    from streamlit.testing.v1 import AppTest

    context, quote = _committed_realistic_quote()

    at = AppTest.from_file(str(ROOT / "app" / "pages" / "quotes.py"))
    _open_fit_to_budget(at, context, quote)

    form_key = f"{quote.quote_id}_v{quote.current_version.version_number}"
    at.get_by_key(f"budget_fit_target_{form_key}").set_value(45000.0)
    at.run()
    [b for b in at.button if b.label == "Find Budget Fit"][0].click().run()
    assert not at.exception
    assert any(":blue[**RECOMMENDED**]" in m.value for m in at.markdown)

    # Change the target budget WITHOUT rerunning Find Budget Fit.
    at.get_by_key(f"budget_fit_target_{form_key}").set_value(50000.0)
    at.run()
    assert not at.exception

    markdown_text = " ".join(m.value for m in at.markdown)
    caption_text = " ".join(c.value for c in at.caption)
    info_text = " ".join(i.value for i in at.info)
    # The previous recommendations must not still be represented as current.
    assert ":blue[**RECOMMENDED**]" not in markdown_text
    assert "Changes" not in caption_text
    assert "run budget fit again" in info_text.lower()


def test_budget_fit_ui_smoke_flow_no_fit():
    from streamlit.testing.v1 import AppTest

    context, quote = _committed_realistic_quote()
    versions_before = len(quote.versions)

    at = AppTest.from_file(str(ROOT / "app" / "pages" / "quotes.py"))
    _open_fit_to_budget(at, context, quote)

    form_key = f"{quote.quote_id}_v{quote.current_version.version_number}"
    at.get_by_key(f"budget_fit_target_{form_key}").set_value(1000.0)
    at.run()
    [b for b in at.button if b.label == "Find Budget Fit"][0].click().run()

    assert not at.exception
    warning_text = " ".join(w.value for w in at.warning)
    assert "No valid configuration fits this budget" in warning_text
    assert len(quote.versions) == versions_before


def test_budget_fit_ui_smoke_flow_baseline_already_fits():
    from streamlit.testing.v1 import AppTest

    context, quote = _committed_realistic_quote()
    committed_price = quote.current_version.pricing_snapshot.final_price
    versions_before = len(quote.versions)

    at = AppTest.from_file(str(ROOT / "app" / "pages" / "quotes.py"))
    _open_fit_to_budget(at, context, quote)

    form_key = f"{quote.quote_id}_v{quote.current_version.version_number}"
    at.get_by_key(f"budget_fit_target_{form_key}").set_value(committed_price + 5000.0)
    at.run()
    [b for b in at.button if b.label == "Find Budget Fit"][0].click().run()

    assert not at.exception
    info_text = " ".join(i.value for i in at.info)
    assert "already fits the customer's budget" in info_text
    markdown_text = " ".join(m.value for m in at.markdown)
    assert ":blue[**RECOMMENDED**]" not in markdown_text
    assert len(quote.versions) == versions_before
