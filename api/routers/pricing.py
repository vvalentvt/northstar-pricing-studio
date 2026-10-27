"""Pricing catalog + stateless preview endpoints.

Both derive from the same canonical pricing rules and the same
calculate_quote() engine every other pricing-aware endpoint uses:

- GET /api/pricing/options exposes the rule-driven catalog (tiers,
  coverage, discount guardrails, ...) so the frontend's Configure
  screen never hard-codes a second copy of config/pricing_rules.yaml.
- POST /api/pricing/preview runs a what-if calculation with no
  persistence: no Quote ID is generated, nothing is written to SQLite,
  no QuoteVersion is created. See api/routers/quotes.py for where a
  configuration actually becomes a durable, persisted Quote v1 -- this
  endpoint never does that; it exists purely so Configure can show the
  user a price before they commit to anything.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from pricing_engine import calculate_quote
from quotes import PricingSnapshot

from api.dependencies import get_pricing_rules
from api.dto_mapping import configuration_dto_to_request, pricing_snapshot_to_dto
from api.models import (
    ConfigurationDto,
    DiscountPolicyDto,
    PricingOptionsResponseDto,
    PricingSnapshotDto,
)

router = APIRouter(prefix="/api/pricing", tags=["pricing"])


@router.get("/options", response_model=PricingOptionsResponseDto)
def get_pricing_options() -> PricingOptionsResponseDto:
    rules = get_pricing_rules()
    return PricingOptionsResponseDto(
        ruleVersion=str(rules["version"]),
        tiers=list(rules["tiers"].keys()),
        coverage=list(rules["coverage"].keys()),
        historyYears=sorted(rules["history_years"].keys()),
        contractMonths=sorted(rules["contract_term"].keys()),
        includedUsers=rules["users"]["included"],
        discountPolicy=DiscountPolicyDto(
            selfServiceThresholdPercent=rules["discount_policy"]["max_self_service_percent"],
            maxAllowedDiscountPercent=rules["discount_policy"]["max_allowed_percent"],
        ),
    )


@router.post("/preview", response_model=PricingSnapshotDto)
def post_pricing_preview(configuration: ConfigurationDto) -> PricingSnapshotDto:
    """Stateless what-if calculation. Validates the configuration, runs
    it through the canonical pricing engine, and returns the result --
    persisting nothing."""
    try:
        request = configuration_dto_to_request(configuration)
        result = calculate_quote(request, get_pricing_rules())
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    pricing_snapshot = PricingSnapshot.from_pricing_result(result)
    return pricing_snapshot_to_dto(pricing_snapshot)
