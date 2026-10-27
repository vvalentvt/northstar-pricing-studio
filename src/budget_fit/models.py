from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from quotes import ConfigurationSnapshot, PricingSnapshot


class BudgetFitField(str, Enum):
    """The QuoteRequest configuration dimensions Budget Fit can search or
    constrain. Deliberately excludes `requested_discount_percent` -- see
    ADR-002 / docs: Budget Fit solves budget problems through product and
    service configuration before discretionary discount, so discount is
    never a search dimension in this phase and has no enum member here."""

    TIER = "tier"
    USERS = "users"
    COVERAGE = "coverage"
    HISTORY_YEARS = "history_years"
    CONTRACT_MONTHS = "contract_months"
    RENEWAL = "renewal"
    PREMIUM_SUPPORT = "premium_support"
    IMPLEMENTATION_SERVICES = "implementation_services"


class BudgetFitConstraints(BaseModel):
    """Machine-readable customer requirements for one Budget Fit search.

    Deliberately small and typed rather than a generic constraint-
    expression language: a field is either locked to the baseline's exact
    value, given a numeric floor (users only -- the one field with a
    natural "at least N" business meaning), or, for the two optional
    services, required to be present. Everything else is fully flexible
    across its rule-derived domain by default.
    """

    model_config = ConfigDict(frozen=True)

    locked_fields: frozenset[BudgetFitField] = Field(default_factory=frozenset)
    minimum_users: int | None = Field(default=None, ge=1)
    required_premium_support: bool = False
    required_implementation_services: bool = False


class BudgetFitRequest(BaseModel):
    """One Budget Fit search request.

    target_budget is a plain float, matching every monetary value already
    used throughout the pricing engine and quote domain (QuoteResult,
    PricingSnapshot, ...) -- introducing Decimal here would create a type
    mismatch at the exact point candidates are compared against
    QuoteResult.final_price, without a corresponding change anywhere else
    in the existing pricing code.

    baseline_configuration is an existing immutable ConfigurationSnapshot
    (never live in-memory UI state), so a search is always anchored to a
    specific committed or evaluated commercial decision.
    """

    model_config = ConfigDict(frozen=True)

    target_budget: float = Field(gt=0)
    baseline_configuration: ConfigurationSnapshot
    constraints: BudgetFitConstraints = Field(default_factory=BudgetFitConstraints)
    max_recommendations: int = Field(default=3, ge=1, le=5)


class CapabilityComponent(BaseModel):
    """One dimension's contribution to a candidate's capability score."""

    model_config = ConfigDict(frozen=True)

    field: BudgetFitField
    score: float = Field(ge=0, le=1)


class FieldChange(BaseModel):
    """A single "baseline value -> candidate value" difference, already
    formatted as plain commercial language (never raw multipliers/keys)."""

    model_config = ConfigDict(frozen=True)

    field: BudgetFitField
    baseline_value: str
    candidate_value: str


class BudgetFitRecommendation(BaseModel):
    """One ranked, explainable Budget Fit candidate.

    Composed from the domain's own immutable ConfigurationSnapshot /
    PricingSnapshot -- the same types a QuoteVersion or Scenario already
    uses -- so nothing here is a parallel pricing representation, and a
    future Phase 4C can build a Scenario directly from these two fields
    without any conversion.
    """

    model_config = ConfigDict(frozen=True)

    configuration_snapshot: ConfigurationSnapshot
    pricing_snapshot: PricingSnapshot
    rank: int = Field(ge=1)
    capability_score: float = Field(ge=0, le=1)
    capability_breakdown: tuple[CapabilityComponent, ...]
    budget_utilization: float = Field(ge=0)
    changed_fields: tuple[FieldChange, ...]
    preserved_fields: tuple[BudgetFitField, ...]
    is_baseline: bool = False

    @property
    def change_count(self) -> int:
        return len(self.changed_fields)


class BudgetFitResult(BaseModel):
    """The outcome of one Budget Fit search -- always a valid result, even
    when nothing fits (see no_fit_reason); only request validation
    (target_budget <= 0, etc.) raises."""

    model_config = ConfigDict(frozen=True)

    target_budget: float
    baseline_price: float
    evaluated_candidate_count: int = Field(ge=0)
    feasible_candidate_count: int = Field(ge=0)
    recommendations: tuple[BudgetFitRecommendation, ...]
    no_fit_reason: str | None = None
