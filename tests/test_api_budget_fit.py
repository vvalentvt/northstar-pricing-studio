"""Tests for the FastAPI Budget Fit HTTP boundary (api/routers/budget_fit.py).

These prove the endpoint is a correct, thin translation over the real
domain -- not a second implementation of search/ranking. Optimizer
behavior itself (feasibility, ranking, diversity, capability scoring) is
already covered by tests/test_budget_fit.py and is deliberately not
re-tested here; several tests below instead assert the endpoint's
numbers match a direct find_budget_fit call for the same request.
"""

from pathlib import Path
import sys

from fastapi.testclient import TestClient
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from budget_fit import BudgetFitConstraints, BudgetFitField, BudgetFitRequest, find_budget_fit
from pricing_engine import load_rules
from quotes import ConfigurationSnapshot

from api.main import app

RULES = load_rules(ROOT / "config" / "pricing_rules.yaml")

client = TestClient(app)


def _baseline_payload(**overrides) -> dict:
    payload = dict(
        customerName="Example Health Systems",
        tier="enterprise",
        users=10,
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


def _baseline_snapshot(**overrides) -> ConfigurationSnapshot:
    defaults = dict(
        customer_name="Example Health Systems",
        tier="enterprise",
        users=10,
        coverage="north_america",
        history_years=3,
        contract_months=24,
        premium_support=True,
        implementation_services=False,
        renewal=False,
        requested_discount_percent=0,
    )
    defaults.update(overrides)
    return ConfigurationSnapshot(**defaults)


def test_budget_fit_endpoint_returns_real_recommendations():
    response = client.post(
        "/api/budget-fit",
        json={
            "targetBudget": 45000,
            "baselineConfiguration": _baseline_payload(),
            "constraints": {"lockedFields": ["coverage"], "minimumUsers": 5},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["baselinePrice"] == pytest.approx(94320.0)
    assert body["feasibleCandidateCount"] > 0
    assert len(body["recommendations"]) == 3
    top = body["recommendations"][0]
    assert top["rank"] == 1
    assert top["finalPrice"] <= 45000
    assert 0 <= top["capabilityPreserved"] <= 1
    assert top["configuration"]["tier"] in RULES["tiers"]


def test_budget_fit_endpoint_respects_target_budget():
    response = client.post(
        "/api/budget-fit",
        json={"targetBudget": 30000, "baselineConfiguration": _baseline_payload()},
    )

    assert response.status_code == 200
    body = response.json()
    for rec in body["recommendations"]:
        assert rec["finalPrice"] <= 30000
        assert rec["budgetHeadroom"] == pytest.approx(30000 - rec["finalPrice"])


def test_budget_fit_endpoint_respects_locked_fields():
    response = client.post(
        "/api/budget-fit",
        json={
            "targetBudget": 45000,
            "baselineConfiguration": _baseline_payload(),
            "constraints": {"lockedFields": ["coverage"]},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommendations"]
    for rec in body["recommendations"]:
        assert rec["configuration"]["coverage"] == "north_america"


def test_budget_fit_endpoint_respects_minimum_users():
    response = client.post(
        "/api/budget-fit",
        json={
            "targetBudget": 100000,
            "baselineConfiguration": _baseline_payload(),
            "constraints": {"minimumUsers": 6},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommendations"]
    for rec in body["recommendations"]:
        assert rec["configuration"]["users"] >= 6


def test_budget_fit_endpoint_returns_no_fit_as_200():
    response = client.post(
        "/api/budget-fit",
        json={"targetBudget": 1000, "baselineConfiguration": _baseline_payload()},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommendations"] == []
    assert body["noFitReason"] is not None


def test_budget_fit_endpoint_returns_validation_error_for_invalid_budget():
    response = client.post(
        "/api/budget-fit",
        json={"targetBudget": 0, "baselineConfiguration": _baseline_payload()},
    )

    assert response.status_code == 422

    response = client.post(
        "/api/budget-fit",
        json={"targetBudget": -100, "baselineConfiguration": _baseline_payload()},
    )

    assert response.status_code == 422


def test_budget_fit_endpoint_returns_validation_error_for_unknown_locked_field():
    response = client.post(
        "/api/budget-fit",
        json={
            "targetBudget": 45000,
            "baselineConfiguration": _baseline_payload(),
            "constraints": {"lockedFields": ["not_a_real_field"]},
        },
    )

    assert response.status_code == 422


def test_budget_fit_endpoint_returns_validation_error_for_unsupported_tier():
    response = client.post(
        "/api/budget-fit",
        json={
            "targetBudget": 45000,
            "baselineConfiguration": _baseline_payload(tier="not_a_real_tier"),
        },
    )

    assert response.status_code == 422


def test_budget_fit_endpoint_does_not_mutate_domain_state():
    rules_before = load_rules(ROOT / "config" / "pricing_rules.yaml")

    client.post(
        "/api/budget-fit",
        json={
            "targetBudget": 45000,
            "baselineConfiguration": _baseline_payload(),
            "constraints": {"lockedFields": ["coverage"], "minimumUsers": 5},
        },
    )

    rules_after = load_rules(ROOT / "config" / "pricing_rules.yaml")
    assert rules_before == rules_after


def test_budget_fit_endpoint_matches_direct_domain_call():
    """The endpoint must be a pure translation layer -- its numbers for a
    given request must match calling find_budget_fit directly."""
    baseline = _baseline_snapshot(coverage="global", history_years=5)
    domain_request = BudgetFitRequest(
        target_budget=45000.0,
        baseline_configuration=baseline,
        constraints=BudgetFitConstraints(minimum_users=5),
    )
    direct_result = find_budget_fit(domain_request, RULES)

    response = client.post(
        "/api/budget-fit",
        json={
            "targetBudget": 45000,
            "baselineConfiguration": _baseline_payload(coverage="global", historyYears=5),
            "constraints": {"minimumUsers": 5},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["feasibleCandidateCount"] == direct_result.feasible_candidate_count
    assert len(body["recommendations"]) == len(direct_result.recommendations)
    for api_rec, domain_rec in zip(body["recommendations"], direct_result.recommendations):
        assert api_rec["finalPrice"] == pytest.approx(domain_rec.pricing_snapshot.final_price)
        assert api_rec["capabilityPreserved"] == pytest.approx(domain_rec.capability_score)
        assert api_rec["configuration"]["tier"] == domain_rec.configuration_snapshot.tier
        assert api_rec["configuration"]["users"] == domain_rec.configuration_snapshot.users


def test_budget_fit_endpoint_baseline_already_fits():
    baseline_payload = _baseline_payload(
        tier="core", users=5, coverage="national", historyYears=1, premiumSupport=False
    )
    baseline_price = client.post(
        "/api/budget-fit",
        json={"targetBudget": 1_000_000, "baselineConfiguration": baseline_payload},
    ).json()["baselinePrice"]

    response = client.post(
        "/api/budget-fit",
        json={"targetBudget": baseline_price + 5000, "baselineConfiguration": baseline_payload},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["recommendations"]) == 1
    assert body["recommendations"][0]["isBaseline"] is True
