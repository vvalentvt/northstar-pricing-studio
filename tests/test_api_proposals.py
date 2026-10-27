"""Tests for the FastAPI Proposal HTTP boundary (api/routers/proposals.py).

Each test overrides the quote/scenario/budget-fit-run/proposal
repositories with SQLite repositories pointed at a pytest tmp_path
file -- never the real data/northstar.db -- and uses the real
ReportLabProposalRenderer (fast, deterministic) rather than a mock, so
these tests prove the real rendering/persistence pipeline end to end.
"""

from pathlib import Path
import sys

from fastapi.testclient import TestClient
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import pricing_engine
from api.dependencies import (
    get_budget_fit_run_repository,
    get_proposal_renderer,
    get_proposal_repository,
    get_quote_repository,
    get_scenario_repository,
)
from api.main import app
from persistence import (
    SQLiteBudgetFitRunRepository,
    SQLiteProposalRepository,
    SQLiteQuoteRepository,
    SQLiteScenarioRepository,
)
from proposals import ReportLabProposalRenderer

client = TestClient(app)


@pytest.fixture(autouse=True)
def _repository_overrides(tmp_path):
    db_path = tmp_path / "northstar.db"
    quote_repository = SQLiteQuoteRepository(db_path)
    scenario_repository = SQLiteScenarioRepository(db_path)
    budget_fit_run_repository = SQLiteBudgetFitRunRepository(db_path)
    proposal_repository = SQLiteProposalRepository(db_path)
    renderer = ReportLabProposalRenderer()
    app.dependency_overrides[get_quote_repository] = lambda: quote_repository
    app.dependency_overrides[get_scenario_repository] = lambda: scenario_repository
    app.dependency_overrides[get_budget_fit_run_repository] = lambda: budget_fit_run_repository
    app.dependency_overrides[get_proposal_repository] = lambda: proposal_repository
    app.dependency_overrides[get_proposal_renderer] = lambda: renderer
    yield quote_repository, proposal_repository, scenario_repository
    app.dependency_overrides.clear()


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


def _proposal_payload(**overrides) -> dict:
    payload = dict(
        expectedVersionNumber=1,
        proposalTitle="Pricing Proposal",
        executiveSummary="Northstar is pleased to provide this pricing proposal for Acme.",
        commercialNotes="Multi-year discount available on request.",
    )
    payload.update(overrides)
    return payload


def _generate(quote_id: str, **payload_overrides):
    return client.post(f"/api/quotes/{quote_id}/proposals", json=_proposal_payload(**payload_overrides))


class TestGenerateProposal:
    def test_generate_returns_201(self):
        quote = _create_quote()

        response = _generate(quote["quoteId"])

        assert response.status_code == 201
        body = response.json()
        assert body["proposalId"].startswith("P-")
        assert body["quoteId"] == quote["quoteId"]
        assert body["quoteVersionNumber"] == 1

    def test_generation_uses_committed_current_quote_version(self):
        quote = _create_quote()

        body = _generate(quote["quoteId"]).json()

        assert body["pricing"] == quote["currentVersion"]["pricing"]
        assert body["configuration"] == quote["currentVersion"]["configuration"]

    def test_generation_ignores_client_supplied_commercial_facts(self):
        quote = _create_quote()
        payload = _proposal_payload()
        payload["finalPrice"] = 1.0
        payload["pricing"] = {"finalPrice": 1.0}
        payload["approvalRequired"] = False

        body = client.post(f"/api/quotes/{quote['quoteId']}/proposals", json=payload).json()

        assert body["pricing"]["finalPrice"] == quote["currentVersion"]["pricing"]["finalPrice"]
        assert body["pricing"]["finalPrice"] != 1.0

    def test_creates_no_quote_version(self):
        quote = _create_quote()

        _generate(quote["quoteId"])

        reloaded = client.get(f"/api/quotes/{quote['quoteId']}").json()
        assert reloaded["currentVersion"]["versionNumber"] == 1
        assert reloaded["versionHistory"] == []

    def test_changes_no_scenario_workspace(self):
        quote = _create_quote()
        alt_response = client.post(
            f"/api/quotes/{quote['quoteId']}/alternatives/manual",
            json={"name": "Trimmed Scope", "configuration": _configuration_payload(tier="core", users=5)},
        )
        assert alt_response.status_code == 201
        before = client.get(f"/api/quotes/{quote['quoteId']}/alternatives").json()

        _generate(quote["quoteId"])

        after = client.get(f"/api/quotes/{quote['quoteId']}/alternatives").json()
        assert after["scenarios"] == before["scenarios"]
        assert after["selectedScenarioId"] == before["selectedScenarioId"]

    def test_missing_quote_returns_404(self):
        response = _generate("Q-does-not-exist")

        assert response.status_code == 404

    def test_invalid_narrative_returns_422(self):
        quote = _create_quote()

        response = client.post(
            f"/api/quotes/{quote['quoteId']}/proposals",
            json=_proposal_payload(proposalTitle="", executiveSummary=""),
        )

        assert response.status_code == 422


class TestApprovalGate:
    def test_within_authority_generation_succeeds(self):
        quote = _create_quote(requestedDiscountPercent=0)
        assert quote["currentVersion"]["pricing"]["approvalRequired"] is False

        response = _generate(quote["quoteId"])

        assert response.status_code == 201

    def test_approval_required_generation_is_blocked(self):
        quote = _create_quote(
            tier="enterprise", users=20, coverage="global", historyYears=5,
            contractMonths=36, implementationServices=True, requestedDiscountPercent=18,
        )
        assert quote["currentVersion"]["pricing"]["approvalRequired"] is True

        response = _generate(quote["quoteId"])

        assert response.status_code == 409
        listed = client.get(f"/api/quotes/{quote['quoteId']}/proposals").json()
        assert listed == []
        reloaded_quote = client.get(f"/api/quotes/{quote['quoteId']}").json()
        assert reloaded_quote["currentVersion"]["versionNumber"] == 1


class TestStaleVersion:
    def test_stale_expected_version_is_blocked(self, _repository_overrides):
        quote_repository, _proposal_repository, _scenario_repository = _repository_overrides
        quote = _create_quote()
        alt_response = client.post(
            f"/api/quotes/{quote['quoteId']}/alternatives/manual",
            json={"name": "Trimmed Scope", "configuration": _configuration_payload(tier="core", users=5)},
        ).json()
        scenario_id = alt_response["scenarios"][0]["scenarioId"]
        client.put(
            f"/api/quotes/{quote['quoteId']}/alternatives/selection",
            json={"scenarioId": scenario_id},
        )
        client.post(f"/api/quotes/{quote['quoteId']}/revisions/from-selected-alternative")

        response = _generate(quote["quoteId"], expectedVersionNumber=1)

        assert response.status_code == 409
        listed = client.get(f"/api/quotes/{quote['quoteId']}/proposals").json()
        assert listed == []

    def test_matching_current_version_succeeds(self):
        quote = _create_quote()
        alt_response = client.post(
            f"/api/quotes/{quote['quoteId']}/alternatives/manual",
            json={"name": "Trimmed Scope", "configuration": _configuration_payload(tier="core", users=5)},
        ).json()
        scenario_id = alt_response["scenarios"][0]["scenarioId"]
        client.put(
            f"/api/quotes/{quote['quoteId']}/alternatives/selection", json={"scenarioId": scenario_id}
        )
        client.post(f"/api/quotes/{quote['quoteId']}/revisions/from-selected-alternative")

        response = _generate(quote["quoteId"], expectedVersionNumber=2)

        assert response.status_code == 201
        assert response.json()["quoteVersionNumber"] == 2


class TestRetrievalAndPdf:
    def test_proposal_detail_retrievable(self):
        quote = _create_quote()
        created = _generate(quote["quoteId"]).json()

        response = client.get(f"/api/proposals/{created['proposalId']}")

        assert response.status_code == 200
        assert response.json()["proposalId"] == created["proposalId"]

    def test_proposal_list_retrievable(self):
        quote = _create_quote()
        created = _generate(quote["quoteId"]).json()

        response = client.get(f"/api/quotes/{quote['quoteId']}/proposals")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["proposalId"] == created["proposalId"]

    def test_pdf_endpoint_returns_application_pdf(self):
        quote = _create_quote()
        created = _generate(quote["quoteId"]).json()

        response = client.get(f"/api/proposals/{created['proposalId']}/pdf")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert created["filename"] in response.headers["content-disposition"]

    def test_pdf_endpoint_returns_stored_bytes_never_regenerated(self):
        quote = _create_quote()
        created = _generate(quote["quoteId"]).json()

        first = client.get(f"/api/proposals/{created['proposalId']}/pdf").content
        second = client.get(f"/api/proposals/{created['proposalId']}/pdf").content

        assert first == second
        assert first[:5] == b"%PDF-"

    def test_missing_proposal_returns_404(self):
        assert client.get("/api/proposals/P-does-not-exist").status_code == 404
        assert client.get("/api/proposals/P-does-not-exist/pdf").status_code == 404

    def test_missing_quote_returns_404_for_listing(self):
        response = client.get("/api/quotes/Q-does-not-exist/proposals")

        assert response.status_code == 404


class TestHistoricalFidelity:
    def test_proposal_survives_later_quote_revision(self):
        quote = _create_quote()
        p1 = _generate(quote["quoteId"]).json()
        original_price = p1["pricing"]["finalPrice"]

        alt_response = client.post(
            f"/api/quotes/{quote['quoteId']}/alternatives/manual",
            json={"name": "Trimmed Scope", "configuration": _configuration_payload(tier="core", users=5)},
        ).json()
        scenario_id = alt_response["scenarios"][0]["scenarioId"]
        client.put(
            f"/api/quotes/{quote['quoteId']}/alternatives/selection", json={"scenarioId": scenario_id}
        )
        client.post(f"/api/quotes/{quote['quoteId']}/revisions/from-selected-alternative")

        p2 = _generate(quote["quoteId"], expectedVersionNumber=2).json()

        reloaded_p1 = client.get(f"/api/proposals/{p1['proposalId']}").json()
        assert reloaded_p1["quoteVersionNumber"] == 1
        assert reloaded_p1["pricing"]["finalPrice"] == original_price

        reloaded_p2 = client.get(f"/api/proposals/{p2['proposalId']}").json()
        assert reloaded_p2["quoteVersionNumber"] == 2

        listed = client.get(f"/api/quotes/{quote['quoteId']}/proposals").json()
        assert {p["proposalId"] for p in listed} == {p1["proposalId"], p2["proposalId"]}
        assert {p["quoteVersionNumber"] for p in listed} == {1, 2}

        pdf1 = client.get(f"/api/proposals/{p1['proposalId']}/pdf").content
        pdf2 = client.get(f"/api/proposals/{p2['proposalId']}/pdf").content
        assert pdf1[:5] == b"%PDF-"
        assert pdf2[:5] == b"%PDF-"


class TestNoRecalculation:
    def test_generation_never_calls_the_pricing_engine(self, monkeypatch):
        """Proves generate_proposal builds its ProposalSnapshot purely
        from the committed QuoteVersion -- never recalculating."""
        quote = _create_quote()

        def _fail_if_called(*args, **kwargs):
            raise AssertionError("calculate_quote must never be called during proposal generation")

        monkeypatch.setattr(pricing_engine, "calculate_quote", _fail_if_called)

        response = _generate(quote["quoteId"])

        assert response.status_code == 201
