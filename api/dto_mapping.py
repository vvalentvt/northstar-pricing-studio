"""Shared DTO <-> domain conversions used by more than one router.

Kept separate from any single router (budget_fit.py, quotes.py,
pricing.py all need these) so adding a new pricing-aware endpoint never
means re-deriving the same field-by-field mapping a third time. No
pricing, approval, or scoring logic lives here -- only the translation
between wire DTOs (api/models.py) and the existing domain models
(src/pricing_engine, src/quotes).
"""

from __future__ import annotations

from fastapi import HTTPException

from budget_fit import BudgetFitField, BudgetFitRecommendation
from pricing_engine import QuoteRequest
from proposals import Proposal
from quotes import ConfigurationSnapshot, NegotiationContext, PricingSnapshot, QuoteSummary, Scenario

from api.models import (
    AdjustmentDto,
    ConfigurationDto,
    FieldChangeDto,
    NegotiationContextDto,
    PricingSnapshotDto,
    ProposalNarrativeDto,
    ProposalResponseDto,
    ProposalSummaryDto,
    QuoteSummaryDto,
    RecommendationDto,
    ScenarioDto,
)

#: Human-readable labels for BudgetFitField values -- presentation only.
#: Deliberately not imported from src/application/scenarios.py: the API
#: depends only on src/ (see ADR-003), never on another presentation
#: layer's formatting choices, so this small label dict is kept local
#: rather than coupling two presentation layers together.
BUDGET_FIT_FIELD_LABELS: dict[str, str] = {
    "tier": "Tier",
    "users": "Users",
    "coverage": "Coverage",
    "history_years": "Historical depth",
    "contract_months": "Contract term",
    "renewal": "Renewal",
    "premium_support": "Premium support",
    "implementation_services": "Implementation services",
}


def parse_locked_fields(values: list[str]) -> frozenset[BudgetFitField]:
    try:
        return frozenset(BudgetFitField(value) for value in values)
    except ValueError as exc:
        valid = ", ".join(field.value for field in BudgetFitField)
        raise HTTPException(
            status_code=422,
            detail=f"Invalid locked field: {exc}. Valid fields: {valid}",
        ) from exc


def recommendation_to_dto(rec: BudgetFitRecommendation, target_budget: float) -> RecommendationDto:
    return RecommendationDto(
        rank=rec.rank,
        finalPrice=rec.pricing_snapshot.final_price,
        budgetHeadroom=target_budget - rec.pricing_snapshot.final_price,
        capabilityPreserved=rec.capability_score,
        budgetUtilization=rec.budget_utilization,
        approvalRequired=rec.pricing_snapshot.approval_required,
        approvalReason=rec.pricing_snapshot.approval_reason,
        isBaseline=rec.is_baseline,
        configuration=configuration_snapshot_to_dto(rec.configuration_snapshot),
        changedFields=[
            FieldChangeDto(
                field=change.field.value,
                label=BUDGET_FIT_FIELD_LABELS.get(change.field.value, change.field.value),
                baselineValue=change.baseline_value,
                candidateValue=change.candidate_value,
            )
            for change in rec.changed_fields
        ],
        preservedFields=[
            BUDGET_FIT_FIELD_LABELS.get(field.value, field.value) for field in rec.preserved_fields
        ],
    )


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


def negotiation_context_to_dto(context: NegotiationContext) -> NegotiationContextDto:
    return NegotiationContextDto(
        targetBudget=context.target_budget,
        requiredAttributes=list(context.required_attributes),
        flexibleAttributes=list(context.flexible_attributes),
    )


def scenario_to_dto(scenario: Scenario) -> ScenarioDto:
    return ScenarioDto(
        scenarioId=scenario.scenario_id,
        name=scenario.name,
        source=scenario.source.value,
        configuration=configuration_snapshot_to_dto(scenario.configuration_snapshot),
        pricing=pricing_snapshot_to_dto(scenario.pricing_snapshot),
        negotiationContext=(
            negotiation_context_to_dto(scenario.negotiation_context)
            if scenario.negotiation_context is not None
            else None
        ),
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


def quote_summary_to_dto(summary: QuoteSummary) -> QuoteSummaryDto:
    return QuoteSummaryDto(
        quoteId=summary.quote_id,
        customerName=summary.customer_name,
        owner=summary.owner,
        status=summary.status,
        createdAt=summary.created_at.isoformat(),
        currentVersionNumber=summary.current_version_number,
        finalPrice=summary.final_price,
        approvalRequired=summary.approval_required,
    )


def proposal_to_response_dto(proposal: Proposal) -> ProposalResponseDto:
    snapshot = proposal.snapshot
    return ProposalResponseDto(
        proposalId=proposal.proposal_id,
        quoteId=proposal.quote_id,
        quoteVersionNumber=proposal.quote_version_number,
        createdAt=proposal.created_at.isoformat(),
        templateVersion=proposal.template_version,
        filename=proposal.filename,
        customerName=snapshot.customer_name,
        owner=snapshot.owner,
        narrative=ProposalNarrativeDto(
            proposalTitle=snapshot.narrative.proposal_title,
            executiveSummary=snapshot.narrative.executive_summary,
            commercialNotes=snapshot.narrative.commercial_notes,
            validThrough=snapshot.narrative.valid_through,
        ),
        configuration=configuration_snapshot_to_dto(snapshot.configuration_snapshot),
        pricing=pricing_snapshot_to_dto(snapshot.pricing_snapshot),
    )


def proposal_to_summary_dto(proposal: Proposal) -> ProposalSummaryDto:
    return ProposalSummaryDto(
        proposalId=proposal.proposal_id,
        quoteVersionNumber=proposal.quote_version_number,
        createdAt=proposal.created_at.isoformat(),
        templateVersion=proposal.template_version,
        filename=proposal.filename,
    )
