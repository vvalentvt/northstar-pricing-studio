"""Phase 4C: Budget Fit recommendation -> Scenario -> QuoteVersion lifecycle.

These tests verify application/orchestration logic only. Optimizer
behavior (feasibility, ranking, diversity, capability scoring) is already
covered by tests/test_budget_fit.py; scenario-domain invariants (staleness,
promotion mapping, immutability) are already covered by
tests/test_scenarios.py and tests/test_scenario_promotion.py. Neither is
re-tested here except where Phase 4C introduces a new integration seam.
"""

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

from pricing_engine import load_rules
from budget_fit import BudgetFitConstraints, BudgetFitField

from app_state import (
    ConfigurationInput,
    DealContext,
    DealType,
    ScenarioError,
    WorkflowStep,
    add_budget_fit_recommendation,
    build_budget_fit_negotiation_context,
    budget_fit_recommendation_is_added,
    calculate_pricing,
    create_budget_fit_scenario,
    create_quote,
    run_budget_fit,
)
from quotes import PricingSnapshot, QuoteVersionSource, Scenario, ScenarioSource, ScenarioWorkspace

RULES = load_rules(ROOT / "config" / "pricing_rules.yaml")


def _configuration(**overrides) -> ConfigurationInput:
    defaults = dict(
        tier="enterprise", users=10, coverage="north_america", history_years=3,
        contract_months=24, premium_support=True, implementation_services=False,
        renewal=False, requested_discount_percent=0.0,
    )
    defaults.update(overrides)
    return ConfigurationInput(**defaults)


def _committed_quote(configuration: ConfigurationInput, customer_name: str = "Acme"):
    context = DealContext(customer_name=customer_name, deal_type=DealType.NEW_BUSINESS)
    result = calculate_pricing(customer_name, configuration, RULES)
    return create_quote(context, configuration, result)


def _advance_quote_to_next_version(quote, configuration: ConfigurationInput):
    from app_state import configuration_to_quote_request

    result = calculate_pricing(quote.customer_name, configuration, RULES)
    request = configuration_to_quote_request(quote.customer_name, configuration)
    pricing_snapshot = PricingSnapshot.from_pricing_result(result)
    return quote.add_version(
        configuration=request, pricing_snapshot=pricing_snapshot,
        source=QuoteVersionSource.MANUAL_REVISION,
    )


def _realistic_budget_fit_state(quote):
    """The $45,000 negotiation scenario used throughout Phase 4A/4B/4C:
    Enterprise/10 users/North America/3yr/Premium support baseline,
    coverage locked, minimum 5 users -- three real, distinct recommendations."""
    return run_budget_fit(
        quote, 45000.0,
        BudgetFitConstraints(locked_fields=frozenset({BudgetFitField.COVERAGE}), minimum_users=5),
        RULES,
    )


# ---------------------------------------------------------------------------
# Section 27 -- pure application logic
# ---------------------------------------------------------------------------


def test_budget_fit_recommendation_creates_budget_fit_scenario():
    quote = _committed_quote(_configuration())
    budget_fit_state = _realistic_budget_fit_state(quote)
    recommendation = budget_fit_state.result.recommendations[0]

    scenario = create_budget_fit_scenario(quote, budget_fit_state, recommendation)

    assert scenario.name == "Budget Fit — Recommended"


def test_budget_fit_scenario_reuses_configuration_snapshot():
    quote = _committed_quote(_configuration())
    budget_fit_state = _realistic_budget_fit_state(quote)
    recommendation = budget_fit_state.result.recommendations[1]

    scenario = create_budget_fit_scenario(quote, budget_fit_state, recommendation)

    assert scenario.configuration_snapshot is recommendation.configuration_snapshot


def test_budget_fit_scenario_reuses_pricing_snapshot():
    quote = _committed_quote(_configuration())
    budget_fit_state = _realistic_budget_fit_state(quote)
    recommendation = budget_fit_state.result.recommendations[2]

    scenario = create_budget_fit_scenario(quote, budget_fit_state, recommendation)

    assert scenario.pricing_snapshot is recommendation.pricing_snapshot


def test_budget_fit_scenario_uses_source_version_number():
    quote = _committed_quote(_configuration(tier="core"))
    _advance_quote_to_next_version(quote, _configuration(tier="enterprise", users=10, coverage="global", history_years=5))
    assert quote.current_version.version_number == 2
    budget_fit_state = run_budget_fit(quote, 45000.0, BudgetFitConstraints(), RULES)
    assert not budget_fit_state.result.recommendations[0].is_baseline

    scenario = create_budget_fit_scenario(
        quote, budget_fit_state, budget_fit_state.result.recommendations[0]
    )

    assert scenario.source_version_number == 2


def test_budget_fit_scenario_uses_budget_fit_source():
    quote = _committed_quote(_configuration())
    budget_fit_state = _realistic_budget_fit_state(quote)

    scenario = create_budget_fit_scenario(
        quote, budget_fit_state, budget_fit_state.result.recommendations[0]
    )

    assert scenario.source == ScenarioSource.BUDGET_FIT


def test_adding_recommendation_does_not_create_quote_version():
    quote = _committed_quote(_configuration())
    versions_before = tuple(quote.versions)
    budget_fit_state = _realistic_budget_fit_state(quote)

    add_budget_fit_recommendation(
        quote, None, budget_fit_state, budget_fit_state.result.recommendations[0]
    )

    assert tuple(quote.versions) == versions_before
    assert len(quote.versions) == 1


def test_budget_fit_scenario_can_be_added_to_new_workspace():
    quote = _committed_quote(_configuration())
    budget_fit_state = _realistic_budget_fit_state(quote)

    workspace = add_budget_fit_recommendation(
        quote, None, budget_fit_state, budget_fit_state.result.recommendations[0]
    )

    assert workspace.quote_id == quote.quote_id
    assert workspace.base_version_number == 1
    assert len(workspace.scenarios) == 1
    assert workspace.scenarios[0].source == ScenarioSource.BUDGET_FIT


def test_budget_fit_scenario_reuses_existing_same_version_workspace():
    quote = _committed_quote(_configuration())
    workspace = ScenarioWorkspace(quote_id=quote.quote_id, base_version_number=1)
    budget_fit_state = _realistic_budget_fit_state(quote)

    returned = add_budget_fit_recommendation(
        quote, workspace, budget_fit_state, budget_fit_state.result.recommendations[0]
    )

    assert returned is workspace
    assert len(workspace.scenarios) == 1


def test_manual_and_budget_fit_scenarios_can_coexist():
    from app_state import create_manual_scenario, create_scenario_workspace
    from app_state import PricingState

    quote = _committed_quote(_configuration())
    workspace = create_scenario_workspace(quote)
    manual_configuration = _configuration(tier="growth")
    manual_pricing_state = PricingState(
        result=calculate_pricing("Acme", manual_configuration, RULES),
        customer_name="Acme", configuration=manual_configuration,
    )
    create_manual_scenario("Reduced Scope", workspace, manual_pricing_state, stale=False)

    budget_fit_state = _realistic_budget_fit_state(quote)
    add_budget_fit_recommendation(
        quote, workspace, budget_fit_state, budget_fit_state.result.recommendations[0]
    )
    add_budget_fit_recommendation(
        quote, workspace, budget_fit_state, budget_fit_state.result.recommendations[1]
    )

    assert len(workspace.scenarios) == 3
    sources = {s.source for s in workspace.scenarios}
    assert sources == {ScenarioSource.MANUAL, ScenarioSource.BUDGET_FIT}


def test_duplicate_budget_fit_recommendation_is_not_added_twice():
    quote = _committed_quote(_configuration())
    budget_fit_state = _realistic_budget_fit_state(quote)
    recommendation = budget_fit_state.result.recommendations[0]
    workspace = add_budget_fit_recommendation(quote, None, budget_fit_state, recommendation)
    assert len(workspace.scenarios) == 1

    with pytest.raises(ScenarioError):
        add_budget_fit_recommendation(quote, workspace, budget_fit_state, recommendation)

    assert len(workspace.scenarios) == 1


def test_budget_fit_recommendation_is_added_detects_existing_scenario():
    quote = _committed_quote(_configuration())
    budget_fit_state = _realistic_budget_fit_state(quote)
    recommendation = budget_fit_state.result.recommendations[0]
    workspace = add_budget_fit_recommendation(quote, None, budget_fit_state, recommendation)
    scenario_again = create_budget_fit_scenario(quote, budget_fit_state, recommendation)

    assert budget_fit_recommendation_is_added(workspace, scenario_again) is True
    other_scenario = create_budget_fit_scenario(
        quote, budget_fit_state, budget_fit_state.result.recommendations[1]
    )
    assert budget_fit_recommendation_is_added(workspace, other_scenario) is False


def test_same_price_different_configuration_is_not_treated_as_duplicate():
    quote = _committed_quote(_configuration())
    budget_fit_state = _realistic_budget_fit_state(quote)
    recommendation = budget_fit_state.result.recommendations[0]
    workspace = add_budget_fit_recommendation(quote, None, budget_fit_state, recommendation)

    # A different configuration, force-priced to exactly match the
    # already-added recommendation, must still not read as a duplicate.
    decoy_configuration = recommendation.configuration_snapshot.model_copy(
        update={"users": recommendation.configuration_snapshot.users + 1}
    )
    assert decoy_configuration != recommendation.configuration_snapshot
    decoy_pricing = recommendation.pricing_snapshot.model_copy(
        update={"final_price": recommendation.pricing_snapshot.final_price}
    )
    decoy_scenario = Scenario(
        name="Decoy",
        source_version_number=budget_fit_state.source_version_number,
        configuration_snapshot=decoy_configuration,
        pricing_snapshot=decoy_pricing,
        source=ScenarioSource.BUDGET_FIT,
    )

    assert budget_fit_recommendation_is_added(workspace, decoy_scenario) is False


def test_recommendation_from_another_budget_fit_state_is_rejected():
    """Same QuoteVersion, two different Budget Fit runs (different target
    budgets) -- a recommendation genuinely evaluated under run A must not
    be attachable to run B's NegotiationContext just because both runs
    share a QuoteVersion."""
    quote = _committed_quote(_configuration(tier="enterprise", users=10, coverage="global", history_years=5))
    state_a = run_budget_fit(quote, 45000.0, BudgetFitConstraints(), RULES)
    state_b = run_budget_fit(quote, 30000.0, BudgetFitConstraints(), RULES)
    recommendation_from_a = state_a.result.recommendations[0]
    assert recommendation_from_a not in state_b.result.recommendations

    with pytest.raises(ScenarioError):
        create_budget_fit_scenario(quote, state_b, recommendation_from_a)


def test_recommendation_from_same_result_is_accepted():
    quote = _committed_quote(_configuration())
    budget_fit_state = _realistic_budget_fit_state(quote)
    recommendation = budget_fit_state.result.recommendations[0]
    assert recommendation in budget_fit_state.result.recommendations

    scenario = create_budget_fit_scenario(quote, budget_fit_state, recommendation)

    assert scenario.configuration_snapshot == recommendation.configuration_snapshot


def test_identical_rerun_differing_only_in_calculated_at_is_duplicate():
    """Two independent Budget Fit runs with identical inputs produce
    commercially identical recommendations but fresh
    PricingSnapshot.calculated_at timestamps each time -- the volatile
    timestamp alone must not defeat duplicate detection."""
    quote = _committed_quote(_configuration(tier="enterprise", users=10, coverage="global", history_years=5))
    first_state = run_budget_fit(quote, 45000.0, BudgetFitConstraints(), RULES)
    second_state = run_budget_fit(quote, 45000.0, BudgetFitConstraints(), RULES)
    first_recommendation = first_state.result.recommendations[0]
    second_recommendation = second_state.result.recommendations[0]

    # Sanity check this test is actually exercising the volatile field.
    assert first_recommendation.configuration_snapshot == second_recommendation.configuration_snapshot
    assert (
        first_recommendation.pricing_snapshot.calculated_at
        != second_recommendation.pricing_snapshot.calculated_at
    )

    workspace = add_budget_fit_recommendation(quote, None, first_state, first_recommendation)
    second_scenario = create_budget_fit_scenario(quote, second_state, second_recommendation)

    assert budget_fit_recommendation_is_added(workspace, second_scenario) is True


def test_same_price_different_approval_state_is_not_treated_as_duplicate():
    quote = _committed_quote(_configuration())
    budget_fit_state = _realistic_budget_fit_state(quote)
    recommendation = budget_fit_state.result.recommendations[0]
    workspace = add_budget_fit_recommendation(quote, None, budget_fit_state, recommendation)

    # Same configuration and final_price, but a materially different
    # commercial decision (approval state) must not read as a duplicate.
    decoy_pricing = recommendation.pricing_snapshot.model_copy(
        update={"approval_required": not recommendation.pricing_snapshot.approval_required}
    )
    decoy_scenario = Scenario(
        name="Decoy",
        source_version_number=budget_fit_state.source_version_number,
        configuration_snapshot=recommendation.configuration_snapshot,
        pricing_snapshot=decoy_pricing,
        source=ScenarioSource.BUDGET_FIT,
    )

    assert budget_fit_recommendation_is_added(workspace, decoy_scenario) is False


def test_same_price_different_pricing_composition_is_not_treated_as_duplicate():
    quote = _committed_quote(_configuration())
    budget_fit_state = _realistic_budget_fit_state(quote)
    recommendation = budget_fit_state.result.recommendations[0]
    workspace = add_budget_fit_recommendation(quote, None, budget_fit_state, recommendation)

    # Same final_price, but a different discount/subtotal composition
    # underneath it -- a genuinely different evaluated commercial decision
    # that happens to net out to the same headline number.
    original = recommendation.pricing_snapshot
    decoy_pricing = original.model_copy(
        update={
            "subtotal_before_discount": original.subtotal_before_discount + 1000.0,
            "discount_amount": original.discount_amount + 1000.0,
        }
    )
    assert decoy_pricing.final_price == original.final_price
    decoy_scenario = Scenario(
        name="Decoy",
        source_version_number=budget_fit_state.source_version_number,
        configuration_snapshot=recommendation.configuration_snapshot,
        pricing_snapshot=decoy_pricing,
        source=ScenarioSource.BUDGET_FIT,
    )

    assert budget_fit_recommendation_is_added(workspace, decoy_scenario) is False


def test_stale_budget_fit_version_cannot_create_scenario():
    quote = _committed_quote(_configuration(tier="core"))
    budget_fit_state = run_budget_fit(quote, 100000.0, BudgetFitConstraints(), RULES)
    _advance_quote_to_next_version(quote, _configuration(tier="growth"))
    assert quote.current_version.version_number == 2

    with pytest.raises(ScenarioError):
        create_budget_fit_scenario(
            quote, budget_fit_state, budget_fit_state.result.recommendations[0]
        )


def test_mismatched_workspace_base_version_rejects_budget_fit_scenario():
    quote = _committed_quote(_configuration(tier="core"))
    _advance_quote_to_next_version(quote, _configuration(tier="growth"))
    assert quote.current_version.version_number == 2
    # A workspace left over from exploration against the older version.
    stale_workspace = ScenarioWorkspace(quote_id=quote.quote_id, base_version_number=1)
    budget_fit_state = run_budget_fit(quote, 100000.0, BudgetFitConstraints(), RULES)
    assert budget_fit_state.source_version_number == 2

    with pytest.raises(ScenarioError):
        add_budget_fit_recommendation(
            quote, stale_workspace, budget_fit_state, budget_fit_state.result.recommendations[0]
        )
    assert len(stale_workspace.scenarios) == 0


def test_approval_required_budget_fit_recommendation_can_create_scenario():
    baseline = _configuration(
        tier="enterprise", users=10, coverage="global", history_years=5, requested_discount_percent=15
    )
    quote = _committed_quote(baseline)
    committed_price = quote.current_version.pricing_snapshot.final_price
    assert quote.current_version.pricing_snapshot.approval_required is True
    # A tight budget forces a real search; requested_discount_percent is
    # never searched (carried from baseline), so every feasible
    # recommendation stays approval-required too.
    budget_fit_state = run_budget_fit(quote, committed_price * 0.6, BudgetFitConstraints(), RULES)
    recommendation = budget_fit_state.result.recommendations[0]
    assert not recommendation.is_baseline

    scenario = create_budget_fit_scenario(quote, budget_fit_state, recommendation)

    assert scenario.pricing_snapshot.approval_required is True


def test_baseline_recommendation_is_not_added_as_alternative():
    configuration = _configuration(tier="core", users=5, coverage="national", history_years=1, premium_support=False)
    quote = _committed_quote(configuration)
    current_price = quote.current_version.pricing_snapshot.final_price
    budget_fit_state = run_budget_fit(quote, current_price + 5000, BudgetFitConstraints(), RULES)
    recommendation = budget_fit_state.result.recommendations[0]
    assert recommendation.is_baseline is True

    with pytest.raises(ScenarioError):
        create_budget_fit_scenario(quote, budget_fit_state, recommendation)


def test_budget_fit_scenario_negotiation_context_carries_target_budget_and_constraints():
    quote = _committed_quote(_configuration())
    constraints = BudgetFitConstraints(
        locked_fields=frozenset({BudgetFitField.COVERAGE}),
        minimum_users=5,
        required_premium_support=True,
    )
    budget_fit_state = run_budget_fit(quote, 45000.0, constraints, RULES)
    recommendation = budget_fit_state.result.recommendations[0]

    scenario = create_budget_fit_scenario(quote, budget_fit_state, recommendation)

    context = scenario.negotiation_context
    assert context is not None
    assert context.target_budget == 45000.0
    assert "Coverage" in context.required_attributes
    assert "Premium support" in context.required_attributes
    assert any("Minimum 5 users" in attribute for attribute in context.required_attributes)
    assert "Tier" in context.flexible_attributes
    assert "Coverage" not in context.flexible_attributes


def test_build_budget_fit_negotiation_context_is_deterministic():
    constraints = BudgetFitConstraints(
        locked_fields=frozenset({BudgetFitField.TIER, BudgetFitField.RENEWAL}),
        required_implementation_services=True,
    )

    first = build_budget_fit_negotiation_context(30000.0, constraints)
    second = build_budget_fit_negotiation_context(30000.0, constraints)

    assert first.required_attributes == second.required_attributes
    assert first.flexible_attributes == second.flexible_attributes


# ---------------------------------------------------------------------------
# Section 28 -- existing scenario lifecycle, driven from a Budget Fit origin
# ---------------------------------------------------------------------------


def test_budget_fit_scenario_promotion_creates_budget_fit_quote_version():
    from app_state import promote_selected_scenario

    quote = _committed_quote(_configuration())
    original_version = quote.current_version
    original_price = original_version.pricing_snapshot.final_price
    budget_fit_state = _realistic_budget_fit_state(quote)
    recommendation = budget_fit_state.result.recommendations[0]

    workspace = add_budget_fit_recommendation(quote, None, budget_fit_state, recommendation)
    other_scenario = create_budget_fit_scenario(
        quote, budget_fit_state, budget_fit_state.result.recommendations[1]
    )
    workspace.add_scenario(other_scenario)
    workspace.select_scenario(workspace.scenarios[0].scenario_id)

    new_version = promote_selected_scenario(quote, workspace)

    # Exactly one new QuoteVersion, with Budget Fit provenance.
    assert new_version.version_number == 2
    assert len(quote.versions) == 2
    assert new_version.source == QuoteVersionSource.BUDGET_FIT

    # v1 is completely unchanged.
    assert quote.versions[0] is original_version
    assert quote.versions[0].pricing_snapshot.final_price == original_price

    # The unselected second Budget Fit scenario created no QuoteVersion.
    assert quote.current_version.pricing_snapshot.final_price == recommendation.pricing_snapshot.final_price

    # No recalculation anywhere in the lifecycle. pricing_snapshot is
    # passed straight through by identity; Quote.add_version always
    # reconstructs configuration_snapshot via ConfigurationSnapshot.from_
    # request (existing domain behavior, not a Phase 4C recalculation --
    # same pattern every scenario promotion uses), so it is checked by
    # value instead.
    assert new_version.configuration_snapshot == recommendation.configuration_snapshot
    assert new_version.pricing_snapshot is recommendation.pricing_snapshot


# ---------------------------------------------------------------------------
# Section 29 -- AppTest smoke flow, driven through the real page.
# ---------------------------------------------------------------------------


def _committed_realistic_quote():
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


def _run_45k_budget_fit(at, quote):
    form_key = f"{quote.quote_id}_v{quote.current_version.version_number}"
    at.get_by_key(f"budget_fit_target_{form_key}").set_value(45000.0)
    at.get_by_key(f"budget_fit_lock_coverage_{form_key}").set_value(True)
    at.get_by_key(f"budget_fit_require_min_users_{form_key}").set_value(True)
    at.run()
    at.get_by_key(f"budget_fit_min_users_{form_key}").set_value(5)
    at.run()
    [b for b in at.button if b.label == "Find Budget Fit"][0].click().run()
    assert not at.exception
    return form_key


def test_budget_fit_scenario_smoke_flow_full_lifecycle():
    from streamlit.testing.v1 import AppTest

    context, quote = _committed_realistic_quote()
    at = AppTest.from_file(str(ROOT / "app" / "pages" / "quotes.py"))
    _open_fit_to_budget(at, context, quote)
    form_key = _run_45k_budget_fit(at, quote)

    # Add recommendation 1 -- no QuoteVersion created.
    at.get_by_key(f"budget_fit_{form_key}_add_1").click().run()
    assert not at.exception
    assert len(quote.versions) == 1
    assert "ADDED TO ALTERNATIVES" in " ".join(m.value for m in at.markdown)

    # Add recommendation 2 -- both coexist in one workspace.
    at.get_by_key(f"budget_fit_{form_key}_add_2").click().run()
    assert not at.exception
    workspace = at.session_state["scenario_workspace"]
    assert len(workspace.scenarios) == 2
    assert all(s.source == ScenarioSource.BUDGET_FIT for s in workspace.scenarios)

    # View Alternatives navigates into the EXISTING Explore Alternatives
    # screen -- no new Budget Fit comparison screen.
    [b for b in at.button if b.label == "View Alternatives"][0].click().run()
    assert not at.exception
    assert at.title[0].value == "Explore Alternatives"
    saved_text = " ".join(m.value for m in at.markdown)
    assert "Budget Fit" in saved_text

    # Compare Scenarios -- baseline + both Budget Fit scenarios visible.
    [b for b in at.button if b.label == "Compare Scenarios"][0].click().run()
    assert not at.exception
    assert at.title[0].value == "Compare Scenarios"
    price_texts = [m.value for m in at.markdown if m.value.startswith("**$")]
    assert len(price_texts) == 3  # committed baseline + 2 Budget Fit scenarios

    # Select the recommended Budget Fit scenario -- still no QuoteVersion.
    [b for b in at.button if b.label == "Select"][0].click().run()
    assert not at.exception
    assert len(quote.versions) == 1

    # Create Quote Revision -- exactly one new QuoteVersion, BUDGET_FIT provenance.
    [b for b in at.button if b.label == "Create Quote Revision"][0].click().run()
    assert not at.exception
    assert len(quote.versions) == 2
    assert quote.versions[1].source == QuoteVersionSource.BUDGET_FIT
    # v1 is untouched.
    assert quote.versions[0].configuration_snapshot.tier == "enterprise"

    # Review Pricing naturally reflects the new current version (the page
    # header's context line, styled via markdown, not st.caption).
    review_text = " ".join(m.value for m in at.markdown)
    assert "Pricing version v2" in review_text


def test_budget_fit_scenario_smoke_flow_mixed_manual_and_budget_fit():
    from streamlit.testing.v1 import AppTest
    from app_state import PricingState, create_manual_scenario, create_scenario_workspace

    context, quote = _committed_realistic_quote()
    workspace = create_scenario_workspace(quote)
    manual_configuration = _configuration(tier="growth")
    manual_pricing_state = PricingState(
        result=calculate_pricing("Acme", manual_configuration, RULES),
        customer_name="Acme", configuration=manual_configuration,
    )
    create_manual_scenario("Reduced Scope", workspace, manual_pricing_state, stale=False)

    at = AppTest.from_file(str(ROOT / "app" / "pages" / "quotes.py"))
    at.session_state["workflow_step"] = WorkflowStep.REVIEW_PRICING
    at.session_state["deal_context"] = context
    at.session_state["current_quote"] = quote
    at.session_state["scenario_workspace"] = workspace
    at.run()
    [b for b in at.button if b.label == "Fit to Budget"][0].click().run()
    form_key = _run_45k_budget_fit(at, quote)

    at.get_by_key(f"budget_fit_{form_key}_add_1").click().run()
    assert not at.exception

    updated_workspace = at.session_state["scenario_workspace"]
    assert len(updated_workspace.scenarios) == 2
    sources = {s.source for s in updated_workspace.scenarios}
    assert sources == {ScenarioSource.MANUAL, ScenarioSource.BUDGET_FIT}

    [b for b in at.button if b.label == "View Alternatives"][0].click().run()
    [b for b in at.button if b.label == "Compare Scenarios"][0].click().run()
    assert not at.exception
    price_texts = [m.value for m in at.markdown if m.value.startswith("**$")]
    assert len(price_texts) == 3  # baseline + manual + budget fit


def test_budget_fit_scenario_smoke_flow_duplicate_protection():
    from streamlit.testing.v1 import AppTest

    context, quote = _committed_realistic_quote()
    at = AppTest.from_file(str(ROOT / "app" / "pages" / "quotes.py"))
    _open_fit_to_budget(at, context, quote)
    form_key = _run_45k_budget_fit(at, quote)

    at.get_by_key(f"budget_fit_{form_key}_add_1").click().run()
    assert not at.exception
    workspace = at.session_state["scenario_workspace"]
    assert len(workspace.scenarios) == 1

    # The UI itself removes the button once added (replaced by the ADDED
    # state) -- confirm it, then confirm the application layer independently
    # refuses a repeated attempt rather than silently duplicating.
    assert not [b for b in at.button if b.key == f"budget_fit_{form_key}_add_1"]
    budget_fit_state = at.session_state["budget_fit_state"]
    recommendation = budget_fit_state.result.recommendations[0]
    with pytest.raises(ScenarioError):
        add_budget_fit_recommendation(quote, workspace, budget_fit_state, recommendation)
    assert len(workspace.scenarios) == 1


def test_budget_fit_scenario_smoke_flow_approval_required():
    from streamlit.testing.v1 import AppTest

    configuration = _configuration(
        tier="enterprise", users=10, coverage="global", history_years=5, requested_discount_percent=15,
    )
    context = DealContext(customer_name="Acme", deal_type=DealType.NEW_BUSINESS)
    quote = _committed_quote(configuration)
    committed_price = quote.current_version.pricing_snapshot.final_price
    assert quote.current_version.pricing_snapshot.approval_required is True

    at = AppTest.from_file(str(ROOT / "app" / "pages" / "quotes.py"))
    _open_fit_to_budget(at, context, quote)
    form_key = f"{quote.quote_id}_v1"
    at.get_by_key(f"budget_fit_target_{form_key}").set_value(committed_price * 0.6)
    at.run()
    [b for b in at.button if b.label == "Find Budget Fit"][0].click().run()
    assert not at.exception

    add_buttons = [b for b in at.button if b.label == "Add to Alternatives"]
    assert add_buttons
    add_buttons[0].click().run()
    assert not at.exception

    workspace = at.session_state["scenario_workspace"]
    workspace.select_scenario(workspace.scenarios[0].scenario_id)
    at.session_state["scenario_workspace"] = workspace
    [b for b in at.button if b.label == "View Alternatives"][0].click().run()
    [b for b in at.button if b.label == "Compare Scenarios"][0].click().run()
    assert not at.exception
    [b for b in at.button if b.label == "Create Quote Revision"][0].click().run()
    assert not at.exception

    assert len(quote.versions) == 2
    assert quote.versions[1].source == QuoteVersionSource.BUDGET_FIT
    assert quote.versions[1].pricing_snapshot.approval_required is True
    status_text = " ".join(m.value for m in at.markdown)
    assert "NEEDS APPROVAL" in status_text or "Approval required" in status_text


def test_budget_fit_scenario_smoke_flow_stale_version_blocks_add():
    from streamlit.testing.v1 import AppTest

    context, quote = _committed_realistic_quote()
    at = AppTest.from_file(str(ROOT / "app" / "pages" / "quotes.py"))
    _open_fit_to_budget(at, context, quote)
    form_key = _run_45k_budget_fit(at, quote)
    versions_before = len(quote.versions)

    # The quote advances to v2 through some other path entirely (e.g. a
    # manual revision elsewhere), independently of this Budget Fit run.
    _advance_quote_to_next_version(quote, _configuration(tier="core"))
    assert quote.current_version.version_number == 2

    at.session_state["current_quote"] = quote
    at.run()
    assert not at.exception

    # Stale-version attention state is styled via markdown, not st.warning.
    markdown_text = " ".join(m.value for m in at.markdown)
    assert "changed since Budget Fit was run" in markdown_text
    assert not [b for b in at.button if b.label == "Add to Alternatives"]
    assert len(quote.versions) == versions_before + 1  # only the independent advance
