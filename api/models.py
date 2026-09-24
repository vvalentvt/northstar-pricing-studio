"""HTTP request/response DTOs for the Northstar API.

These are transport shapes, not domain models: field names are
camelCase (matching normal JSON/JS convention) rather than the
domain's snake_case, and only the fields the frontend actually needs
are exposed. Nothing here contains pricing formulas, Budget Fit
scoring, or scenario logic -- see api/routers/budget_fit.py for the
translation to/from the real domain in src/budget_fit, src/quotes, and
src/pricing_engine.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ConfigurationDto(BaseModel):
    """The wire shape of one product/service configuration -- mirrors
    pricing_engine.QuoteRequest's fields, camelCased for the frontend."""

    model_config = ConfigDict(populate_by_name=True)

    customer_name: str = Field(alias="customerName", min_length=1)
    tier: str
    users: int = Field(ge=1)
    coverage: str
    history_years: int = Field(alias="historyYears")
    contract_months: int = Field(alias="contractMonths")
    premium_support: bool = Field(default=False, alias="premiumSupport")
    implementation_services: bool = Field(default=False, alias="implementationServices")
    renewal: bool = False
    requested_discount_percent: float = Field(
        default=0, ge=0, le=100, alias="requestedDiscountPercent"
    )


class ConstraintsDto(BaseModel):
    """Mirrors budget_fit.BudgetFitConstraints. `locked_fields` uses the
    same string values as BudgetFitField (e.g. "tier", "coverage")."""

    model_config = ConfigDict(populate_by_name=True)

    locked_fields: list[str] = Field(default_factory=list, alias="lockedFields")
    minimum_users: int | None = Field(default=None, ge=1, alias="minimumUsers")
    required_premium_support: bool = Field(default=False, alias="requiredPremiumSupport")
    required_implementation_services: bool = Field(
        default=False, alias="requiredImplementationServices"
    )


class BudgetFitRequestDto(BaseModel):
    """POST /api/budget-fit request body."""

    model_config = ConfigDict(populate_by_name=True)

    target_budget: float = Field(gt=0, alias="targetBudget")
    baseline_configuration: ConfigurationDto = Field(alias="baselineConfiguration")
    constraints: ConstraintsDto = Field(default_factory=ConstraintsDto)
    max_recommendations: int = Field(default=3, ge=1, le=5, alias="maxRecommendations")


class FieldChangeDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    field: str
    label: str
    baseline_value: str = Field(alias="baselineValue")
    candidate_value: str = Field(alias="candidateValue")


class RecommendationDto(BaseModel):
    """Only what the UI needs to render a recommendation card -- never a
    raw dump of the internal BudgetFitRecommendation model."""

    model_config = ConfigDict(populate_by_name=True)

    rank: int
    final_price: float = Field(alias="finalPrice")
    budget_headroom: float = Field(alias="budgetHeadroom")
    capability_preserved: float = Field(alias="capabilityPreserved")
    budget_utilization: float = Field(alias="budgetUtilization")
    approval_required: bool = Field(alias="approvalRequired")
    approval_reason: str | None = Field(default=None, alias="approvalReason")
    is_baseline: bool = Field(alias="isBaseline")
    configuration: ConfigurationDto
    changed_fields: list[FieldChangeDto] = Field(alias="changedFields")
    preserved_fields: list[str] = Field(alias="preservedFields")


class BudgetFitResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    target_budget: float = Field(alias="targetBudget")
    baseline_price: float = Field(alias="baselinePrice")
    feasible_candidate_count: int = Field(alias="feasibleCandidateCount")
    recommendations: list[RecommendationDto]
    no_fit_reason: str | None = Field(default=None, alias="noFitReason")


class ErrorResponseDto(BaseModel):
    """The one predictable error shape for 4xx/5xx responses."""

    detail: str
