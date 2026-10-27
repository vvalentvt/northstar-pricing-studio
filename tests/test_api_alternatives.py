"""Tests for the FastAPI Alternatives / negotiation-workspace HTTP
boundary (api/routers/alternatives.py).

Each test overrides the quote/scenario/budget-fit-run repositories with
SQLite repositories pointed at a pytest tmp_path file -- never the real
data/northstar.db -- so these run against a real (temporary) SQLite
file, not a mock.
"""

from pathlib import Path
import sys

from fastapi.testclient import TestClient
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from api.dependencies import (
    get_budget_fit_run_repository,
    get_quote_repository,
    get_scenario_repository,
)
from api.main import app
from persistence import (
    SQLiteBudgetFitRunRepository,
    SQLiteQuoteRepository,
    SQLiteScenarioRepository,
)
from quotes import QuoteVersionSource

client = TestClient(app)


@pytest.fixture(autouse=True)
def _repository_overrides(tmp_path):
    db_path = tmp_path / "northstar.db"
    quote_repository = SQLiteQuoteRepository(db_path)
    scenario_repository = SQLiteScenarioRepository(db_path)
    budget_fit_run_repository = SQLiteBudgetFitRunRepository(db_path)
    app.dependency_overrides[get_quote_repository] = lambda: quote_repository
    app.dependency_overrides[get_scenario_repository] = lambda: scenario_repository
    app.dependency_overrides[get_budget_fit_run_repository] = lambda: budget_fit_run_repository
    yield quote_repository, scenario_repository, budget_fit_run_repository
    app.dependency_overrides.pop(get_quote_repository, None)
    app.dependency_overrides.pop(get_scenario_repository, None)
    app.dependency_overrides.pop(get_budget_fit_run_repository, None)


def _configuration_payload(**overrides) -> dict:
    payload = dict(
        customerName="Acme",
        tier="growth",
        users=8,
        coverage="north_america",
        historyYears=3,
        contractMonths=24,
        premiumSupport=True,
        implementationServices=False,
        renewal=False,
        requestedDiscountPercent=0,
    )
    payload.update(overrides)
    return payload


def _create_quote(**config_overrides) -> dict:
    response = client.post(
        "/api/quotes",
        json={
            "customerName": "Acme",
            "owner": "Vincent",
            "configuration": _configuration_payload(**config_overrides),
        },
    )
    assert response.status_code == 201
    return response.json()


def _add_manual_alternative(quote_id: str, name: str = "Trimmed Scope", **config_overrides) -> dict:
    defaults = dict(
        tier="core", users=5, coverage="national", historyYears=1,
        contractMonths=12, premiumSupport=False,
    )
    defaults.update(config_overrides)
    response = client.post(
        f"/api/quotes/{quote_id}/alternatives/manual",
        json={"name": name, "configuration": _configuration_payload(**defaults)},
    )
    assert response.status_code == 201
    return response.json()


def _run_quote_linked_budget_fit(quote_id: str, target_budget: float = 50000) -> dict:
    response = client.post(f"/api/quotes/{quote_id}/budget-fit", json={"targetBudget": target_budget})
    assert response.status_code == 200
    return response.json()


def _select(quote_id: str, scenario_id: str | None) -> dict:
    response = client.put(
        f"/api/quotes/{quote_id}/alternatives/selection", json={"scenarioId": scenario_id}
    )
    assert response.status_code == 200
    return response.json()


def _promote(quote_id: str):
    return client.post(f"/api/quotes/{quote_id}/revisions/from-selected-alternative")


class TestManualAlternatives:
    def test_manual_alternative_creates_scenario_not_quote_version(self):
        quote = _create_quote()

        alternatives = _add_manual_alternative(quote["quoteId"])

        assert len(alternatives["scenarios"]) == 1
        reloaded_quote = client.get(f"/api/quotes/{quote['quoteId']}").json()
        assert reloaded_quote["currentVersion"]["versionNumber"] == 1

    def test_workspace_baseline_equals_current_version_at_creation(self):
        quote = _create_quote()

        alternatives = client.get(f"/api/quotes/{quote['quoteId']}/alternatives").json()

        assert alternatives["baseVersionNumber"] == 1
        assert alternatives["baseline"]["versionNumber"] == 1
        assert alternatives["baseline"]["pricing"]["finalPrice"] == quote["currentVersion"]["pricing"]["finalPrice"]

    def test_multiple_scenarios_coexist(self):
        quote = _create_quote()
        _add_manual_alternative(quote["quoteId"], name="Option A")
        alternatives = _add_manual_alternative(quote["quoteId"], name="Option B", users=7)

        assert len(alternatives["scenarios"]) == 2
        names = {s["name"] for s in alternatives["scenarios"]}
        assert names == {"Option A", "Option B"}

    def test_manual_scenario_uses_canonical_pricing_engine(self):
        from pricing_engine import QuoteRequest, calculate_quote, load_rules

        quote = _create_quote()
        alternatives = _add_manual_alternative(quote["quoteId"], tier="core", users=5)
        scenario = alternatives["scenarios"][0]

        rules = load_rules(ROOT / "config" / "pricing_rules.yaml")
        direct = calculate_quote(
            QuoteRequest(
                customer_name="Acme", tier="core", users=5, coverage="national",
                history_years=1, contract_months=12, premium_support=False,
            ),
            rules,
        )
        assert scenario["pricing"]["finalPrice"] == direct.final_price


class TestSelection:
    def test_selection_persists(self):
        quote = _create_quote()
        alternatives = _add_manual_alternative(quote["quoteId"])
        scenario_id = alternatives["scenarios"][0]["scenarioId"]

        _select(quote["quoteId"], scenario_id)
        reloaded = client.get(f"/api/quotes/{quote['quoteId']}/alternatives").json()

        assert reloaded["selectedScenarioId"] == scenario_id

    def test_selection_creates_no_quote_version(self):
        quote = _create_quote()
        alternatives = _add_manual_alternative(quote["quoteId"])
        scenario_id = alternatives["scenarios"][0]["scenarioId"]

        _select(quote["quoteId"], scenario_id)

        reloaded_quote = client.get(f"/api/quotes/{quote['quoteId']}").json()
        assert reloaded_quote["currentVersion"]["versionNumber"] == 1

    def test_clearing_selection_is_allowed(self):
        quote = _create_quote()
        alternatives = _add_manual_alternative(quote["quoteId"])
        scenario_id = alternatives["scenarios"][0]["scenarioId"]
        _select(quote["quoteId"], scenario_id)

        cleared = _select(quote["quoteId"], None)

        assert cleared["selectedScenarioId"] is None


class TestPromotion:
    def test_promotion_creates_exactly_one_next_version(self):
        quote = _create_quote()
        alternatives = _add_manual_alternative(quote["quoteId"])
        _select(quote["quoteId"], alternatives["scenarios"][0]["scenarioId"])

        response = _promote(quote["quoteId"])

        assert response.status_code == 200
        body = response.json()
        assert body["currentVersion"]["versionNumber"] == 2
        assert len(body["versionHistory"]) == 1
        assert body["versionHistory"][0]["versionNumber"] == 1

    def test_promotion_reuses_scenario_pricing_snapshot_exactly(self):
        quote = _create_quote()
        alternatives = _add_manual_alternative(quote["quoteId"])
        scenario = alternatives["scenarios"][0]
        _select(quote["quoteId"], scenario["scenarioId"])

        body = _promote(quote["quoteId"]).json()

        committed = body["currentVersion"]["pricing"]
        assert committed["finalPrice"] == scenario["pricing"]["finalPrice"]
        assert committed["ruleVersion"] == scenario["pricing"]["ruleVersion"]
        assert committed["approvalRequired"] == scenario["pricing"]["approvalRequired"]
        assert committed == scenario["pricing"]

    def test_promotion_preserves_manual_scenario_source(self):
        quote = _create_quote()
        alternatives = _add_manual_alternative(quote["quoteId"])
        _select(quote["quoteId"], alternatives["scenarios"][0]["scenarioId"])

        body = _promote(quote["quoteId"]).json()

        assert body["currentVersion"]["source"] == "manual_revision"

    def test_promotion_preserves_budget_fit_scenario_source(self):
        quote = _create_quote()
        run = _run_quote_linked_budget_fit(quote["quoteId"])
        alternatives = client.post(
            f"/api/quotes/{quote['quoteId']}/alternatives/from-budget-fit",
            json={"runId": run["runId"], "rank": 1},
        ).json()
        _select(quote["quoteId"], alternatives["scenarios"][0]["scenarioId"])

        body = _promote(quote["quoteId"]).json()

        assert body["currentVersion"]["source"] == "budget_fit"

    def test_approval_required_scenario_can_be_promoted(self):
        quote = _create_quote()
        alternatives = _add_manual_alternative(
            quote["quoteId"], tier="enterprise", users=5, coverage="national",
            historyYears=1, contractMonths=12, premiumSupport=False,
            requestedDiscountPercent=18,
        )
        scenario = alternatives["scenarios"][0]
        assert scenario["pricing"]["approvalRequired"] is True
        _select(quote["quoteId"], scenario["scenarioId"])

        body = _promote(quote["quoteId"]).json()

        assert body["currentVersion"]["pricing"]["approvalRequired"] is True
        assert body["currentVersion"]["pricing"]["approvalReason"] is not None

    def test_successful_promotion_clears_workspace(self):
        quote = _create_quote()
        alternatives = _add_manual_alternative(quote["quoteId"])
        _select(quote["quoteId"], alternatives["scenarios"][0]["scenarioId"])
        _promote(quote["quoteId"])

        reloaded = client.get(f"/api/quotes/{quote['quoteId']}/alternatives").json()

        assert reloaded["scenarios"] == []
        assert reloaded["selectedScenarioId"] is None

    def test_next_workspace_begins_from_new_version(self):
        quote = _create_quote()
        alternatives = _add_manual_alternative(quote["quoteId"])
        _select(quote["quoteId"], alternatives["scenarios"][0]["scenarioId"])
        _promote(quote["quoteId"])

        reloaded = client.get(f"/api/quotes/{quote['quoteId']}/alternatives").json()

        assert reloaded["baseVersionNumber"] == 2
        assert reloaded["currentVersionNumber"] == 2
        assert reloaded["stale"] is False

    def test_promotion_requires_a_selection(self):
        quote = _create_quote()
        _add_manual_alternative(quote["quoteId"])

        response = _promote(quote["quoteId"])

        assert response.status_code == 400

    def test_promotion_with_no_workspace_returns_404(self):
        quote = _create_quote()

        response = _promote(quote["quoteId"])

        assert response.status_code == 404


class TestStaleWorkspace:
    def _make_stale(self, quote_repository, quote_id: str):
        """Advances the Quote externally (bypassing the Alternatives
        API entirely), leaving any already-loaded workspace stale --
        the same mechanism Phase 6E spec section 49 describes."""
        quote = quote_repository.get(quote_id)
        current = quote.current_version
        new_version = quote.add_version(
            configuration=current.configuration_snapshot,
            pricing_snapshot=current.pricing_snapshot,
            source=QuoteVersionSource.MANUAL_REVISION,
        )
        quote_repository.append_version(
            quote_id, new_version, expected_current_version=current.version_number
        )

    def test_stale_workspace_promotion_returns_conflict_with_no_history_mutation(
        self, _repository_overrides
    ):
        quote_repository, _scenario_repository, _run_repository = _repository_overrides
        quote = _create_quote()
        alternatives = _add_manual_alternative(quote["quoteId"])
        _select(quote["quoteId"], alternatives["scenarios"][0]["scenarioId"])

        self._make_stale(quote_repository, quote["quoteId"])

        response = _promote(quote["quoteId"])

        assert response.status_code == 409
        reloaded = client.get(f"/api/quotes/{quote['quoteId']}").json()
        assert reloaded["currentVersion"]["versionNumber"] == 2
        assert len(reloaded["versionHistory"]) == 1

    def test_stale_workspace_cannot_select(self, _repository_overrides):
        quote_repository, _scenario_repository, _run_repository = _repository_overrides
        quote = _create_quote()
        alternatives = _add_manual_alternative(quote["quoteId"])
        scenario_id = alternatives["scenarios"][0]["scenarioId"]

        self._make_stale(quote_repository, quote["quoteId"])

        response = client.put(
            f"/api/quotes/{quote['quoteId']}/alternatives/selection",
            json={"scenarioId": scenario_id},
        )
        assert response.status_code == 409

    def test_stale_workspace_cannot_add_alternative(self, _repository_overrides):
        quote_repository, _scenario_repository, _run_repository = _repository_overrides
        quote = _create_quote()
        client.get(f"/api/quotes/{quote['quoteId']}/alternatives")  # lazily create workspace @ v1

        self._make_stale(quote_repository, quote["quoteId"])

        response = client.post(
            f"/api/quotes/{quote['quoteId']}/alternatives/manual",
            json={"name": "x", "configuration": _configuration_payload()},
        )
        assert response.status_code == 409

    def test_restart_creates_fresh_workspace_from_current_version(self, _repository_overrides):
        quote_repository, _scenario_repository, _run_repository = _repository_overrides
        quote = _create_quote()
        _add_manual_alternative(quote["quoteId"])

        self._make_stale(quote_repository, quote["quoteId"])

        restarted = client.post(f"/api/quotes/{quote['quoteId']}/alternatives/restart").json()

        assert restarted["baseVersionNumber"] == 2
        assert restarted["stale"] is False
        assert restarted["scenarios"] == []


class TestBudgetFitAlternatives:
    def test_quote_linked_budget_fit_captures_base_version(self):
        quote = _create_quote()

        run = _run_quote_linked_budget_fit(quote["quoteId"])

        assert run["baseVersionNumber"] == 1
        assert run["quoteId"] == quote["quoteId"]
        assert len(run["recommendations"]) > 0

    def test_add_from_budget_fit_reuses_exact_recommendation_snapshot(self):
        quote = _create_quote()
        run = _run_quote_linked_budget_fit(quote["quoteId"])
        recommendation = run["recommendations"][0]

        alternatives = client.post(
            f"/api/quotes/{quote['quoteId']}/alternatives/from-budget-fit",
            json={"runId": run["runId"], "rank": recommendation["rank"]},
        ).json()

        scenario = alternatives["scenarios"][0]
        assert scenario["pricing"]["finalPrice"] == recommendation["finalPrice"]
        assert scenario["configuration"] == recommendation["configuration"]

    def test_duplicate_budget_fit_recommendation_is_blocked(self):
        quote = _create_quote()
        run = _run_quote_linked_budget_fit(quote["quoteId"])

        first = client.post(
            f"/api/quotes/{quote['quoteId']}/alternatives/from-budget-fit",
            json={"runId": run["runId"], "rank": 1},
        )
        assert first.status_code == 201

        second = client.post(
            f"/api/quotes/{quote['quoteId']}/alternatives/from-budget-fit",
            json={"runId": run["runId"], "rank": 1},
        )
        assert second.status_code == 409

    def test_calculated_at_only_difference_does_not_create_duplicate(self):
        """Two independent Budget Fit runs over the same quote/inputs
        should produce commercially-identical recommendations
        (identical configuration + pricing facts, differing only in
        calculatedAt) -- adding one, then the equivalent one from a
        second run, must be blocked as a duplicate."""
        quote = _create_quote()
        run_a = _run_quote_linked_budget_fit(quote["quoteId"])
        run_b = _run_quote_linked_budget_fit(quote["quoteId"])
        assert run_a["recommendations"][0]["finalPrice"] == run_b["recommendations"][0]["finalPrice"]

        first = client.post(
            f"/api/quotes/{quote['quoteId']}/alternatives/from-budget-fit",
            json={"runId": run_a["runId"], "rank": 1},
        )
        assert first.status_code == 201

        second = client.post(
            f"/api/quotes/{quote['quoteId']}/alternatives/from-budget-fit",
            json={"runId": run_b["runId"], "rank": 1},
        )
        assert second.status_code == 409

    def test_same_final_price_different_configuration_remains_distinct(self):
        quote = _create_quote()
        run = _run_quote_linked_budget_fit(quote["quoteId"])
        manual = _add_manual_alternative(quote["quoteId"])
        from_bf = client.post(
            f"/api/quotes/{quote['quoteId']}/alternatives/from-budget-fit",
            json={"runId": run["runId"], "rank": 1},
        )
        assert from_bf.status_code == 201
        combined = from_bf.json()
        assert len(combined["scenarios"]) == 2

    def test_stale_run_cannot_add_recommendation(self, _repository_overrides):
        quote_repository, _scenario_repository, _run_repository = _repository_overrides
        quote = _create_quote()
        run = _run_quote_linked_budget_fit(quote["quoteId"])

        TestStaleWorkspace()._make_stale(quote_repository, quote["quoteId"])

        response = client.post(
            f"/api/quotes/{quote['quoteId']}/alternatives/from-budget-fit",
            json={"runId": run["runId"], "rank": 1},
        )
        assert response.status_code == 409

    def test_recommendation_from_another_quote_cannot_be_used(self):
        quote_a = _create_quote()
        quote_b = _create_quote()
        run_a = _run_quote_linked_budget_fit(quote_a["quoteId"])

        response = client.post(
            f"/api/quotes/{quote_b['quoteId']}/alternatives/from-budget-fit",
            json={"runId": run_a["runId"], "rank": 1},
        )
        assert response.status_code == 404

    def test_invalid_recommendation_rank_is_rejected(self):
        quote = _create_quote()
        run = _run_quote_linked_budget_fit(quote["quoteId"])

        response = client.post(
            f"/api/quotes/{quote['quoteId']}/alternatives/from-budget-fit",
            json={"runId": run["runId"], "rank": 999},
        )
        assert response.status_code == 404

    def test_unknown_run_id_is_rejected(self):
        quote = _create_quote()

        response = client.post(
            f"/api/quotes/{quote['quoteId']}/alternatives/from-budget-fit",
            json={"runId": "does-not-exist", "rank": 1},
        )
        assert response.status_code == 404


class TestVersionHistory:
    def test_historical_version_unaffected_by_promotion(self):
        quote = _create_quote()
        original_price = quote["currentVersion"]["pricing"]["finalPrice"]
        alternatives = _add_manual_alternative(quote["quoteId"])
        _select(quote["quoteId"], alternatives["scenarios"][0]["scenarioId"])
        _promote(quote["quoteId"])

        v1 = client.get(f"/api/quotes/{quote['quoteId']}/versions/1").json()
        v2 = client.get(f"/api/quotes/{quote['quoteId']}/versions/2").json()

        assert v1["pricing"]["finalPrice"] == original_price
        assert v1["source"] == "initial"
        assert v2["versionNumber"] == 2
        assert v2["source"] == "manual_revision"

    def test_get_quote_after_promotion_shows_version_history(self):
        quote = _create_quote()
        alternatives = _add_manual_alternative(quote["quoteId"])
        _select(quote["quoteId"], alternatives["scenarios"][0]["scenarioId"])
        _promote(quote["quoteId"])

        reloaded = client.get(f"/api/quotes/{quote['quoteId']}").json()

        assert reloaded["currentVersion"]["versionNumber"] == 2
        assert [v["versionNumber"] for v in reloaded["versionHistory"]] == [1]
