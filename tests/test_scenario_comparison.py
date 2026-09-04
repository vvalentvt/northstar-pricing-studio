import inspect
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

from pricing_engine import load_rules

from app_state import (
    ConfigurationInput,
    DealContext,
    DealType,
    PricingState,
    build_scenario_comparison,
    calculate_pricing,
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
    return create_quote(context, configuration, result)


def _saved_scenario(quote, workspace, name: str, configuration: ConfigurationInput):
    result = calculate_pricing(quote.customer_name, configuration, RULES)
    pricing_state = PricingState(
        result=result, customer_name=quote.customer_name, configuration=configuration
    )
    return create_manual_scenario(name, workspace, pricing_state, stale=False)


def test_comparison_uses_committed_quote_as_baseline():
    quote = _committed_quote(_configuration(tier="enterprise", users=5))
    workspace = create_scenario_workspace(quote)

    comparison = build_scenario_comparison(quote, workspace.scenarios)

    assert len(comparison.options) == 1
    baseline = comparison.options[0]
    assert baseline.is_baseline is True
    assert baseline.name == "Committed Quote"
    assert baseline.final_price == quote.current_version.pricing_snapshot.final_price
    assert baseline.configuration is quote.current_version.configuration_snapshot


def test_comparison_uses_saved_scenario_snapshots():
    quote = _committed_quote(_configuration(tier="enterprise"))
    workspace = create_scenario_workspace(quote)
    scenario = _saved_scenario(quote, workspace, "Reduced Scope", _configuration(tier="growth"))

    comparison = build_scenario_comparison(quote, workspace.scenarios)

    assert len(comparison.options) == 2
    scenario_option = comparison.options[1]
    assert scenario_option.is_baseline is False
    assert scenario_option.id == scenario.scenario_id
    assert scenario_option.name == "Reduced Scope"
    assert scenario_option.final_price == scenario.pricing_snapshot.final_price
    assert scenario_option.configuration is scenario.configuration_snapshot


def test_comparison_does_not_use_scenario_draft_state():
    """Comparison only ever takes `scenarios` (saved, immutable Scenario
    objects from the workspace) -- there is no parameter through which a
    live draft PricingState could reach it."""
    quote = _committed_quote(_configuration())
    workspace = create_scenario_workspace(quote)
    _saved_scenario(quote, workspace, "Saved Alt", _configuration(users=8))

    params = list(inspect.signature(build_scenario_comparison).parameters)
    assert params == ["quote", "scenarios"]

    comparison = build_scenario_comparison(quote, workspace.scenarios)
    assert comparison.options[1].configuration.users == 8


def test_comparison_final_prices_are_snapshot_values():
    quote = _committed_quote(_configuration(requested_discount_percent=5))
    workspace = create_scenario_workspace(quote)
    scenario = _saved_scenario(quote, workspace, "Alt", _configuration(tier="growth"))

    comparison = build_scenario_comparison(quote, workspace.scenarios)

    assert comparison.options[0].final_price == quote.current_version.pricing_snapshot.final_price
    assert comparison.options[1].final_price == scenario.pricing_snapshot.final_price


def test_comparison_price_delta_is_relative_to_committed_baseline():
    quote = _committed_quote(_configuration(tier="enterprise"))
    workspace = create_scenario_workspace(quote)
    _saved_scenario(quote, workspace, "Cheaper", _configuration(tier="core"))
    _saved_scenario(quote, workspace, "Similar", _configuration(tier="enterprise", users=5))

    comparison = build_scenario_comparison(quote, workspace.scenarios)

    baseline_price = comparison.options[0].final_price
    assert comparison.price_deltas[0] is None
    for option, delta in zip(comparison.options[1:], comparison.price_deltas[1:]):
        assert delta == option.final_price - baseline_price


def test_comparison_marks_differing_configuration_rows():
    quote = _committed_quote(_configuration(tier="enterprise", coverage="national"))
    workspace = create_scenario_workspace(quote)
    _saved_scenario(quote, workspace, "Growth Tier", _configuration(tier="growth", coverage="national"))

    comparison = build_scenario_comparison(quote, workspace.scenarios)

    tier_row = next(r for r in comparison.rows if r.label == "Subscription tier")
    assert tier_row.differs is True
    assert tier_row.values == ("Enterprise", "Growth")


def test_comparison_does_not_mark_identical_rows_as_different():
    quote = _committed_quote(_configuration(tier="enterprise", coverage="national"))
    workspace = create_scenario_workspace(quote)
    _saved_scenario(
        quote, workspace, "Same Coverage", _configuration(tier="growth", coverage="national")
    )

    comparison = build_scenario_comparison(quote, workspace.scenarios)

    coverage_row = next(r for r in comparison.rows if r.label == "Geographic coverage")
    assert coverage_row.differs is False
    assert len(set(coverage_row.values)) == 1


def test_comparison_preserves_approval_state():
    quote = _committed_quote(_configuration(requested_discount_percent=5))
    workspace = create_scenario_workspace(quote)
    _saved_scenario(
        quote, workspace, "Needs Approval", _configuration(tier="growth", requested_discount_percent=15)
    )

    comparison = build_scenario_comparison(quote, workspace.scenarios)

    assert comparison.options[0].approval_required is False
    assert comparison.options[1].approval_required is True


def test_comparison_does_not_change_quote_history():
    quote = _committed_quote(_configuration())
    workspace = create_scenario_workspace(quote)
    _saved_scenario(quote, workspace, "Alt A", _configuration(tier="growth"))
    _saved_scenario(quote, workspace, "Alt B", _configuration(users=10))
    versions_before = tuple(quote.versions)

    build_scenario_comparison(quote, workspace.scenarios)

    assert tuple(quote.versions) == versions_before
    assert len(quote.versions) == 1


def test_comparison_does_not_change_scenario_workspace():
    quote = _committed_quote(_configuration())
    workspace = create_scenario_workspace(quote)
    _saved_scenario(quote, workspace, "Alt A", _configuration(tier="growth"))
    scenarios_before = tuple(workspace.scenarios)

    build_scenario_comparison(quote, workspace.scenarios)

    assert tuple(workspace.scenarios) == scenarios_before
    assert len(workspace.scenarios) == 1


def test_comparison_supports_a_single_saved_scenario():
    quote = _committed_quote(_configuration())
    workspace = create_scenario_workspace(quote)
    _saved_scenario(quote, workspace, "Only Alt", _configuration(users=8))

    comparison = build_scenario_comparison(quote, workspace.scenarios)

    assert len(comparison.options) == 2
    assert len(comparison.price_deltas) == 2
