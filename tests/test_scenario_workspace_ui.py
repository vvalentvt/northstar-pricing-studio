from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

from pricing_engine import calculate_quote, load_rules
from quotes import ScenarioSource

from app_state import (
    ConfigurationInput,
    DealContext,
    DealType,
    PricingState,
    ScenarioError,
    calculate_pricing,
    configuration_input_from_snapshot,
    configuration_to_quote_request,
    create_manual_scenario,
    create_quote,
    create_scenario_workspace,
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
    quote = create_quote(context, configuration, result)
    return context, quote


def _scenario_pricing_state(
    customer_name: str, configuration: ConfigurationInput
) -> PricingState:
    result = calculate_pricing(customer_name, configuration, RULES)
    return PricingState(result=result, customer_name=customer_name, configuration=configuration)


def test_scenario_workspace_created_from_current_quote_version():
    _, quote = _committed_quote(_configuration())

    workspace = create_scenario_workspace(quote)

    assert workspace.quote_id == quote.quote_id
    assert workspace.base_version_number == quote.current_version.version_number == 1
    assert len(workspace.scenarios) == 0


def test_scenario_draft_starts_from_committed_configuration():
    committed_configuration = _configuration(tier="growth", users=8, premium_support=True)
    _, quote = _committed_quote(committed_configuration)

    draft = configuration_input_from_snapshot(quote.current_version.configuration_snapshot)

    assert draft.tier == "growth"
    assert draft.users == 8
    assert draft.premium_support is True
    assert draft == committed_configuration


def test_manual_scenario_uses_existing_pricing_engine():
    scenario_configuration = _configuration(users=8, coverage="north_america")

    result_via_app = calculate_pricing("Acme", scenario_configuration, RULES)
    result_via_engine = calculate_quote(
        configuration_to_quote_request("Acme", scenario_configuration), RULES
    )

    assert result_via_app == result_via_engine


def test_saving_manual_scenario_creates_scenario_not_quote_version():
    _, quote = _committed_quote(_configuration())
    workspace = create_scenario_workspace(quote)
    scenario_configuration = _configuration(tier="growth", users=8)
    pricing_state = _scenario_pricing_state("Acme", scenario_configuration)

    scenario = create_manual_scenario("Reduced Scope", workspace, pricing_state, stale=False)

    assert len(quote.versions) == 1
    assert quote.current_version.configuration_snapshot.tier == "core"
    assert len(workspace.scenarios) == 1
    assert workspace.scenarios[0] is scenario
    assert scenario.source == ScenarioSource.MANUAL
    assert scenario.source_version_number == workspace.base_version_number


def test_saved_scenario_preserves_configuration_snapshot():
    _, quote = _committed_quote(_configuration())
    workspace = create_scenario_workspace(quote)
    scenario_configuration = _configuration(
        tier="growth", users=8, coverage="north_america", contract_months=24
    )
    pricing_state = _scenario_pricing_state("Acme", scenario_configuration)

    scenario = create_manual_scenario("Longer Term", workspace, pricing_state, stale=False)

    assert scenario.configuration_snapshot.tier == "growth"
    assert scenario.configuration_snapshot.users == 8
    assert scenario.configuration_snapshot.coverage == "north_america"
    assert scenario.configuration_snapshot.contract_months == 24


def test_saved_scenario_preserves_pricing_snapshot():
    _, quote = _committed_quote(_configuration())
    workspace = create_scenario_workspace(quote)
    scenario_configuration = _configuration(requested_discount_percent=5)
    pricing_state = _scenario_pricing_state("Acme", scenario_configuration)

    scenario = create_manual_scenario("Standard Support", workspace, pricing_state, stale=False)

    assert scenario.pricing_snapshot.final_price == pricing_state.result.final_price
    assert scenario.pricing_snapshot.rule_version == pricing_state.result.rule_version
    assert scenario.pricing_snapshot.discount_amount == pricing_state.result.discount_amount


def test_stale_scenario_pricing_cannot_be_saved():
    _, quote = _committed_quote(_configuration())
    workspace = create_scenario_workspace(quote)
    pricing_state = _scenario_pricing_state("Acme", _configuration())

    with pytest.raises(ScenarioError):
        create_manual_scenario("Stale Draft", workspace, pricing_state, stale=True)

    assert len(workspace.scenarios) == 0


def test_scenario_requires_name_before_save():
    _, quote = _committed_quote(_configuration())
    workspace = create_scenario_workspace(quote)
    pricing_state = _scenario_pricing_state("Acme", _configuration())

    with pytest.raises(ScenarioError):
        create_manual_scenario("", workspace, pricing_state, stale=False)

    with pytest.raises(ScenarioError):
        create_manual_scenario("   ", workspace, pricing_state, stale=False)

    with pytest.raises(ScenarioError):
        create_manual_scenario("Some Name", workspace, None, stale=False)

    assert len(workspace.scenarios) == 0


def test_approval_required_scenario_can_be_saved():
    _, quote = _committed_quote(_configuration())
    workspace = create_scenario_workspace(quote)
    scenario_configuration = _configuration(tier="growth", requested_discount_percent=15)
    pricing_state = _scenario_pricing_state("Acme", scenario_configuration)
    assert pricing_state.result.approval_required is True

    scenario = create_manual_scenario(
        "Customer Budget Option", workspace, pricing_state, stale=False
    )

    assert scenario.pricing_snapshot.approval_required is True
    assert len(workspace.scenarios) == 1


def test_removing_scenario_does_not_change_quote_history():
    _, quote = _committed_quote(_configuration())
    workspace = create_scenario_workspace(quote)
    pricing_state = _scenario_pricing_state("Acme", _configuration(users=8))
    scenario = create_manual_scenario("Extra Users", workspace, pricing_state, stale=False)
    versions_before = tuple(quote.versions)

    workspace.remove_scenario(scenario.scenario_id)

    assert tuple(quote.versions) == versions_before
    assert len(quote.versions) == 1
    assert len(workspace.scenarios) == 0


def test_new_quote_flow_clears_previous_scenario_workspace():
    """Starting a new quote must not let a prior quote's scenarios leak in.

    This is inherently a session-state concern (app_session.py, which
    imports streamlit), not a pure-function one, so it's exercised through
    AppTest -- clicking the real "+ New Quote" action on Home.
    """
    from streamlit.testing.v1 import AppTest

    _, quote = _committed_quote(_configuration())
    workspace = create_scenario_workspace(quote)
    pricing_state = _scenario_pricing_state("Acme", _configuration(users=8))
    create_manual_scenario("Leftover Scenario", workspace, pricing_state, stale=False)

    # Driven through the real entrypoint (not home.py in isolation): only
    # there does st.navigation register "pages/quotes.py" so the Home
    # button's st.switch_page call resolves instead of raising a
    # test-harness-only StreamlitPageNotFoundError.
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"))
    at.run()
    at.session_state["current_quote"] = quote
    at.session_state["scenario_workspace"] = workspace
    at.session_state["scenario_draft_pricing_state"] = pricing_state
    at.session_state["exploring_alternatives"] = True

    new_quote_button = [b for b in at.button if "New Quote" in (b.label or "")][0]
    new_quote_button.click().run()
    assert not at.exception

    assert at.session_state["current_quote"] is None
    assert at.session_state["scenario_workspace"] is None
    assert at.session_state["scenario_draft_pricing_state"] is None
    assert at.session_state["exploring_alternatives"] is False
