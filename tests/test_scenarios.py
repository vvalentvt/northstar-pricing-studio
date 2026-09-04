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
    QuoteVersionSource,
    Scenario,
    ScenarioSource,
    ScenarioWorkspace,
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


def _pricing_snapshot(configuration: QuoteRequest) -> PricingSnapshot:
    result = calculate_quote(configuration, RULES)
    return PricingSnapshot.from_pricing_result(result)


def _scenario(
    *,
    name: str = "Scenario A",
    source_version_number: int = 2,
    source: ScenarioSource = ScenarioSource.MANUAL,
    negotiation_context: NegotiationContext | None = None,
    **configuration_overrides,
) -> Scenario:
    configuration = _configuration(**configuration_overrides)
    return Scenario(
        name=name,
        source_version_number=source_version_number,
        configuration_snapshot=ConfigurationSnapshot.from_request(configuration),
        pricing_snapshot=_pricing_snapshot(configuration),
        source=source,
        negotiation_context=negotiation_context,
    )


def _quote_at_v2() -> Quote:
    configuration_v1 = _configuration()
    quote = Quote.create(
        quote_id="Q-00124",
        customer_name="Acme",
        owner="vinnie",
        configuration=configuration_v1,
        pricing_snapshot=_pricing_snapshot(configuration_v1),
    )
    configuration_v2 = _configuration(requested_discount_percent=5)
    quote.add_version(
        configuration=configuration_v2,
        pricing_snapshot=_pricing_snapshot(configuration_v2),
        source=QuoteVersionSource.MANUAL_REVISION,
    )
    return quote


def test_create_manual_scenario():
    scenario = _scenario(name="Scenario A", source_version_number=2)

    assert scenario.scenario_id
    assert scenario.name == "Scenario A"
    assert scenario.source_version_number == 2
    assert isinstance(scenario.configuration_snapshot, ConfigurationSnapshot)
    assert isinstance(scenario.pricing_snapshot, PricingSnapshot)
    assert scenario.source == ScenarioSource.MANUAL


def test_create_budget_fit_scenario():
    scenario = _scenario(
        name="Scenario B", source_version_number=2, source=ScenarioSource.BUDGET_FIT
    )

    assert scenario.source == ScenarioSource.BUDGET_FIT
    assert scenario.source.value == "budget_fit"


def test_workspace_rejects_scenario_from_different_base_version():
    workspace = ScenarioWorkspace(quote_id="Q-00124", base_version_number=2)
    wrong_base_scenario = _scenario(source_version_number=1)

    with pytest.raises(ValueError):
        workspace.add_scenario(wrong_base_scenario)


def test_add_scenario_to_workspace():
    workspace = ScenarioWorkspace(quote_id="Q-00124", base_version_number=2)
    scenario = _scenario(name="Scenario A", source_version_number=2)

    workspace.add_scenario(scenario)

    assert len(workspace.scenarios) == 1
    assert workspace.scenarios[0] is scenario


def test_remove_scenario_does_not_change_quote_history():
    quote = _quote_at_v2()
    workspace = ScenarioWorkspace(quote_id=quote.quote_id, base_version_number=2)
    scenario = _scenario(name="Scenario C", source_version_number=2)
    workspace.add_scenario(scenario)

    versions_before = tuple(quote.versions)

    workspace.remove_scenario(scenario.scenario_id)

    assert len(workspace.scenarios) == 0
    assert tuple(quote.versions) == versions_before
    assert quote.versions[0].configuration_snapshot.tier == "core"


def test_select_scenario():
    workspace = ScenarioWorkspace(quote_id="Q-00124", base_version_number=2)
    scenario = _scenario(name="Scenario A", source_version_number=2)
    workspace.add_scenario(scenario)

    selected = workspace.select_scenario(scenario.scenario_id)

    assert selected is scenario
    assert workspace.selected_scenario_id == scenario.scenario_id
    assert workspace.selected_scenario is scenario


def test_selecting_scenario_replaces_previous_selection():
    workspace = ScenarioWorkspace(quote_id="Q-00124", base_version_number=2)
    scenario_a = _scenario(name="Scenario A", source_version_number=2)
    scenario_b = _scenario(name="Scenario B", source_version_number=2, tier="growth")
    workspace.add_scenario(scenario_a)
    workspace.add_scenario(scenario_b)

    workspace.select_scenario(scenario_a.scenario_id)
    workspace.select_scenario(scenario_b.scenario_id)

    assert workspace.selected_scenario_id == scenario_b.scenario_id
    assert workspace.selected_scenario is scenario_b


def test_select_unknown_scenario_fails():
    workspace = ScenarioWorkspace(quote_id="Q-00124", base_version_number=2)

    with pytest.raises(ValueError):
        workspace.select_scenario("does-not-exist")


def test_promote_manual_scenario_creates_new_quote_version():
    quote = _quote_at_v2()
    workspace = ScenarioWorkspace(quote_id=quote.quote_id, base_version_number=2)
    scenario = _scenario(
        name="Scenario B", source_version_number=2, source=ScenarioSource.MANUAL
    )
    workspace.add_scenario(scenario)
    workspace.select_scenario(scenario.scenario_id)

    new_version = workspace.promote_selected(quote)

    assert new_version.version_number == 3
    assert new_version.source == QuoteVersionSource.MANUAL_REVISION
    assert quote.current_version is new_version


def test_promote_budget_fit_scenario_creates_budget_fit_version():
    quote = _quote_at_v2()
    workspace = ScenarioWorkspace(quote_id=quote.quote_id, base_version_number=2)
    scenario = _scenario(
        name="Scenario C", source_version_number=2, source=ScenarioSource.BUDGET_FIT
    )
    workspace.add_scenario(scenario)
    workspace.select_scenario(scenario.scenario_id)

    new_version = workspace.promote_selected(quote)

    assert new_version.source == QuoteVersionSource.BUDGET_FIT


def test_scenario_promotion_does_not_recalculate_or_modify_pricing_snapshot():
    quote = _quote_at_v2()
    workspace = ScenarioWorkspace(quote_id=quote.quote_id, base_version_number=2)
    scenario = _scenario(name="Scenario B", source_version_number=2, tier="growth")
    workspace.add_scenario(scenario)
    workspace.select_scenario(scenario.scenario_id)

    new_version = workspace.promote_selected(quote)

    assert new_version.pricing_snapshot is scenario.pricing_snapshot
    assert new_version.pricing_snapshot.final_price == scenario.pricing_snapshot.final_price
    assert new_version.pricing_snapshot.rule_version == scenario.pricing_snapshot.rule_version
    assert new_version.configuration_snapshot.tier == "growth"


def test_promotion_does_not_create_versions_for_unselected_scenarios():
    quote = _quote_at_v2()
    workspace = ScenarioWorkspace(quote_id=quote.quote_id, base_version_number=2)
    scenario_a = _scenario(name="Scenario A", source_version_number=2)
    scenario_b = _scenario(name="Scenario B", source_version_number=2, tier="growth")
    scenario_c = _scenario(name="Scenario C", source_version_number=2, users=10)
    workspace.add_scenario(scenario_a)
    workspace.add_scenario(scenario_b)
    workspace.add_scenario(scenario_c)
    workspace.select_scenario(scenario_b.scenario_id)

    workspace.promote_selected(quote)

    assert len(quote.versions) == 3
    assert quote.current_version.configuration_snapshot.tier == "growth"


def test_promote_requires_a_selected_scenario():
    quote = _quote_at_v2()
    workspace = ScenarioWorkspace(quote_id=quote.quote_id, base_version_number=2)
    workspace.add_scenario(_scenario(source_version_number=2))

    with pytest.raises(ValueError):
        workspace.promote_selected(quote)


def test_promote_requires_matching_quote():
    quote = _quote_at_v2()
    other_quote = _quote_at_v2()
    other_quote.quote_id = "Q-99999"
    workspace = ScenarioWorkspace(quote_id="Q-00124", base_version_number=2)
    scenario = _scenario(source_version_number=2)
    workspace.add_scenario(scenario)
    workspace.select_scenario(scenario.scenario_id)

    with pytest.raises(ValueError):
        workspace.promote_selected(other_quote)


def test_cannot_promote_scenario_from_stale_base_version():
    quote = _quote_at_v2()
    workspace = ScenarioWorkspace(quote_id=quote.quote_id, base_version_number=2)
    scenario = _scenario(source_version_number=2)
    workspace.add_scenario(scenario)
    workspace.select_scenario(scenario.scenario_id)

    configuration_v3 = _configuration(users=8)
    quote.add_version(
        configuration=configuration_v3,
        pricing_snapshot=_pricing_snapshot(configuration_v3),
        source=QuoteVersionSource.MANUAL_REVISION,
    )
    assert quote.current_version.version_number == 3

    with pytest.raises(ValueError):
        workspace.promote_selected(quote)

    assert len(quote.versions) == 3


def test_removing_selected_scenario_clears_selection():
    workspace = ScenarioWorkspace(quote_id="Q-00124", base_version_number=2)
    scenario_a = _scenario(name="Scenario A", source_version_number=2)
    scenario_b = _scenario(name="Scenario B", source_version_number=2, tier="growth")
    workspace.add_scenario(scenario_a)
    workspace.add_scenario(scenario_b)
    workspace.select_scenario(scenario_a.scenario_id)

    workspace.remove_scenario(scenario_a.scenario_id)

    assert workspace.selected_scenario_id is None
    assert workspace.selected_scenario is None


def test_removing_unselected_scenario_leaves_selection_unchanged():
    workspace = ScenarioWorkspace(quote_id="Q-00124", base_version_number=2)
    scenario_a = _scenario(name="Scenario A", source_version_number=2)
    scenario_b = _scenario(name="Scenario B", source_version_number=2, tier="growth")
    workspace.add_scenario(scenario_a)
    workspace.add_scenario(scenario_b)
    workspace.select_scenario(scenario_a.scenario_id)

    workspace.remove_scenario(scenario_b.scenario_id)

    assert workspace.selected_scenario_id == scenario_a.scenario_id
    assert workspace.selected_scenario is scenario_a


def test_workspace_rejects_duplicate_scenario_id():
    workspace = ScenarioWorkspace(quote_id="Q-00124", base_version_number=2)
    scenario = _scenario(source_version_number=2)
    workspace.add_scenario(scenario)

    with pytest.raises(ValueError):
        workspace.add_scenario(scenario)

    assert len(workspace.scenarios) == 1


def test_scenario_cannot_be_mutated_after_creation():
    scenario = _scenario()

    with pytest.raises(ValidationError):
        scenario.name = "New name"


def test_workspace_scenario_collection_cannot_be_mutated_in_place():
    workspace = ScenarioWorkspace(quote_id="Q-00124", base_version_number=2)
    scenario = _scenario(source_version_number=2)
    workspace.add_scenario(scenario)

    assert isinstance(workspace.scenarios, tuple)
    with pytest.raises(AttributeError):
        workspace.scenarios.append(scenario)
    with pytest.raises(TypeError):
        workspace.scenarios[0] = scenario
