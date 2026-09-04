from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

from pricing_engine import load_rules
from quotes import PricingSnapshot, QuoteVersionSource

from app_state import (
    ConfigurationInput,
    DealContext,
    DealType,
    PricingState,
    ScenarioError,
    build_review_pricing,
    calculate_pricing,
    configuration_to_quote_request,
    create_manual_scenario,
    create_quote,
    create_scenario_workspace,
    promote_selected_scenario,
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


def _committed_quote(configuration: ConfigurationInput, customer_name: str = "Acme"):
    context = DealContext(customer_name=customer_name, deal_type=DealType.NEW_BUSINESS)
    result = calculate_pricing(customer_name, configuration, RULES)
    return create_quote(context, configuration, result)


def _saved_scenario(quote, workspace, name: str, configuration: ConfigurationInput):
    result = calculate_pricing(quote.customer_name, configuration, RULES)
    pricing_state = PricingState(
        result=result, customer_name=quote.customer_name, configuration=configuration
    )
    return create_manual_scenario(name, workspace, pricing_state, stale=False)


def _advance_quote_to_next_version(quote, configuration: ConfigurationInput):
    """Simulates advancing the quote independently of this workspace, using
    the existing Quote.add_version domain method directly."""
    result = calculate_pricing(quote.customer_name, configuration, RULES)
    request = configuration_to_quote_request(quote.customer_name, configuration)
    pricing_snapshot = PricingSnapshot.from_pricing_result(result)
    return quote.add_version(
        configuration=request,
        pricing_snapshot=pricing_snapshot,
        source=QuoteVersionSource.MANUAL_REVISION,
    )


def test_selecting_scenario_does_not_change_quote_history():
    quote = _committed_quote(_configuration())
    workspace = create_scenario_workspace(quote)
    scenario = _saved_scenario(quote, workspace, "Reduced Scope", _configuration(tier="growth"))
    versions_before = tuple(quote.versions)

    workspace.select_scenario(scenario.scenario_id)

    assert tuple(quote.versions) == versions_before
    assert len(quote.versions) == 1
    assert workspace.selected_scenario_id == scenario.scenario_id


def test_selecting_second_scenario_replaces_first_selection():
    quote = _committed_quote(_configuration())
    workspace = create_scenario_workspace(quote)
    scenario_a = _saved_scenario(quote, workspace, "Reduced Scope", _configuration(tier="growth"))
    scenario_b = _saved_scenario(quote, workspace, "Increased Scope", _configuration(users=20))

    workspace.select_scenario(scenario_a.scenario_id)
    workspace.select_scenario(scenario_b.scenario_id)

    assert workspace.selected_scenario_id == scenario_b.scenario_id
    assert workspace.selected_scenario is scenario_b
    assert len(quote.versions) == 1


def test_selected_scenario_is_exposed_for_confirmation():
    quote = _committed_quote(_configuration())
    workspace = create_scenario_workspace(quote)
    scenario = _saved_scenario(quote, workspace, "Reduced Scope", _configuration(tier="growth"))

    workspace.select_scenario(scenario.scenario_id)

    assert workspace.selected_scenario is scenario
    assert workspace.selected_scenario.pricing_snapshot.final_price == scenario.pricing_snapshot.final_price


def test_promoting_selected_scenario_creates_next_quote_version():
    quote = _committed_quote(_configuration())
    workspace = create_scenario_workspace(quote)
    scenario = _saved_scenario(quote, workspace, "Reduced Scope", _configuration(tier="growth"))
    workspace.select_scenario(scenario.scenario_id)

    new_version = promote_selected_scenario(quote, workspace)

    assert new_version.version_number == 2
    assert len(quote.versions) == 2
    assert quote.current_version is new_version


def test_promotion_preserves_original_quote_version():
    original_configuration = _configuration(tier="core", users=5)
    quote = _committed_quote(original_configuration)
    original_price = quote.current_version.pricing_snapshot.final_price
    workspace = create_scenario_workspace(quote)
    scenario = _saved_scenario(quote, workspace, "Reduced Scope", _configuration(tier="growth"))
    workspace.select_scenario(scenario.scenario_id)

    promote_selected_scenario(quote, workspace)

    v1 = quote.versions[0]
    assert v1.version_number == 1
    assert v1.configuration_snapshot.tier == "core"
    assert v1.pricing_snapshot.final_price == original_price


def test_promotion_uses_selected_scenario_configuration_snapshot():
    quote = _committed_quote(_configuration(tier="core"))
    workspace = create_scenario_workspace(quote)
    scenario = _saved_scenario(
        quote, workspace, "Reduced Scope", _configuration(tier="growth", users=8)
    )
    workspace.select_scenario(scenario.scenario_id)

    new_version = promote_selected_scenario(quote, workspace)

    assert new_version.configuration_snapshot.tier == "growth"
    assert new_version.configuration_snapshot.users == 8
    assert new_version.configuration_snapshot == scenario.configuration_snapshot


def test_promotion_uses_selected_scenario_pricing_snapshot():
    quote = _committed_quote(_configuration())
    workspace = create_scenario_workspace(quote)
    scenario = _saved_scenario(quote, workspace, "Reduced Scope", _configuration(tier="growth"))
    workspace.select_scenario(scenario.scenario_id)

    new_version = promote_selected_scenario(quote, workspace)

    assert new_version.pricing_snapshot is scenario.pricing_snapshot
    assert new_version.pricing_snapshot.final_price == scenario.pricing_snapshot.final_price


def test_unselected_scenarios_do_not_create_quote_versions():
    quote = _committed_quote(_configuration())
    workspace = create_scenario_workspace(quote)
    scenario_a = _saved_scenario(quote, workspace, "Reduced Scope", _configuration(tier="growth"))
    _saved_scenario(quote, workspace, "Increased Scope", _configuration(users=20))
    workspace.select_scenario(scenario_a.scenario_id)

    promote_selected_scenario(quote, workspace)

    assert len(quote.versions) == 2
    assert quote.current_version.configuration_snapshot.tier == "growth"
    assert quote.current_version.configuration_snapshot.users == 5


def test_approval_required_scenario_can_be_promoted():
    quote = _committed_quote(_configuration())
    workspace = create_scenario_workspace(quote)
    scenario = _saved_scenario(
        quote, workspace, "Big Discount", _configuration(tier="growth", requested_discount_percent=15)
    )
    assert scenario.pricing_snapshot.approval_required is True
    workspace.select_scenario(scenario.scenario_id)

    new_version = promote_selected_scenario(quote, workspace)

    assert new_version.pricing_snapshot.approval_required is True
    assert quote.current_version.pricing_snapshot.approval_required is True


def test_stale_workspace_promotion_is_rejected():
    quote = _committed_quote(_configuration())
    workspace = create_scenario_workspace(quote)
    scenario = _saved_scenario(quote, workspace, "Reduced Scope", _configuration(tier="growth"))
    workspace.select_scenario(scenario.scenario_id)

    # The quote advances independently of this workspace (e.g. via some
    # other path) -- the workspace is now stale relative to current_version.
    _advance_quote_to_next_version(quote, _configuration(tier="enterprise", users=20))
    assert quote.current_version.version_number == 2

    with pytest.raises(ScenarioError):
        promote_selected_scenario(quote, workspace)

    assert len(quote.versions) == 2
    assert quote.current_version.configuration_snapshot.tier == "enterprise"


def test_review_pricing_uses_new_current_version_after_promotion():
    quote = _committed_quote(_configuration(tier="core"))
    workspace = create_scenario_workspace(quote)
    scenario = _saved_scenario(quote, workspace, "Reduced Scope", _configuration(tier="growth"))
    workspace.select_scenario(scenario.scenario_id)

    promote_selected_scenario(quote, workspace)

    review = build_review_pricing(quote)
    assert review.version_number == 2
    assert review.configuration.tier == "growth"
    assert review.final_price == scenario.pricing_snapshot.final_price


def test_new_exploration_after_promotion_is_based_on_new_version():
    quote = _committed_quote(_configuration(tier="core"))
    workspace = create_scenario_workspace(quote)
    scenario = _saved_scenario(quote, workspace, "Reduced Scope", _configuration(tier="growth"))
    workspace.select_scenario(scenario.scenario_id)

    promote_selected_scenario(quote, workspace)

    new_workspace = create_scenario_workspace(quote)
    assert new_workspace.base_version_number == 2
    assert len(new_workspace.scenarios) == 0


def test_successful_promotion_clears_exploration_session_state():
    """Clearing exploration state after promotion is a session-state
    concern (app_session.py imports streamlit), not a pure-function one,
    so it's exercised through AppTest against quotes.py directly (the
    robust pattern established in prior phases for this codebase)."""
    from streamlit.testing.v1 import AppTest
    from app_state import DealType, WorkflowStep

    quote = _committed_quote(_configuration(tier="core"))
    workspace = create_scenario_workspace(quote)
    scenario = _saved_scenario(quote, workspace, "Reduced Scope", _configuration(tier="growth"))
    workspace.select_scenario(scenario.scenario_id)
    context = DealContext(customer_name=quote.customer_name, deal_type=DealType.NEW_BUSINESS)

    at = AppTest.from_file(str(ROOT / "app" / "pages" / "quotes.py"))
    at.session_state["workflow_step"] = WorkflowStep.REVIEW_PRICING
    at.session_state["deal_context"] = context
    at.session_state["current_quote"] = quote
    at.session_state["scenario_workspace"] = workspace
    at.session_state["exploring_alternatives"] = True
    at.session_state["comparing_scenarios"] = True
    at.run()
    assert not at.exception

    create_button = [b for b in at.button if b.label == "Create Quote Revision"][0]
    create_button.click().run()
    assert not at.exception

    assert len(quote.versions) == 2
    assert at.session_state["scenario_workspace"] is None
    assert at.session_state["scenario_draft_pricing_state"] is None
    assert at.session_state["exploring_alternatives"] is False
    assert at.session_state["comparing_scenarios"] is False
    assert at.session_state["current_quote"] is quote
    assert at.session_state["current_quote"].current_version.version_number == 2
