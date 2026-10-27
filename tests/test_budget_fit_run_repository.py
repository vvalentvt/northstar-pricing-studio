from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from budget_fit import BudgetFitConstraints, BudgetFitRequest, find_budget_fit
from pricing_engine import QuoteRequest, load_rules
from quotes import ConfigurationSnapshot, Quote
from pricing_engine import calculate_quote
from quotes import PricingSnapshot
from persistence import (
    BudgetFitRun,
    BudgetFitRunNotFoundError,
    SQLiteBudgetFitRunRepository,
    SQLiteQuoteRepository,
)

RULES = load_rules(ROOT / "config" / "pricing_rules.yaml")


def _baseline_snapshot(**overrides) -> ConfigurationSnapshot:
    defaults = dict(
        customer_name="Acme",
        tier="growth",
        users=8,
        coverage="north_america",
        history_years=3,
        contract_months=24,
        premium_support=True,
    )
    defaults.update(overrides)
    return ConfigurationSnapshot(**defaults)


def _seed_quote(db_path: Path, quote_id: str = "Q-00001") -> Quote:
    repo = SQLiteQuoteRepository(db_path)
    configuration = QuoteRequest(
        customer_name="Acme",
        tier="growth",
        users=8,
        coverage="north_america",
        history_years=3,
        contract_months=24,
        premium_support=True,
    )
    result = calculate_quote(configuration, RULES)
    snapshot = PricingSnapshot.from_pricing_result(result)
    quote = Quote.create(
        quote_id=quote_id, customer_name="Acme", owner="vinnie",
        configuration=configuration, pricing_snapshot=snapshot,
    )
    repo.create(quote)
    return quote


def _run(quote_id: str = "Q-00001", base_version_number: int = 1, target_budget: float = 45000) -> BudgetFitRun:
    request = BudgetFitRequest(
        target_budget=target_budget,
        baseline_configuration=_baseline_snapshot(),
        constraints=BudgetFitConstraints(),
    )
    result = find_budget_fit(request, RULES)
    return BudgetFitRun(
        quote_id=quote_id,
        base_version_number=base_version_number,
        request=request,
        result=result,
    )


def test_run_round_trips(tmp_path):
    db_path = tmp_path / "northstar.db"
    _seed_quote(db_path)
    repo = SQLiteBudgetFitRunRepository(db_path)
    run = _run()

    repo.create_run(run)
    loaded = repo.get_run(run.run_id)

    assert loaded.run_id == run.run_id
    assert loaded.quote_id == "Q-00001"
    assert loaded.base_version_number == 1


def test_run_captures_base_version(tmp_path):
    db_path = tmp_path / "northstar.db"
    _seed_quote(db_path)
    repo = SQLiteBudgetFitRunRepository(db_path)
    run = _run(base_version_number=3)

    repo.create_run(run)
    loaded = repo.get_run(run.run_id)

    assert loaded.base_version_number == 3


def test_recommendation_snapshots_round_trip_exactly(tmp_path):
    db_path = tmp_path / "northstar.db"
    _seed_quote(db_path)
    repo = SQLiteBudgetFitRunRepository(db_path)
    run = _run()
    assert len(run.result.recommendations) > 0

    repo.create_run(run)
    loaded = repo.get_run(run.run_id)

    assert loaded.result.recommendations == run.result.recommendations
    for original, reloaded in zip(run.result.recommendations, loaded.result.recommendations):
        assert reloaded.configuration_snapshot == original.configuration_snapshot
        assert reloaded.pricing_snapshot == original.pricing_snapshot


def test_request_round_trips_exactly(tmp_path):
    db_path = tmp_path / "northstar.db"
    _seed_quote(db_path)
    repo = SQLiteBudgetFitRunRepository(db_path)
    run = _run(target_budget=52345)

    repo.create_run(run)
    loaded = repo.get_run(run.run_id)

    assert loaded.request == run.request
    assert loaded.request.target_budget == 52345


def test_run_survives_repository_recreation(tmp_path):
    db_path = tmp_path / "northstar.db"
    _seed_quote(db_path)
    repo_a = SQLiteBudgetFitRunRepository(db_path)
    run = _run()
    repo_a.create_run(run)
    del repo_a

    repo_b = SQLiteBudgetFitRunRepository(db_path)
    loaded = repo_b.get_run(run.run_id)

    assert loaded == run


def test_get_missing_run_raises(tmp_path):
    db_path = tmp_path / "northstar.db"
    _seed_quote(db_path)
    repo = SQLiteBudgetFitRunRepository(db_path)

    with pytest.raises(BudgetFitRunNotFoundError):
        repo.get_run("does-not-exist")
