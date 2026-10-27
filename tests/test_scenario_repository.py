from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pricing_engine import QuoteRequest, calculate_quote, load_rules
from quotes import (
    NegotiationContext,
    PricingSnapshot,
    Quote,
    Scenario,
    ScenarioSource,
    ScenarioWorkspace,
)
from persistence import (
    DuplicateWorkspaceError,
    ScenarioNotFoundError,
    SQLiteQuoteRepository,
    SQLiteScenarioRepository,
    WorkspaceNotFoundError,
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


def _quote(quote_id: str = "Q-00001", **overrides) -> Quote:
    configuration = _configuration(**overrides)
    snapshot = _snapshot(configuration)
    return Quote.create(
        quote_id=quote_id,
        customer_name="Acme",
        owner="vinnie",
        configuration=configuration,
        pricing_snapshot=snapshot,
    )


def _manual_scenario(base_version: int = 1, **overrides) -> Scenario:
    configuration = _configuration(requested_discount_percent=5, **overrides)
    from quotes import ConfigurationSnapshot

    return Scenario(
        name="Trimmed Scope",
        source_version_number=base_version,
        configuration_snapshot=ConfigurationSnapshot.from_request(configuration),
        pricing_snapshot=_snapshot(configuration),
        source=ScenarioSource.MANUAL,
    )


def _budget_fit_scenario(base_version: int = 1) -> Scenario:
    configuration = _configuration(tier="growth", users=8)
    from quotes import ConfigurationSnapshot

    return Scenario(
        name="Budget Fit — Recommended",
        source_version_number=base_version,
        configuration_snapshot=ConfigurationSnapshot.from_request(configuration),
        pricing_snapshot=_snapshot(configuration),
        source=ScenarioSource.BUDGET_FIT,
        negotiation_context=NegotiationContext(
            target_budget=50000,
            required_attributes=("Coverage",),
            flexible_attributes=("Tier", "Users"),
        ),
    )


def _db(tmp_path: Path) -> Path:
    return tmp_path / "northstar.db"


def _seed_quote(db_path: Path, quote_id: str = "Q-00001") -> Quote:
    quote_repo = SQLiteQuoteRepository(db_path)
    quote = _quote(quote_id)
    quote_repo.create(quote)
    return quote


def test_workspace_round_trips(tmp_path):
    db_path = _db(tmp_path)
    _seed_quote(db_path)
    repo = SQLiteScenarioRepository(db_path)
    workspace = ScenarioWorkspace(quote_id="Q-00001", base_version_number=1)

    repo.create_workspace(workspace)
    loaded = repo.get_workspace("Q-00001")

    assert loaded.quote_id == "Q-00001"
    assert loaded.base_version_number == 1
    assert loaded.scenarios == ()
    assert loaded.selected_scenario_id is None


def test_manual_scenario_round_trips(tmp_path):
    db_path = _db(tmp_path)
    _seed_quote(db_path)
    repo = SQLiteScenarioRepository(db_path)
    workspace = ScenarioWorkspace(quote_id="Q-00001", base_version_number=1)
    repo.create_workspace(workspace)
    scenario = _manual_scenario()

    repo.add_scenario("Q-00001", scenario)
    loaded = repo.get_workspace("Q-00001")

    assert len(loaded.scenarios) == 1
    assert loaded.scenarios[0] == scenario


def test_budget_fit_scenario_round_trips(tmp_path):
    db_path = _db(tmp_path)
    _seed_quote(db_path)
    repo = SQLiteScenarioRepository(db_path)
    repo.create_workspace(ScenarioWorkspace(quote_id="Q-00001", base_version_number=1))
    scenario = _budget_fit_scenario()

    repo.add_scenario("Q-00001", scenario)
    loaded = repo.get_workspace("Q-00001")

    assert len(loaded.scenarios) == 1
    assert loaded.scenarios[0] == scenario
    assert loaded.scenarios[0].source == ScenarioSource.BUDGET_FIT


def test_manual_and_budget_fit_scenarios_coexist(tmp_path):
    db_path = _db(tmp_path)
    _seed_quote(db_path)
    repo = SQLiteScenarioRepository(db_path)
    repo.create_workspace(ScenarioWorkspace(quote_id="Q-00001", base_version_number=1))
    manual = _manual_scenario()
    budget_fit = _budget_fit_scenario()

    repo.add_scenario("Q-00001", manual)
    repo.add_scenario("Q-00001", budget_fit)
    loaded = repo.get_workspace("Q-00001")

    assert len(loaded.scenarios) == 2
    sources = {s.source for s in loaded.scenarios}
    assert sources == {ScenarioSource.MANUAL, ScenarioSource.BUDGET_FIT}


def test_selection_persists(tmp_path):
    db_path = _db(tmp_path)
    _seed_quote(db_path)
    repo = SQLiteScenarioRepository(db_path)
    repo.create_workspace(ScenarioWorkspace(quote_id="Q-00001", base_version_number=1))
    scenario = _manual_scenario()
    repo.add_scenario("Q-00001", scenario)

    repo.select_scenario("Q-00001", scenario.scenario_id)
    loaded = repo.get_workspace("Q-00001")

    assert loaded.selected_scenario_id == scenario.scenario_id
    assert loaded.selected_scenario == scenario


def test_selecting_unknown_scenario_raises(tmp_path):
    db_path = _db(tmp_path)
    _seed_quote(db_path)
    repo = SQLiteScenarioRepository(db_path)
    repo.create_workspace(ScenarioWorkspace(quote_id="Q-00001", base_version_number=1))

    with pytest.raises(ScenarioNotFoundError):
        repo.select_scenario("Q-00001", "does-not-exist")


def test_clear_selection(tmp_path):
    db_path = _db(tmp_path)
    _seed_quote(db_path)
    repo = SQLiteScenarioRepository(db_path)
    repo.create_workspace(ScenarioWorkspace(quote_id="Q-00001", base_version_number=1))
    scenario = _manual_scenario()
    repo.add_scenario("Q-00001", scenario)
    repo.select_scenario("Q-00001", scenario.scenario_id)

    repo.clear_selection("Q-00001")

    assert repo.get_workspace("Q-00001").selected_scenario_id is None


def test_configuration_snapshot_fidelity(tmp_path):
    db_path = _db(tmp_path)
    _seed_quote(db_path)
    repo = SQLiteScenarioRepository(db_path)
    repo.create_workspace(ScenarioWorkspace(quote_id="Q-00001", base_version_number=1))
    scenario = _manual_scenario(tier="enterprise", users=20, coverage="global")
    repo.add_scenario("Q-00001", scenario)

    loaded = repo.get_workspace("Q-00001").scenarios[0]

    assert loaded.configuration_snapshot == scenario.configuration_snapshot
    assert loaded.configuration_snapshot.tier == "enterprise"
    assert loaded.configuration_snapshot.users == 20


def test_pricing_snapshot_fidelity(tmp_path):
    db_path = _db(tmp_path)
    _seed_quote(db_path)
    repo = SQLiteScenarioRepository(db_path)
    repo.create_workspace(ScenarioWorkspace(quote_id="Q-00001", base_version_number=1))
    scenario = _manual_scenario()
    repo.add_scenario("Q-00001", scenario)

    loaded = repo.get_workspace("Q-00001").scenarios[0]

    assert loaded.pricing_snapshot == scenario.pricing_snapshot
    assert loaded.pricing_snapshot.final_price == scenario.pricing_snapshot.final_price
    assert loaded.pricing_snapshot.rule_version == scenario.pricing_snapshot.rule_version


def test_negotiation_context_fidelity(tmp_path):
    db_path = _db(tmp_path)
    _seed_quote(db_path)
    repo = SQLiteScenarioRepository(db_path)
    repo.create_workspace(ScenarioWorkspace(quote_id="Q-00001", base_version_number=1))
    scenario = _budget_fit_scenario()
    repo.add_scenario("Q-00001", scenario)

    loaded = repo.get_workspace("Q-00001").scenarios[0]

    assert loaded.negotiation_context == scenario.negotiation_context
    assert loaded.negotiation_context.target_budget == 50000


def test_manual_scenario_has_no_negotiation_context(tmp_path):
    db_path = _db(tmp_path)
    _seed_quote(db_path)
    repo = SQLiteScenarioRepository(db_path)
    repo.create_workspace(ScenarioWorkspace(quote_id="Q-00001", base_version_number=1))
    scenario = _manual_scenario()
    repo.add_scenario("Q-00001", scenario)

    loaded = repo.get_workspace("Q-00001").scenarios[0]

    assert loaded.negotiation_context is None


def test_workspace_survives_repository_recreation(tmp_path):
    db_path = _db(tmp_path)
    _seed_quote(db_path)
    repo_a = SQLiteScenarioRepository(db_path)
    repo_a.create_workspace(ScenarioWorkspace(quote_id="Q-00001", base_version_number=1))
    scenario = _manual_scenario()
    repo_a.add_scenario("Q-00001", scenario)
    repo_a.select_scenario("Q-00001", scenario.scenario_id)
    del repo_a

    repo_b = SQLiteScenarioRepository(db_path)
    loaded = repo_b.get_workspace("Q-00001")

    assert loaded.scenarios == (scenario,)
    assert loaded.selected_scenario_id == scenario.scenario_id


def test_scenarios_load_deterministically(tmp_path):
    db_path = _db(tmp_path)
    _seed_quote(db_path)
    repo = SQLiteScenarioRepository(db_path)
    repo.create_workspace(ScenarioWorkspace(quote_id="Q-00001", base_version_number=1))
    first = _manual_scenario(users=6)
    second = _budget_fit_scenario()
    repo.add_scenario("Q-00001", first)
    repo.add_scenario("Q-00001", second)

    loaded_once = repo.get_workspace("Q-00001").scenarios
    loaded_twice = repo.get_workspace("Q-00001").scenarios

    assert loaded_once == loaded_twice
    assert [s.scenario_id for s in loaded_once] == [first.scenario_id, second.scenario_id]


def test_create_workspace_duplicate_raises(tmp_path):
    db_path = _db(tmp_path)
    _seed_quote(db_path)
    repo = SQLiteScenarioRepository(db_path)
    repo.create_workspace(ScenarioWorkspace(quote_id="Q-00001", base_version_number=1))

    with pytest.raises(DuplicateWorkspaceError):
        repo.create_workspace(ScenarioWorkspace(quote_id="Q-00001", base_version_number=1))


def test_get_missing_workspace_raises(tmp_path):
    db_path = _db(tmp_path)
    _seed_quote(db_path)
    repo = SQLiteScenarioRepository(db_path)

    with pytest.raises(WorkspaceNotFoundError):
        repo.get_workspace("Q-00001")


def test_clearing_workspace_does_not_alter_quote_history(tmp_path):
    db_path = _db(tmp_path)
    quote = _seed_quote(db_path)
    quote_repo = SQLiteQuoteRepository(db_path)
    scenario_repo = SQLiteScenarioRepository(db_path)
    scenario_repo.create_workspace(ScenarioWorkspace(quote_id="Q-00001", base_version_number=1))
    scenario_repo.add_scenario("Q-00001", _manual_scenario())

    scenario_repo.clear_workspace("Q-00001")

    assert scenario_repo.workspace_exists("Q-00001") is False
    reloaded_quote = quote_repo.get("Q-00001")
    assert reloaded_quote == quote
    assert reloaded_quote.current_version == quote.current_version


def test_clear_workspace_removes_its_scenarios(tmp_path):
    db_path = _db(tmp_path)
    _seed_quote(db_path)
    repo = SQLiteScenarioRepository(db_path)
    repo.create_workspace(ScenarioWorkspace(quote_id="Q-00001", base_version_number=1))
    repo.add_scenario("Q-00001", _manual_scenario())

    repo.clear_workspace("Q-00001")
    repo.create_workspace(ScenarioWorkspace(quote_id="Q-00001", base_version_number=1))
    loaded = repo.get_workspace("Q-00001")

    assert loaded.scenarios == ()


def test_clear_missing_workspace_raises(tmp_path):
    db_path = _db(tmp_path)
    _seed_quote(db_path)
    repo = SQLiteScenarioRepository(db_path)

    with pytest.raises(WorkspaceNotFoundError):
        repo.clear_workspace("Q-00001")
