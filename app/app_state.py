"""Pure application-layer state and orchestration logic for the Streamlit UI.

Deliberately has no dependency on `streamlit` so it can be unit tested like
any other Python module. `app_session.py` is the thin layer that wires these
types into `st.session_state`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from application.quotes import create_quote as _create_quote
from application.quotes import generate_quote_id as _generate_quote_id
from budget_fit import (
    BudgetFitConstraints,
    BudgetFitField,
    BudgetFitRecommendation,
    BudgetFitRequest,
    BudgetFitResult,
    find_budget_fit,
)
from pricing_engine import QuoteRequest, QuoteResult, calculate_quote
from quotes import (
    AdjustmentSnapshot,
    ConfigurationSnapshot,
    NegotiationContext,
    PricingSnapshot,
    Quote,
    QuoteVersion,
    Scenario,
    ScenarioSource,
    ScenarioWorkspace,
)

DEFAULT_OWNER = "You"


class DealType(str, Enum):
    NEW_BUSINESS = "new_business"
    RENEWAL = "renewal"


DEAL_TYPE_LABELS: dict[DealType, str] = {
    DealType.NEW_BUSINESS: "New Business",
    DealType.RENEWAL: "Renewal",
}


class WorkflowStep(str, Enum):
    DEAL_SETUP = "deal_setup"
    CONFIGURE = "configure"
    REVIEW_PRICING = "review_pricing"
    PROPOSAL = "proposal"


WORKFLOW_STEP_ORDER: tuple[WorkflowStep, ...] = (
    WorkflowStep.DEAL_SETUP,
    WorkflowStep.CONFIGURE,
    WorkflowStep.REVIEW_PRICING,
    WorkflowStep.PROPOSAL,
)

WORKFLOW_STEP_LABELS: dict[WorkflowStep, str] = {
    WorkflowStep.DEAL_SETUP: "Deal Setup",
    WorkflowStep.CONFIGURE: "Configure",
    WorkflowStep.REVIEW_PRICING: "Review Pricing",
    WorkflowStep.PROPOSAL: "Proposal",
}


@dataclass(frozen=True)
class DealContext:
    customer_name: str
    deal_type: DealType
    opportunity_reference: str = ""


@dataclass(frozen=True)
class ConfigurationInput:
    """Editable draft configuration state for the Configure step.

    Distinct from `QuoteRequest`: this is unfinished form state that may
    change on every rerun, whereas `QuoteRequest` is the validated input
    handed to the pricing engine at calculation time.
    """

    tier: str
    users: int
    coverage: str
    history_years: int
    contract_months: int
    premium_support: bool = False
    implementation_services: bool = False
    renewal: bool = False
    requested_discount_percent: float = 0.0


@dataclass(frozen=True)
class PricingState:
    """A QuoteResult paired with the exact inputs that produced it.

    Keeping the source inputs alongside the result is what lets the UI
    detect that a result has gone stale relative to the current form state.
    """

    result: QuoteResult
    customer_name: str
    configuration: ConfigurationInput


def validate_deal_context(
    customer_name: str, deal_type: str, opportunity_reference: str
) -> DealContext:
    if not customer_name or not customer_name.strip():
        raise ValueError("Customer name is required.")
    return DealContext(
        customer_name=customer_name.strip(),
        deal_type=DealType(deal_type),
        opportunity_reference=opportunity_reference.strip(),
    )


def configuration_to_quote_request(
    customer_name: str, configuration: ConfigurationInput
) -> QuoteRequest:
    return QuoteRequest(
        customer_name=customer_name,
        tier=configuration.tier,
        users=configuration.users,
        coverage=configuration.coverage,
        history_years=configuration.history_years,
        contract_months=configuration.contract_months,
        premium_support=configuration.premium_support,
        implementation_services=configuration.implementation_services,
        renewal=configuration.renewal,
        requested_discount_percent=configuration.requested_discount_percent,
    )


def calculate_pricing(
    customer_name: str, configuration: ConfigurationInput, rules: dict
) -> QuoteResult:
    """The only place the UI calls into the canonical pricing engine."""
    request = configuration_to_quote_request(customer_name, configuration)
    return calculate_quote(request, rules)


def is_stale(
    pricing_state: PricingState | None,
    customer_name: str,
    configuration: ConfigurationInput,
) -> bool:
    """True if a previously calculated result no longer matches the form.

    False both when nothing has been calculated yet (that's "not
    calculated", a different UI state) and when the result still matches.
    """
    if pricing_state is None:
        return False
    return (
        pricing_state.customer_name != customer_name
        or pricing_state.configuration != configuration
    )


def derive_status_label(quote: Quote | None) -> str:
    """DRAFT until a Quote has actually been committed (see commit_quote).

    Deliberately reads the durable Quote, not the live draft PricingState:
    the badge reflects the commercial decision, not an in-progress
    calculation that hasn't been proceeded past Configure yet.
    """
    if quote is None:
        return "DRAFT"
    if quote.current_version.pricing_snapshot.approval_required:
        return "NEEDS APPROVAL"
    return "PRICED"


def generate_quote_id() -> str:
    return _generate_quote_id()


def create_quote(
    deal_context: DealContext,
    configuration: ConfigurationInput,
    result: QuoteResult,
) -> Quote:
    """Build the durable in-memory Quote from a calculated configuration.

    Delegates to src/application/quotes.py -- the same presentation-
    neutral quote-commit algorithm the API (api/) uses, so Streamlit and
    FastAPI never carry two implementations of "how a Quote gets
    created." This function only translates Streamlit's own draft
    shapes (DealContext, ConfigurationInput) into the plain
    QuoteRequest the shared function takes. Not called directly by the
    UI -- see commit_quote, the one place this is invoked.
    """
    request = configuration_to_quote_request(deal_context.customer_name, configuration)
    return _create_quote(
        customer_name=deal_context.customer_name,
        owner=DEFAULT_OWNER,
        configuration=request,
        result=result,
    )


class CommitError(ValueError):
    """Raised when the current draft state cannot be committed to Review."""


def configuration_input_from_snapshot(snapshot: ConfigurationSnapshot) -> ConfigurationInput:
    return ConfigurationInput(
        tier=snapshot.tier,
        users=snapshot.users,
        coverage=snapshot.coverage,
        history_years=snapshot.history_years,
        contract_months=snapshot.contract_months,
        premium_support=snapshot.premium_support,
        implementation_services=snapshot.implementation_services,
        renewal=snapshot.renewal,
        requested_discount_percent=snapshot.requested_discount_percent,
    )


def committed_configuration_matches(
    quote: Quote | None, pricing_state: PricingState | None
) -> bool:
    """True if `quote`'s committed v1 reflects exactly this `pricing_state`."""
    if quote is None or pricing_state is None:
        return False
    committed_configuration = configuration_input_from_snapshot(
        quote.current_version.configuration_snapshot
    )
    return (
        committed_configuration == pricing_state.configuration
        and quote.current_version.pricing_snapshot.final_price == pricing_state.result.final_price
    )


def commit_quote(
    quote: Quote | None,
    deal_context: DealContext,
    pricing_state: PricingState | None,
    stale: bool,
) -> Quote:
    """The one place a durable Quote / QuoteVersion v1 is created.

    This is the commitment boundary described in ADR-001: Configure
    calculations are draft state (PricingState) until the user explicitly
    proceeds to Review Pricing. Calling this repeatedly with an unchanged,
    non-stale pricing_state is idempotent -- it returns the already
    -committed Quote rather than creating a new one. If a Quote is already
    committed and the current pricing_state reflects a *different*
    calculation, this refuses to silently replace that history and raises
    CommitError instead (this phase does not implement appending a new
    QuoteVersion).
    """
    if pricing_state is None:
        raise CommitError("Calculate a quote before proceeding to Review Pricing.")
    if stale:
        raise CommitError(
            "Configuration has changed since the last calculation. Recalculate "
            "before proceeding to Review Pricing."
        )
    if quote is not None:
        if committed_configuration_matches(quote, pricing_state):
            return quote
        raise CommitError(
            f"{quote.quote_id} is already committed as v{quote.current_version.version_number} "
            "with different pricing. Updating a committed quote isn't supported in this phase."
        )
    return create_quote(deal_context, pricing_state.configuration, pricing_state.result)


def format_money(amount: float, *, signed: bool = False) -> str:
    """The one consistent money formatter (whole-dollar, comma-grouped).

    signed=True prepends +/- so callers never hand-roll a sign themselves.
    """
    if signed:
        sign = "+" if amount > 0 else "-" if amount < 0 else ""
        return f"{sign}${abs(amount):,.0f}"
    return f"${amount:,.0f}"


@dataclass(frozen=True)
class ReviewPricingState:
    """Presentation-ready facts for the Review Pricing screen.

    Every field here is a direct read from the committed QuoteVersion
    (configuration_snapshot / pricing_snapshot) or from the active rule
    set -- nothing here recalculates a price.
    """

    quote_id: str
    version_number: int
    status_label: str
    configuration: ConfigurationSnapshot
    base_price: float
    adjustments: tuple[AdjustmentSnapshot, ...]
    subtotal_before_discount: float
    discount_amount: float
    final_price: float
    approval_required: bool
    approval_reason: str | None
    requested_discount_percent: float
    self_service_threshold_percent: float
    max_allowed_discount_percent: float
    rule_version: str
    calculated_at: datetime

    @property
    def proposal_available(self) -> bool:
        return not self.approval_required


def build_review_pricing(quote: Quote) -> ReviewPricingState:
    """Transform a committed Quote into presentation-ready view data.

    Reads exclusively from quote.current_version -- never draft state and
    never the currently active rules. Authority thresholds come from the
    PricingSnapshot, which preserved the policy values that were active
    when this QuoteVersion was calculated, so a historical quote stays
    explainable even after the active pricing YAML changes.
    """
    version = quote.current_version
    snapshot = version.pricing_snapshot
    configuration = version.configuration_snapshot
    return ReviewPricingState(
        quote_id=quote.quote_id,
        version_number=version.version_number,
        status_label=derive_status_label(quote),
        configuration=configuration,
        base_price=snapshot.base_price,
        adjustments=snapshot.adjustments,
        subtotal_before_discount=snapshot.subtotal_before_discount,
        discount_amount=snapshot.discount_amount,
        final_price=snapshot.final_price,
        approval_required=snapshot.approval_required,
        approval_reason=snapshot.approval_reason,
        requested_discount_percent=configuration.requested_discount_percent,
        self_service_threshold_percent=snapshot.self_service_threshold_percent,
        max_allowed_discount_percent=snapshot.max_allowed_discount_percent,
        rule_version=snapshot.rule_version,
        calculated_at=snapshot.calculated_at,
    )


class ScenarioError(ValueError):
    """Raised when a scenario draft cannot be saved into the workspace."""


def create_scenario_workspace(quote: Quote) -> ScenarioWorkspace:
    """Anchor a new exploration workspace to the committed QuoteVersion.

    Scenarios are exploratory alternatives to this specific version; the
    workspace records exactly which version they were explored against.
    """
    return ScenarioWorkspace(
        quote_id=quote.quote_id,
        base_version_number=quote.current_version.version_number,
    )


def create_manual_scenario(
    name: str,
    workspace: ScenarioWorkspace,
    pricing_state: PricingState | None,
    stale: bool,
) -> Scenario:
    """Save an evaluated scenario draft into the workspace.

    Mirrors commit_quote's shape: validates preconditions (name required,
    pricing must exist and be non-stale), builds the Scenario using the
    same snapshot conversions the domain already uses (ConfigurationSnapshot
    / PricingSnapshot), and appends it to the workspace via
    ScenarioWorkspace.add_scenario. Never touches Quote or QuoteVersion --
    an approval-required scenario is a valid alternative and may be saved.
    """
    if not name or not name.strip():
        raise ScenarioError("Scenario name is required before saving.")
    if pricing_state is None:
        raise ScenarioError("Calculate the scenario before saving.")
    if stale:
        raise ScenarioError(
            "Configuration has changed since the last calculation. Recalculate "
            "before saving."
        )
    request = configuration_to_quote_request(
        pricing_state.customer_name, pricing_state.configuration
    )
    configuration_snapshot = ConfigurationSnapshot.from_request(request)
    pricing_snapshot = PricingSnapshot.from_pricing_result(pricing_state.result)
    scenario = Scenario(
        name=name.strip(),
        source_version_number=workspace.base_version_number,
        configuration_snapshot=configuration_snapshot,
        pricing_snapshot=pricing_snapshot,
        source=ScenarioSource.MANUAL,
    )
    workspace.add_scenario(scenario)
    return scenario


MAX_COMPARISON_ALTERNATIVES = 3


@dataclass(frozen=True)
class ComparisonOption:
    """One column in the scenario comparison: the committed baseline, or
    one saved Scenario. Every field here is copied from an existing
    snapshot -- nothing is recalculated."""

    id: str
    name: str
    is_baseline: bool
    final_price: float
    approval_required: bool
    configuration: ConfigurationSnapshot


@dataclass(frozen=True)
class ComparisonRow:
    """One commercial-attribute row across all comparison options."""

    label: str
    values: tuple[str, ...]
    differs: bool


@dataclass(frozen=True)
class ScenarioComparison:
    options: tuple[ComparisonOption, ...]
    rows: tuple[ComparisonRow, ...]
    price_deltas: tuple[float | None, ...]
    """Aligned with `options`; None for the baseline itself."""


_COMPARISON_FIELDS: tuple[tuple[str, Callable[[ConfigurationSnapshot], str]], ...] = (
    ("Subscription tier", lambda c: c.tier.title()),
    ("Users", lambda c: str(c.users)),
    ("Geographic coverage", lambda c: c.coverage.replace("_", " ").title()),
    (
        "Historical depth",
        lambda c: f"{c.history_years} year" + ("s" if c.history_years != 1 else ""),
    ),
    ("Contract term", lambda c: f"{c.contract_months} months"),
    ("Renewal", lambda c: "Yes" if c.renewal else "No"),
    ("Premium support", lambda c: "Yes" if c.premium_support else "No"),
    ("Implementation services", lambda c: "Yes" if c.implementation_services else "No"),
    ("Discount", lambda c: f"{c.requested_discount_percent:.0f}%"),
)


def resolve_quote_version(quote: Quote, version_number: int) -> QuoteVersion:
    """Look up one historical QuoteVersion by number.

    Shared by comparison and the scenario-workspace baseline display so
    both resolve a workspace's anchor the same way rather than assuming
    it's always quote.current_version.
    """
    if version_number < 1 or version_number > len(quote.versions):
        raise ValueError(
            f"Quote {quote.quote_id} has no version {version_number} "
            f"(it has {len(quote.versions)})"
        )
    # Quote enforces sequential, gap-free numbering starting at 1, so this
    # index is always exact -- no separate lookup structure is needed.
    return quote.versions[version_number - 1]


def _comparison_option_from_version(version: QuoteVersion) -> ComparisonOption:
    snapshot = version.pricing_snapshot
    return ComparisonOption(
        id=f"baseline-v{version.version_number}",
        name="Committed Quote",
        is_baseline=True,
        final_price=snapshot.final_price,
        approval_required=snapshot.approval_required,
        configuration=version.configuration_snapshot,
    )


def _comparison_option_from_scenario(scenario: Scenario) -> ComparisonOption:
    return ComparisonOption(
        id=scenario.scenario_id,
        name=scenario.name,
        is_baseline=False,
        final_price=scenario.pricing_snapshot.final_price,
        approval_required=scenario.pricing_snapshot.approval_required,
        configuration=scenario.configuration_snapshot,
    )


def build_scenario_comparison(
    quote: Quote, workspace: ScenarioWorkspace, scenarios: tuple[Scenario, ...]
) -> ScenarioComparison:
    """Pure comparison facts for the workspace's baseline + selected scenarios.

    The baseline is the QuoteVersion identified by
    workspace.base_version_number -- deliberately NOT quote.current_version.
    Once scenario promotion can advance a quote past the version a
    workspace was anchored to, comparing against current_version would
    misrepresent a scenario's lineage; resolving against the workspace's
    own base version keeps a comparison historically correct regardless of
    later promotions elsewhere. Reads exclusively from existing snapshots
    -- never draft state, never current rules -- and the only arithmetic
    here is a price-delta subtraction between two already-stored
    final_price values; no pricing component is recalculated.
    """
    if workspace.quote_id != quote.quote_id:
        raise ValueError(
            f"Workspace is anchored to quote {workspace.quote_id}, not {quote.quote_id}"
        )
    baseline_version = resolve_quote_version(quote, workspace.base_version_number)
    for scenario in scenarios:
        if scenario.source_version_number != workspace.base_version_number:
            raise ValueError(
                f"Scenario {scenario.scenario_id} is based on version "
                f"{scenario.source_version_number}, not workspace base version "
                f"{workspace.base_version_number}"
            )

    options = (
        _comparison_option_from_version(baseline_version),
        *(_comparison_option_from_scenario(s) for s in scenarios),
    )
    baseline_price = options[0].final_price
    price_deltas = tuple(
        None if option.is_baseline else option.final_price - baseline_price
        for option in options
    )

    rows = []
    for label, formatter in _COMPARISON_FIELDS:
        values = tuple(formatter(option.configuration) for option in options)
        rows.append(ComparisonRow(label=label, values=values, differs=len(set(values)) > 1))

    return ScenarioComparison(options=options, rows=tuple(rows), price_deltas=price_deltas)


def selected_option_changes(comparison: ScenarioComparison, option_id: str) -> tuple[str, ...]:
    """"before → after" bullets for every attribute that differs between the
    baseline (comparison.options[0]) and the given option.

    Reuses the already-computed ScenarioComparison rows -- no new snapshot
    reads and no recalculation. Pass a comparison built from just the
    baseline + one scenario to describe that scenario's changes in
    isolation, regardless of how many alternatives are shown elsewhere.
    """
    try:
        index = next(i for i, option in enumerate(comparison.options) if option.id == option_id)
    except StopIteration:
        return ()
    if index == 0:
        return ()
    changes = []
    for row in comparison.rows:
        baseline_value = row.values[0]
        option_value = row.values[index]
        if baseline_value != option_value:
            changes.append(f"{baseline_value} → {option_value}")
    return tuple(changes)


def promote_selected_scenario(quote: Quote, workspace: ScenarioWorkspace) -> QuoteVersion:
    """Create the next durable QuoteVersion from the workspace's selected scenario.

    A thin wrapper around ScenarioWorkspace.promote_selected -- that domain
    method already validates quote/workspace correspondence and staleness,
    requires a selection, maps ScenarioSource to QuoteVersionSource, and
    reuses the scenario's own configuration/pricing snapshots without
    recalculating anything or calling Quote.add_version directly. This
    helper only translates the domain's ValueError into ScenarioError, the
    same exception type commit_quote and create_manual_scenario already
    use, so the UI has one consistent type to catch.
    """
    try:
        return workspace.promote_selected(quote)
    except ValueError as exc:
        raise ScenarioError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Budget Fit -- the UI collects intent; the Phase 4A engine (find_budget_fit)
# remains the sole authority on which configurations are feasible and how
# they rank. Nothing below recalculates a price, reranks a result, or
# reimplements capability scoring -- see docs/adr/002-budget-fit-optimization.md.
# ---------------------------------------------------------------------------

#: The BudgetFitField values exposed as "must keep exactly" checkboxes.
#: Users and the two services have their own dedicated constraint
#: mechanisms (minimum_users, required_premium_support/
#: required_implementation_services) and are deliberately not offered as
#: exact-match locks here.
BUDGET_FIT_LOCKABLE_FIELDS: tuple[BudgetFitField, ...] = (
    BudgetFitField.TIER,
    BudgetFitField.COVERAGE,
    BudgetFitField.HISTORY_YEARS,
    BudgetFitField.CONTRACT_MONTHS,
    BudgetFitField.RENEWAL,
)

BUDGET_FIT_FIELD_LABELS: dict[BudgetFitField, str] = {
    BudgetFitField.TIER: "Tier",
    BudgetFitField.USERS: "Users",
    BudgetFitField.COVERAGE: "Coverage",
    BudgetFitField.HISTORY_YEARS: "Historical depth",
    BudgetFitField.CONTRACT_MONTHS: "Contract term",
    BudgetFitField.RENEWAL: "Renewal",
    BudgetFitField.PREMIUM_SUPPORT: "Premium support",
    BudgetFitField.IMPLEMENTATION_SERVICES: "Implementation services",
}

#: Genuine product/service capability dimensions -- mirrors the engine's
#: own _CAPABILITY_FIELDS. Commercial mechanics (contract term, renewal)
#: are shown in "changed fields" but not reinforced in "preserved
#: capabilities", since they were never scored as capability either.
_BUDGET_FIT_CAPABILITY_FIELDS: tuple[BudgetFitField, ...] = (
    BudgetFitField.TIER,
    BudgetFitField.USERS,
    BudgetFitField.COVERAGE,
    BudgetFitField.HISTORY_YEARS,
    BudgetFitField.PREMIUM_SUPPORT,
    BudgetFitField.IMPLEMENTATION_SERVICES,
)


@dataclass(frozen=True)
class BudgetFitViewState:
    """A BudgetFitResult paired with the exact request that produced it and
    the QuoteVersion it was anchored to.

    This is everything the UI needs to detect staleness (version advanced,
    or inputs edited) without keeping a second copy of any pricing or
    capability figure -- `result` remains the sole source of recommendation
    truth.
    """

    source_version_number: int
    request: BudgetFitRequest
    result: BudgetFitResult


def build_budget_fit_constraints(
    *,
    lock_tier: bool,
    lock_coverage: bool,
    lock_history_years: bool,
    lock_contract_months: bool,
    lock_renewal: bool,
    minimum_users: int | None,
    required_premium_support: bool,
    required_implementation_services: bool,
) -> BudgetFitConstraints:
    """Translate individual UI checkboxes into the engine's own
    BudgetFitConstraints shape -- one boolean per real, lockable
    BudgetFitField. Deliberately not a generic constraint-rule builder."""
    locked_fields: set[BudgetFitField] = set()
    if lock_tier:
        locked_fields.add(BudgetFitField.TIER)
    if lock_coverage:
        locked_fields.add(BudgetFitField.COVERAGE)
    if lock_history_years:
        locked_fields.add(BudgetFitField.HISTORY_YEARS)
    if lock_contract_months:
        locked_fields.add(BudgetFitField.CONTRACT_MONTHS)
    if lock_renewal:
        locked_fields.add(BudgetFitField.RENEWAL)
    return BudgetFitConstraints(
        locked_fields=frozenset(locked_fields),
        minimum_users=minimum_users,
        required_premium_support=required_premium_support,
        required_implementation_services=required_implementation_services,
    )


def run_budget_fit(
    quote: Quote,
    target_budget: float,
    constraints: BudgetFitConstraints,
    rules: dict,
    max_recommendations: int = 3,
) -> BudgetFitViewState:
    """The one place the UI calls into the Budget Fit engine.

    Always anchors the search to quote.current_version.configuration_snapshot
    -- never a dirty Configure widget, a stale draft PricingState, or a
    Scenario draft -- and records which version that was, so a later quote
    advance can be detected as staleness instead of silently reinterpreted.
    Raises pydantic.ValidationError for invalid inputs (e.g. a non-positive
    target budget); the caller is responsible for turning that into a
    user-facing message.
    """
    version = quote.current_version
    request = BudgetFitRequest(
        target_budget=target_budget,
        baseline_configuration=version.configuration_snapshot,
        constraints=constraints,
        max_recommendations=max_recommendations,
    )
    result = find_budget_fit(request, rules)
    return BudgetFitViewState(
        source_version_number=version.version_number,
        request=request,
        result=result,
    )


def budget_fit_version_is_stale(view_state: BudgetFitViewState | None, quote: Quote) -> bool:
    """True if the Quote has advanced past the version a stored Budget Fit
    result was computed against -- the result must not be shown as though
    it still applies to the current quote."""
    if view_state is None:
        return False
    return view_state.source_version_number != quote.current_version.version_number


def budget_fit_inputs_changed(
    view_state: BudgetFitViewState | None,
    target_budget: float,
    constraints: BudgetFitConstraints,
) -> bool:
    """True if the live target budget/constraints no longer match the
    inputs that produced the stored result.

    Compares the actual typed request state rather than maintaining a
    separate dirty flag, mirroring how `is_stale` already compares
    PricingState to live Configure/Scenario form state.
    """
    if view_state is None:
        return False
    return (
        view_state.request.target_budget != target_budget
        or view_state.request.constraints != constraints
    )


def describe_preserved_capabilities(
    preserved_fields: tuple[BudgetFitField, ...], baseline: ConfigurationSnapshot
) -> tuple[str, ...]:
    """Human-readable bullets for the baseline capabilities a recommendation
    kept unchanged.

    Derived only from the engine's own preserved_fields and the baseline
    snapshot -- never a second scoring pass. Boolean capabilities the
    baseline never had are omitted (nothing meaningful to reinforce);
    commercial mechanics (contract term, renewal) are left to the
    changed-fields list, matching what the engine itself scores as
    capability.
    """
    descriptions: list[str] = []
    for field in _BUDGET_FIT_CAPABILITY_FIELDS:
        if field not in preserved_fields:
            continue
        if field is BudgetFitField.TIER:
            descriptions.append(f"{baseline.tier.title()} tier")
        elif field is BudgetFitField.USERS:
            descriptions.append(f"{baseline.users} users")
        elif field is BudgetFitField.COVERAGE:
            descriptions.append(f"{baseline.coverage.replace('_', ' ').title()} coverage")
        elif field is BudgetFitField.HISTORY_YEARS:
            depth = baseline.history_years
            descriptions.append(f"{depth} year{'s' if depth != 1 else ''} history")
        elif field is BudgetFitField.PREMIUM_SUPPORT and baseline.premium_support:
            descriptions.append("Premium support")
        elif field is BudgetFitField.IMPLEMENTATION_SERVICES and baseline.implementation_services:
            descriptions.append("Implementation services")
    return tuple(descriptions)


@dataclass(frozen=True)
class BudgetFitRecommendationView:
    """Presentation-ready facts for one recommendation.

    The only arithmetic here is a subtraction between two already-known
    monetary values (current committed price, target budget, and the
    recommendation's own already-priced final_price) -- never a new
    pricing calculation.
    """

    recommendation: BudgetFitRecommendation
    price_delta_vs_current: float
    budget_headroom: float


def build_recommendation_views(
    view_state: BudgetFitViewState,
) -> tuple[BudgetFitRecommendationView, ...]:
    result = view_state.result
    views = []
    for rec in result.recommendations:
        price = rec.pricing_snapshot.final_price
        views.append(
            BudgetFitRecommendationView(
                recommendation=rec,
                price_delta_vs_current=price - result.baseline_price,
                budget_headroom=result.target_budget - price,
            )
        )
    return tuple(views)


# ---------------------------------------------------------------------------
# Budget Fit comparison surface -- "shared context once, differences by
# option". Everything below is presentation logic over data the engine
# already returns (FieldChange, preserved_fields, capability_score, ...);
# no new scoring, ranking, or capability computation is introduced.
# ---------------------------------------------------------------------------

#: The symbol shown in a trade-off cell for an option that did not change
#: that particular dimension.
BUDGET_FIT_NO_CHANGE = "—"


def format_budget_fit_headroom(headroom: float) -> str:
    """"At budget" once headroom rounds to $0, otherwise "$X under
    budget" -- final price and headroom are the primary budget metrics;
    budget_utilization stays available on the model but is not the
    headline figure here (see BudgetFitRecommendation.budget_utilization)."""
    rounded = round(headroom)
    if rounded <= 0:
        return "At budget"
    return f"{format_money(rounded)} under budget"


def budget_fit_tradeoff_fields(
    recommendations: tuple[BudgetFitRecommendation, ...],
) -> tuple[BudgetFitField, ...]:
    """Every field that changed in at least one displayed recommendation,
    in engine field order -- the row labels of the trade-off comparison.

    Built from each recommendation's own `changed_fields` (already in a
    stable, consistent order -- see optimizer._ALL_FIELDS), never
    rediscovered from widget state.
    """
    fields: list[BudgetFitField] = []
    seen: set[BudgetFitField] = set()
    for rec in recommendations:
        for change in rec.changed_fields:
            if change.field not in seen:
                seen.add(change.field)
                fields.append(change.field)
    return tuple(fields)


def budget_fit_tradeoff_cell(recommendation: BudgetFitRecommendation, field: BudgetFitField) -> str:
    """"baseline → candidate" for one recommendation/field cell, or the
    no-change symbol if this particular recommendation preserved that
    field (even though another displayed recommendation changed it)."""
    for change in recommendation.changed_fields:
        if change.field is field:
            return f"{change.baseline_value} → {change.candidate_value}"
    return BUDGET_FIT_NO_CHANGE


def budget_fit_shared_preserved_capabilities(
    recommendations: tuple[BudgetFitRecommendation, ...], baseline: ConfigurationSnapshot
) -> tuple[str, ...]:
    """Baseline capabilities preserved by EVERY displayed recommendation --
    the intersection of each recommendation's own `preserved_fields`, so a
    field identical across all options is stated once instead of repeated
    in every column. A field preserved by some but not all recommendations
    belongs in the trade-off rows instead (mutually exclusive by
    construction: a field is either changed or preserved for a given
    recommendation, never both).
    """
    if not recommendations:
        return ()
    common_fields = set(recommendations[0].preserved_fields)
    for rec in recommendations[1:]:
        common_fields &= set(rec.preserved_fields)
    return describe_preserved_capabilities(tuple(common_fields), baseline)


def budget_fit_recommendation_rationale(recommendation: BudgetFitRecommendation) -> str:
    """A short, factual explanation for the top-ranked recommendation --
    never a new scoring algorithm.

    "Highest capability preservation" is safe to state unconditionally
    because capability_score is _rank_key's primary, dominant sort
    criterion (optimizer._rank_key): the top-ranked recommendation's
    capability_score is guaranteed to be at least as high as every other
    displayed recommendation's. The change count is read directly off
    this recommendation, not compared to the others.
    """
    change_word = "change" if recommendation.change_count == 1 else "changes"
    return (
        f"Highest capability preservation • {recommendation.change_count} "
        f"{change_word} from current quote"
    )


# ---------------------------------------------------------------------------
# Budget Fit -> Scenario -- Phase 4C. A recommendation is decision support,
# not a commercial decision: adding it only ever touches ScenarioWorkspace.
# Only the existing promote_selected_scenario (Phase 3) can ever create a
# QuoteVersion. Nothing here calls calculate_quote or find_budget_fit --
# the recommendation's own already-evaluated snapshots are reused exactly.
# ---------------------------------------------------------------------------


def _budget_fit_scenario_name(recommendation: BudgetFitRecommendation) -> str:
    if recommendation.rank == 1:
        return "Budget Fit — Recommended"
    return f"Budget Fit — Option {recommendation.rank}"


def build_budget_fit_negotiation_context(
    target_budget: float, constraints: BudgetFitConstraints
) -> NegotiationContext:
    """Best-effort mapping of Budget Fit intent onto the existing
    NegotiationContext model. required_attributes / flexible_attributes
    are free-form labels (the model's own shape), not a full re-encoding
    of BudgetFitConstraints.

    NegotiationContext has no numeric-floor concept, so minimum_users is
    folded into required_attributes as a short note rather than changing
    the model -- a deliberate, documented limitation, not an oversight.
    """
    required_fields: set[BudgetFitField] = set(constraints.locked_fields)
    if constraints.required_premium_support:
        required_fields.add(BudgetFitField.PREMIUM_SUPPORT)
    if constraints.required_implementation_services:
        required_fields.add(BudgetFitField.IMPLEMENTATION_SERVICES)

    # Iterate BudgetFitField's own declared order (not the set directly) so
    # the resulting tuples are deterministic across calls.
    required_attributes = [
        BUDGET_FIT_FIELD_LABELS[field] for field in BudgetFitField if field in required_fields
    ]
    if constraints.minimum_users is not None:
        required_attributes.append(f"Minimum {constraints.minimum_users} users")

    flexible_attributes = [
        BUDGET_FIT_FIELD_LABELS[field] for field in BudgetFitField if field not in required_fields
    ]

    return NegotiationContext(
        target_budget=target_budget,
        required_attributes=tuple(required_attributes),
        flexible_attributes=tuple(flexible_attributes),
    )


def create_budget_fit_scenario(
    quote: Quote,
    budget_fit_state: BudgetFitViewState,
    recommendation: BudgetFitRecommendation,
) -> Scenario:
    """Build a Scenario directly from an already-evaluated Budget Fit
    recommendation.

    Reuses recommendation.configuration_snapshot and .pricing_snapshot
    exactly as returned by find_budget_fit -- no recalculation. Validates
    version lineage independently of the UI (defense in depth: Phase 4B's
    screen should already prevent reaching this with a stale result) and
    refuses the unchanged-baseline recommendation, since the committed
    quote is already the baseline in Scenario Comparison and doesn't need
    a duplicate Scenario representing itself.

    Also validates that `recommendation` genuinely belongs to
    `budget_fit_state.result` -- membership by value equality against
    BudgetFitRecommendation's own (frozen, fully-compared) fields, not
    rank or price alone -- so a recommendation from a different Budget Fit
    run can never be attached to this state's NegotiationContext (same
    QuoteVersion, different target budget/constraints would otherwise
    silently mismatch a recommendation with the wrong negotiation intent).
    """
    if recommendation not in budget_fit_state.result.recommendations:
        raise ScenarioError(
            "This recommendation does not belong to the supplied Budget Fit "
            "result. Run Budget Fit again and add a recommendation from the "
            "current result."
        )
    if budget_fit_state.source_version_number != quote.current_version.version_number:
        raise ScenarioError(
            "This Budget Fit result is based on an earlier pricing version. "
            "Run Budget Fit again from the current quote before adding it "
            "to Alternatives."
        )
    if recommendation.is_baseline:
        raise ScenarioError(
            "The current quote already fits the customer's budget -- there is "
            "no alternative to add."
        )

    return Scenario(
        name=_budget_fit_scenario_name(recommendation),
        source_version_number=budget_fit_state.source_version_number,
        configuration_snapshot=recommendation.configuration_snapshot,
        pricing_snapshot=recommendation.pricing_snapshot,
        source=ScenarioSource.BUDGET_FIT,
        negotiation_context=build_budget_fit_negotiation_context(
            budget_fit_state.request.target_budget, budget_fit_state.request.constraints
        ),
    )


def _pricing_snapshot_signature(pricing_snapshot: PricingSnapshot) -> tuple:
    """A normalized semantic identity for a PricingSnapshot.

    Includes every commercially meaningful field -- rule/policy version,
    price composition, discount, approval state and reason, and the
    authority thresholds that were active at calculation time -- so two
    snapshots that differ in any historically meaningful fact (e.g. one
    requires approval and the other doesn't, even at the same final_price)
    are never treated as the same evaluated commercial decision.

    Deliberately excludes only `calculated_at`: a live timestamp that
    changes on every calculation even when every commercial fact above is
    identical, so it must not by itself make an otherwise identical
    recommendation look different after an independent Budget Fit rerun.
    `adjustments` is a tuple of frozen AdjustmentSnapshot models, which
    already compare by value, so it's included as-is rather than
    flattened -- no generalized hashing, just the model's own real fields.
    """
    return (
        pricing_snapshot.rule_version,
        pricing_snapshot.base_price,
        pricing_snapshot.adjustments,
        pricing_snapshot.subtotal_before_discount,
        pricing_snapshot.discount_amount,
        pricing_snapshot.final_price,
        pricing_snapshot.approval_required,
        pricing_snapshot.approval_reason,
        pricing_snapshot.self_service_threshold_percent,
        pricing_snapshot.max_allowed_discount_percent,
    )


def budget_fit_recommendation_is_added(workspace: ScenarioWorkspace, scenario: Scenario) -> bool:
    """True if an equivalent Budget Fit scenario already exists in the
    workspace.

    Identified by immutable commercial content -- source version,
    configuration snapshot, and a normalized PricingSnapshot signature --
    not by scenario_id (random per instance), not by final_price alone
    (two genuinely different configurations can coincidentally cost the
    same, and two genuinely different commercial decisions -- e.g.
    differing approval state -- can coincidentally share a final_price
    too), and not by full PricingSnapshot equality (which would fail to
    recognize a commercially identical recommendation produced by an
    independent Budget Fit rerun, since calculated_at is always fresh).

    NegotiationContext is deliberately NOT part of this identity: Northstar
    treats two identical evaluated commercial outcomes (same configuration,
    same real pricing facts) as one alternative regardless of which Budget
    Fit run under which target budget/constraints discovered them --
    Scenario Comparison has no NegotiationContext-specific display, so two
    entries differing only in undisplayed negotiation metadata would look
    like an unexplained duplicate to the user, not a meaningful distinction.
    """
    return any(
        existing.source == ScenarioSource.BUDGET_FIT
        and existing.source_version_number == scenario.source_version_number
        and existing.configuration_snapshot == scenario.configuration_snapshot
        and _pricing_snapshot_signature(existing.pricing_snapshot)
        == _pricing_snapshot_signature(scenario.pricing_snapshot)
        for existing in workspace.scenarios
    )


def add_budget_fit_recommendation(
    quote: Quote,
    workspace: ScenarioWorkspace | None,
    budget_fit_state: BudgetFitViewState,
    recommendation: BudgetFitRecommendation,
) -> ScenarioWorkspace:
    """Add one Budget Fit recommendation to the quote's negotiation
    workspace -- creating a new workspace if none exists yet, or reusing
    an existing one anchored to the same quote/base version so manual and
    Budget Fit scenarios coexist in one workspace (never a parallel
    Budget Fit workspace).

    Raises ScenarioError if: the workspace belongs to a different quote or
    a different base version than this Budget Fit result, the
    recommendation is stale or the unchanged baseline (see
    create_budget_fit_scenario), or an equivalent recommendation has
    already been added.
    """
    if workspace is not None and workspace.quote_id != quote.quote_id:
        raise ScenarioError(
            f"The current negotiation workspace belongs to a different quote "
            f"({workspace.quote_id}). Start exploration again from the current quote."
        )
    if workspace is not None and workspace.base_version_number != budget_fit_state.source_version_number:
        raise ScenarioError(
            "The current negotiation workspace is based on a different pricing "
            "version than this Budget Fit result. Return to Review Pricing and "
            "start from the current quote."
        )

    scenario = create_budget_fit_scenario(quote, budget_fit_state, recommendation)

    if workspace is not None and budget_fit_recommendation_is_added(workspace, scenario):
        raise ScenarioError("This recommendation has already been added to Alternatives.")

    if workspace is None:
        workspace = ScenarioWorkspace(
            quote_id=quote.quote_id, base_version_number=budget_fit_state.source_version_number
        )
    workspace.add_scenario(scenario)
    return workspace
