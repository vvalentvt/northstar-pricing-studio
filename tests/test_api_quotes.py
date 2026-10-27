"""Tests for the FastAPI Quote HTTP boundary (api/routers/quotes.py).

Each test overrides get_quote_repository with a SQLiteQuoteRepository
pointed at a pytest tmp_path file -- never the real data/northstar.db --
so these tests are isolated and prove the endpoint against a real
(temporary) SQLite file, not a mock.
"""

from pathlib import Path
import sys

from fastapi.testclient import TestClient
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from pricing_engine import calculate_quote, load_rules

from api.dependencies import get_quote_repository
from api.main import app
from persistence import SQLiteQuoteRepository

RULES = load_rules(ROOT / "config" / "pricing_rules.yaml")

client = TestClient(app)


@pytest.fixture(autouse=True)
def _quote_repository_override(tmp_path):
    repository = SQLiteQuoteRepository(tmp_path / "northstar.db")
    app.dependency_overrides[get_quote_repository] = lambda: repository
    yield repository
    app.dependency_overrides.pop(get_quote_repository, None)


def _configuration_payload(**overrides) -> dict:
    payload = dict(
        customerName="Acme",
        tier="core",
        users=5,
        coverage="national",
        historyYears=1,
        contractMonths=12,
        premiumSupport=False,
        implementationServices=False,
        renewal=False,
        requestedDiscountPercent=0,
    )
    payload.update(overrides)
    return payload


def _create_payload(**config_overrides) -> dict:
    return {
        "customerName": "Acme",
        "owner": "vinnie",
        "configuration": _configuration_payload(**config_overrides),
    }


def test_create_quote_returns_201_with_server_calculated_pricing():
    response = client.post("/api/quotes", json=_create_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["quoteId"].startswith("Q-")
    assert body["customerName"] == "Acme"
    assert body["owner"] == "vinnie"
    assert body["currentVersion"]["versionNumber"] == 1
    assert body["currentVersion"]["source"] == "initial"
    assert body["versionHistory"] == []


def test_create_quote_pricing_matches_direct_calculate_quote():
    from pricing_engine import QuoteRequest

    response = client.post("/api/quotes", json=_create_payload())
    body = response.json()

    direct_result = calculate_quote(
        QuoteRequest(
            customer_name="Acme",
            tier="core",
            users=5,
            coverage="national",
            history_years=1,
            contract_months=12,
        ),
        RULES,
    )

    assert body["currentVersion"]["pricing"]["finalPrice"] == direct_result.final_price
    assert body["currentVersion"]["pricing"]["ruleVersion"] == direct_result.rule_version


def test_create_quote_rejects_client_supplied_pricing_fields():
    payload = _create_payload()
    payload["configuration"]["finalPrice"] = 1.0
    payload["finalPrice"] = 1.0

    response = client.post("/api/quotes", json=payload)

    assert response.status_code == 201
    body = response.json()
    # Extra unrecognized fields are ignored by the DTO, never trusted as
    # the committed price -- the server-calculated price is what's stored.
    assert body["currentVersion"]["pricing"]["finalPrice"] != 1.0


def test_create_quote_invalid_configuration_returns_422():
    response = client.post("/api/quotes", json=_create_payload(tier="not-a-real-tier"))

    assert response.status_code == 422


def test_get_quote_returns_200_with_full_current_version():
    created = client.post("/api/quotes", json=_create_payload()).json()

    response = client.get(f"/api/quotes/{created['quoteId']}")

    assert response.status_code == 200
    body = response.json()
    assert body["quoteId"] == created["quoteId"]
    assert body["currentVersion"] == created["currentVersion"]


def test_get_quote_missing_returns_404():
    response = client.get("/api/quotes/Q-does-not-exist")

    assert response.status_code == 404


def test_get_quote_version_returns_200():
    created = client.post("/api/quotes", json=_create_payload()).json()

    response = client.get(f"/api/quotes/{created['quoteId']}/versions/1")

    assert response.status_code == 200
    body = response.json()
    assert body["versionNumber"] == 1
    assert body["source"] == "initial"


def test_get_quote_version_missing_quote_returns_404():
    response = client.get("/api/quotes/Q-does-not-exist/versions/1")

    assert response.status_code == 404


def test_get_quote_version_missing_version_returns_404_not_current_version():
    created = client.post("/api/quotes", json=_create_payload()).json()

    response = client.get(f"/api/quotes/{created['quoteId']}/versions/2")

    assert response.status_code == 404


def test_created_quote_persists_across_requests_on_same_repository(_quote_repository_override):
    created = client.post("/api/quotes", json=_create_payload()).json()

    reloaded = _quote_repository_override.get(created["quoteId"])

    assert reloaded.quote_id == created["quoteId"]
    assert reloaded.current_version.pricing_snapshot.final_price == (
        created["currentVersion"]["pricing"]["finalPrice"]
    )


def test_list_quotes_is_empty_list_when_none_exist():
    response = client.get("/api/quotes")

    assert response.status_code == 200
    assert response.json() == []


def test_list_quotes_returns_a_summary_for_each_created_quote():
    first = client.post("/api/quotes", json=_create_payload(customerName="Acme")).json()
    second = client.post("/api/quotes", json=_create_payload(customerName="Globex")).json()

    response = client.get("/api/quotes")

    assert response.status_code == 200
    ids = {entry["quoteId"] for entry in response.json()}
    assert ids == {first["quoteId"], second["quoteId"]}


def test_list_quotes_summary_matches_current_version_not_full_snapshot():
    created = client.post("/api/quotes", json=_create_payload()).json()

    response = client.get("/api/quotes")

    [entry] = response.json()
    assert entry["quoteId"] == created["quoteId"]
    assert entry["customerName"] == created["customerName"]
    assert entry["owner"] == created["owner"]
    assert entry["currentVersionNumber"] == 1
    assert entry["finalPrice"] == created["currentVersion"]["pricing"]["finalPrice"]
    assert entry["approvalRequired"] == created["currentVersion"]["pricing"]["approvalRequired"]
    # Never a full snapshot -- no configuration, no version history.
    assert "configuration" not in entry
    assert "versionHistory" not in entry
    assert "currentVersion" not in entry


def test_list_quotes_most_recently_created_first():
    import time

    first = client.post("/api/quotes", json=_create_payload(customerName="First")).json()
    time.sleep(0.05)
    second = client.post("/api/quotes", json=_create_payload(customerName="Second")).json()

    response = client.get("/api/quotes")

    ids = [entry["quoteId"] for entry in response.json()]
    assert ids.index(second["quoteId"]) < ids.index(first["quoteId"])
