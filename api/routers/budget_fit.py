"""Budget Fit HTTP endpoint.

Thin translation boundary only: converts BudgetFitRequestDto into the
existing domain's BudgetFitRequest / BudgetFitConstraints /
ConfigurationSnapshot, calls the existing find_budget_fit -- the sole
authority on search, feasibility, and ranking -- and translates the
resulting BudgetFitResult back into a response DTO. No pricing
formulas, Budget Fit scoring, or scenario logic is reimplemented here;
see src/budget_fit for the actual optimizer.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from budget_fit import (
    BudgetFitConstraints,
    BudgetFitField,
    BudgetFitRequest,
    BudgetFitResult,
    find_budget_fit,
)

from api.dependencies import get_pricing_rules
from api.dto_mapping import configuration_dto_to_snapshot, configuration_snapshot_to_dto
from api.models import (
    BudgetFitRequestDto,
    BudgetFitResponseDto,
    FieldChangeDto,
    RecommendationDto,
)

router = APIRouter(prefix="/api", tags=["budget-fit"])

#: Human-readable labels for BudgetFitField values -- presentation only.
#: Deliberately not imported from app/app_state.py: the API depends only
#: on src/ (see ADR-003 / the frontend -> api -> src diagram), never on
#: Streamlit's own application layer, so the two presentation layers
#: stay independent even though this small label dict is duplicated.
FIELD_LABELS: dict[str, str] = {
    "tier": "Tier",
    "users": "Users",
    "coverage": "Coverage",
    "history_years": "Historical depth",
    "contract_months": "Contract term",
    "renewal": "Renewal",
    "premium_support": "Premium support",
    "implementation_services": "Implementation services",
}


def _parse_locked_fields(values: list[str]) -> frozenset[BudgetFitField]:
    try:
        return frozenset(BudgetFitField(value) for value in values)
    except ValueError as exc:
        valid = ", ".join(field.value for field in BudgetFitField)
        raise HTTPException(
            status_code=422,
            detail=f"Invalid locked field: {exc}. Valid fields: {valid}",
        ) from exc


def _recommendation_to_dto(rec, target_budget: float) -> RecommendationDto:
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
                label=FIELD_LABELS.get(change.field.value, change.field.value),
                baselineValue=change.baseline_value,
                candidateValue=change.candidate_value,
            )
            for change in rec.changed_fields
        ],
        preservedFields=[
            FIELD_LABELS.get(field.value, field.value) for field in rec.preserved_fields
        ],
    )


@router.post("/budget-fit", response_model=BudgetFitResponseDto)
def post_budget_fit(request: BudgetFitRequestDto) -> BudgetFitResponseDto:
    """Run the real Budget Fit optimizer against a stateless baseline
    configuration supplied by the client.

    A valid no-fit outcome (recommendations=[], no_fit_reason set) is a
    normal 200 response, not an error -- only malformed/invalid input
    (unknown tier/coverage, an unknown locked field, ...) raises 422.
    """
    constraints = BudgetFitConstraints(
        locked_fields=_parse_locked_fields(request.constraints.locked_fields),
        minimum_users=request.constraints.minimum_users,
        required_premium_support=request.constraints.required_premium_support,
        required_implementation_services=request.constraints.required_implementation_services,
    )

    try:
        baseline = configuration_dto_to_snapshot(request.baseline_configuration)
        domain_request = BudgetFitRequest(
            target_budget=request.target_budget,
            baseline_configuration=baseline,
            constraints=constraints,
            max_recommendations=request.max_recommendations,
        )
        result: BudgetFitResult = find_budget_fit(domain_request, get_pricing_rules())
    except (ValidationError, ValueError) as exc:
        # ValidationError: a domain-model constraint the DTO didn't
        # already mirror. ValueError: e.g. calculate_quote rejecting an
        # unsupported tier/coverage value in the baseline configuration.
        # Both are client input problems, not server failures.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    recommendations = [
        _recommendation_to_dto(rec, request.target_budget) for rec in result.recommendations
    ]

    return BudgetFitResponseDto(
        targetBudget=result.target_budget,
        baselinePrice=result.baseline_price,
        feasibleCandidateCount=result.feasible_candidate_count,
        recommendations=recommendations,
        noFitReason=result.no_fit_reason,
    )
