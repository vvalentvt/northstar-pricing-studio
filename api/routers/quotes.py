"""Quote HTTP endpoints -- the durable-persistence boundary.

Thin translation only: v1 is always calculated server-side via the same
shared application.create_quote(...) that app/app_state.py's Streamlit
commit flow now delegates to (see src/application/quotes.py), so the
quote-commit algorithm is never duplicated between presentation layers
and a client can never supply its own PricingSnapshot. Persistence
(SQLiteQuoteRepository) stores exactly the domain decisions Quote/
QuoteVersion already made -- no pricing, approval, or version logic is
reimplemented here.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from application import create_quote
from persistence import (
    DuplicateQuoteError,
    QuoteNotFoundError,
    QuoteRepository,
    QuoteVersionNotFoundError,
)
from pricing_engine import QuoteRequest, calculate_quote, load_rules
from quotes import Quote, QuoteVersion

from api.dependencies import get_quote_repository
from api.models import (
    ConfigurationDto,
    CreateQuoteRequestDto,
    PricingSnapshotDto,
    AdjustmentDto,
    QuoteResponseDto,
    QuoteVersionResponseDto,
    QuoteVersionSummaryDto,
)

router = APIRouter(prefix="/api/quotes", tags=["quotes"])

ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = ROOT / "config" / "pricing_rules.yaml"


@lru_cache(maxsize=1)
def get_rules() -> dict:
    """The same canonical pricing-rule loader used everywhere else --
    never a second pricing configuration source."""
    return load_rules(RULES_PATH)


def _configuration_dto_to_request(dto: ConfigurationDto) -> QuoteRequest:
    return QuoteRequest(
        customer_name=dto.customer_name,
        tier=dto.tier,
        users=dto.users,
        coverage=dto.coverage,
        history_years=dto.history_years,
        contract_months=dto.contract_months,
        premium_support=dto.premium_support,
        implementation_services=dto.implementation_services,
        renewal=dto.renewal,
        requested_discount_percent=dto.requested_discount_percent,
    )


def _configuration_snapshot_to_dto(snapshot) -> ConfigurationDto:
    return ConfigurationDto(
        customerName=snapshot.customer_name,
        tier=snapshot.tier,
        users=snapshot.users,
        coverage=snapshot.coverage,
        historyYears=snapshot.history_years,
        contractMonths=snapshot.contract_months,
        premiumSupport=snapshot.premium_support,
        implementationServices=snapshot.implementation_services,
        renewal=snapshot.renewal,
        requestedDiscountPercent=snapshot.requested_discount_percent,
    )


def _pricing_snapshot_to_dto(pricing) -> PricingSnapshotDto:
    return PricingSnapshotDto(
        ruleVersion=pricing.rule_version,
        basePrice=pricing.base_price,
        adjustments=[
            AdjustmentDto(name=a.name, amount=a.amount, explanation=a.explanation)
            for a in pricing.adjustments
        ],
        subtotalBeforeDiscount=pricing.subtotal_before_discount,
        discountAmount=pricing.discount_amount,
        finalPrice=pricing.final_price,
        approvalRequired=pricing.approval_required,
        approvalReason=pricing.approval_reason,
        selfServiceThresholdPercent=pricing.self_service_threshold_percent,
        maxAllowedDiscountPercent=pricing.max_allowed_discount_percent,
        calculatedAt=pricing.calculated_at.isoformat(),
    )


def _version_to_response_dto(version: QuoteVersion) -> QuoteVersionResponseDto:
    return QuoteVersionResponseDto(
        versionNumber=version.version_number,
        source=version.source.value,
        createdAt=version.created_at.isoformat(),
        configuration=_configuration_snapshot_to_dto(version.configuration_snapshot),
        pricing=_pricing_snapshot_to_dto(version.pricing_snapshot),
    )


def _version_to_summary_dto(version: QuoteVersion) -> QuoteVersionSummaryDto:
    return QuoteVersionSummaryDto(
        versionNumber=version.version_number,
        source=version.source.value,
        createdAt=version.created_at.isoformat(),
        finalPrice=version.pricing_snapshot.final_price,
        approvalRequired=version.pricing_snapshot.approval_required,
    )


def _quote_to_response_dto(quote: Quote) -> QuoteResponseDto:
    return QuoteResponseDto(
        quoteId=quote.quote_id,
        customerName=quote.customer_name,
        owner=quote.owner,
        status=quote.status,
        createdAt=quote.created_at.isoformat(),
        currentVersion=_version_to_response_dto(quote.current_version),
        versionHistory=[_version_to_summary_dto(v) for v in quote.versions[:-1]],
    )


@router.post("", response_model=QuoteResponseDto, status_code=201)
def create_quote_endpoint(
    request: CreateQuoteRequestDto,
    repository: QuoteRepository = Depends(get_quote_repository),
) -> QuoteResponseDto:
    """Calculate v1 server-side via the canonical pricing engine and
    persist it. The client supplies a configuration, never a price."""
    try:
        configuration = _configuration_dto_to_request(request.configuration)
        result = calculate_quote(configuration, get_rules())
        quote = create_quote(
            customer_name=request.customer_name,
            owner=request.owner,
            configuration=configuration,
            result=result,
        )
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        repository.create(quote)
    except DuplicateQuoteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _quote_to_response_dto(quote)


@router.get("/{quote_id}", response_model=QuoteResponseDto)
def get_quote_endpoint(
    quote_id: str,
    repository: QuoteRepository = Depends(get_quote_repository),
) -> QuoteResponseDto:
    try:
        quote = repository.get(quote_id)
    except QuoteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _quote_to_response_dto(quote)


@router.get("/{quote_id}/versions/{version_number}", response_model=QuoteVersionResponseDto)
def get_quote_version_endpoint(
    quote_id: str,
    version_number: int,
    repository: QuoteRepository = Depends(get_quote_repository),
) -> QuoteVersionResponseDto:
    try:
        version = repository.get_version(quote_id, version_number)
    except (QuoteNotFoundError, QuoteVersionNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _version_to_response_dto(version)
