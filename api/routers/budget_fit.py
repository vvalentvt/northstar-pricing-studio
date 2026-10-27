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
    BudgetFitRequest,
    BudgetFitResult,
    find_budget_fit,
)

from api.dependencies import get_pricing_rules
from api.dto_mapping import configuration_dto_to_snapshot, parse_locked_fields, recommendation_to_dto
from api.models import BudgetFitRequestDto, BudgetFitResponseDto

router = APIRouter(prefix="/api", tags=["budget-fit"])


@router.post("/budget-fit", response_model=BudgetFitResponseDto)
def post_budget_fit(request: BudgetFitRequestDto) -> BudgetFitResponseDto:
    """Run the real Budget Fit optimizer against a stateless baseline
    configuration supplied by the client.

    A valid no-fit outcome (recommendations=[], no_fit_reason set) is a
    normal 200 response, not an error -- only malformed/invalid input
    (unknown tier/coverage, an unknown locked field, ...) raises 422.
    """
    constraints = BudgetFitConstraints(
        locked_fields=parse_locked_fields(request.constraints.locked_fields),
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
        recommendation_to_dto(rec, request.target_budget) for rec in result.recommendations
    ]

    return BudgetFitResponseDto(
        targetBudget=result.target_budget,
        baselinePrice=result.baseline_price,
        feasibleCandidateCount=result.feasible_candidate_count,
        recommendations=recommendations,
        noFitReason=result.no_fit_reason,
    )
