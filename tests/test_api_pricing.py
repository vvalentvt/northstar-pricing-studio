"""Tests for the FastAPI pricing catalog + preview endpoints
(api/routers/pricing.py).

GET /api/pricing/options and POST /api/pricing/preview are compared
against values loaded directly via pricing_engine.load_rules() and
pricing_engine.calculate_quote() -- if the endpoint ever hard-coded a
second, parallel catalog instead of deriving it from the canonical
rules, these equality assertions would catch the drift.
"""

import sqlite3
from pathlib import Path
import sys

from fastapi.testclient import TestClient
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from pricing_engine import QuoteRequest, calculate_quote, load_rules

from api.dependencies import get_quote_repository
from api.main import app
from persistence import SQLiteQuoteRepository

RULES = load_rules(ROOT / "config" / "pricing_rules.yaml")

client = TestClient(app)


@pytest.fixture(autouse=True)
def _quote_repository_override(tmp_path):
    db_path = tmp_path / "northstar.db"
    repository = SQLiteQuoteRepository(db_path)
    app.dependency_overrides[get_quote_repository] = lambda: repository
    yield repository, db_path
    app.dependency_overrides.pop(get_quote_repository, None)


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


def _direct_result(**overrides):
    defaults = dict(
        customer_name="Acme",
        tier="growth",
        users=8,
        coverage="north_america",
        history_years=3,
        contract_months=24,
        premium_support=True,
        implementation_services=False,
        renewal=False,
        requested_discount_percent=0,
    )
    defaults.update(overrides)
    return calculate_quote(QuoteRequest(**defaults), RULES)


class TestPricingOptions:
    def test_pricing_options_returns_active_rule_version(self):
        response = client.get("/api/pricing/options")

        assert response.status_code == 200
        assert response.json()["ruleVersion"] == str(RULES["version"])

    def test_pricing_options_returns_supported_tiers(self):
        response = client.get("/api/pricing/options")

        assert response.json()["tiers"] == list(RULES["tiers"].keys())

    def test_pricing_options_returns_supported_coverage(self):
        response = client.get("/api/pricing/options")

        assert response.json()["coverage"] == list(RULES["coverage"].keys())

    def test_pricing_options_returns_history_years(self):
        response = client.get("/api/pricing/options")

        assert response.json()["historyYears"] == sorted(RULES["history_years"].keys())

    def test_pricing_options_returns_contract_terms(self):
        response = client.get("/api/pricing/options")

        assert response.json()["contractMonths"] == sorted(RULES["contract_term"].keys())

    def test_pricing_options_returns_discount_guardrails(self):
        response = client.get("/api/pricing/options")

        body = response.json()
        assert body["includedUsers"] == RULES["users"]["included"]
        assert (
            body["discountPolicy"]["selfServiceThresholdPercent"]
            == RULES["discount_policy"]["max_self_service_percent"]
        )
        assert (
            body["discountPolicy"]["maxAllowedDiscountPercent"]
            == RULES["discount_policy"]["max_allowed_percent"]
        )


class TestPricingPreview:
    def test_pricing_preview_returns_200_for_valid_configuration(self):
        response = client.post("/api/pricing/preview", json=_configuration_payload())

        assert response.status_code == 200
        assert response.json()["finalPrice"] > 0

    def test_pricing_preview_matches_direct_calculate_quote(self):
        response = client.post("/api/pricing/preview", json=_configuration_payload())

        direct = _direct_result()
        body = response.json()
        assert body["finalPrice"] == direct.final_price
        assert body["ruleVersion"] == direct.rule_version
        assert body["basePrice"] == direct.list_price
        assert body["subtotalBeforeDiscount"] == direct.subtotal_before_discount

    def test_pricing_preview_returns_approval_state(self):
        response = client.post(
            "/api/pricing/preview", json=_configuration_payload(requestedDiscountPercent=18)
        )

        body = response.json()
        assert body["approvalRequired"] is True
        assert body["approvalReason"] is not None

    def test_pricing_preview_rejects_invalid_configuration(self):
        response = client.post(
            "/api/pricing/preview", json=_configuration_payload(tier="not-a-real-tier")
        )

        assert response.status_code == 422

    def test_pricing_preview_does_not_create_quote(self, _quote_repository_override):
        _repository, db_path = _quote_repository_override

        client.post("/api/pricing/preview", json=_configuration_payload())

        conn = sqlite3.connect(db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM quotes").fetchone()[0]
        finally:
            conn.close()
        assert count == 0

    def test_pricing_preview_does_not_write_to_repository(self, _quote_repository_override):
        _repository, db_path = _quote_repository_override

        client.post("/api/pricing/preview", json=_configuration_payload())

        conn = sqlite3.connect(db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM quote_versions").fetchone()[0]
        finally:
            conn.close()
        assert count == 0


def test_preview_and_created_quote_match_under_same_rules():
    """The focused parity test: under unchanged pricing rules, a preview
    and the Quote subsequently created from the same configuration must
    report the same commercial facts. The committed Quote is still what
    the frontend trusts -- this just proves the server never lets the
    two diverge for the same input."""
    configuration_payload = _configuration_payload()

    preview = client.post("/api/pricing/preview", json=configuration_payload).json()
    created = client.post(
        "/api/quotes",
        json={"customerName": "Acme", "owner": "Vincent", "configuration": configuration_payload},
    ).json()

    committed_pricing = created["currentVersion"]["pricing"]
    assert committed_pricing["finalPrice"] == preview["finalPrice"]
    assert committed_pricing["discountAmount"] == preview["discountAmount"]
    assert committed_pricing["approvalRequired"] == preview["approvalRequired"]
    assert committed_pricing["ruleVersion"] == preview["ruleVersion"]
