"""Shared DTO <-> domain conversions used by more than one router.

Kept separate from any single router (budget_fit.py, quotes.py,
pricing.py all need these) so adding a new pricing-aware endpoint never
means re-deriving the same field-by-field mapping a third time. No
pricing, approval, or scoring logic lives here -- only the translation
between wire DTOs (api/models.py) and the existing domain models
(src/pricing_engine, src/quotes).
"""

from __future__ import annotations

from pricing_engine import QuoteRequest
from quotes import ConfigurationSnapshot, PricingSnapshot

from api.models import AdjustmentDto, ConfigurationDto, PricingSnapshotDto


def configuration_dto_to_request(dto: ConfigurationDto) -> QuoteRequest:
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


def configuration_dto_to_snapshot(dto: ConfigurationDto) -> ConfigurationSnapshot:
    return ConfigurationSnapshot(
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


def configuration_snapshot_to_dto(snapshot: ConfigurationSnapshot) -> ConfigurationDto:
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


def pricing_snapshot_to_dto(pricing: PricingSnapshot) -> PricingSnapshotDto:
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
