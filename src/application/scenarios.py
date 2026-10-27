"""Presentation-neutral scenario / negotiation-workspace orchestration.

Extracted from app/app_state.py so both app/ (Streamlit) and api/
(FastAPI) call the exact same scenario-lifecycle functions rather than
each carrying its own copy -- the same pattern already used for quote
creation (see application/quotes.py).

Domain rules stay in src/quotes/scenarios.py (Scenario, ScenarioWorkspace,
and ScenarioWorkspace.promote_selected's own validation) and
src/budget_fit (find_budget_fit, ranking, capability scoring). Nothing
here reimplements pricing, scoring, or the workspace's own invariants --
it only orchestrates calls into that domain, translating ValueError into
the one ScenarioError type callers already catch.
"""

from __future__ import annotations

from budget_fit import BudgetFitConstraints, BudgetFitField, BudgetFitRecommendation, BudgetFitRequest
from pricing_engine import QuoteRequest, QuoteResult
from quotes import (
    ConfigurationSnapshot,
    NegotiationContext,
    PricingSnapshot,
    Quote,
    QuoteVersion,
    Scenario,
    ScenarioSource,
    ScenarioWorkspace,
)


class ScenarioError(ValueError):
    """Raised when a scenario/workspace operation cannot be completed."""


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
    configuration: QuoteRequest,
    result: QuoteResult,
) -> Scenario:
    """Build a Scenario from an already-calculated candidate and add it to
    the workspace. Reuses PricingSnapshot.from_pricing_result and
    ConfigurationSnapshot.from_request -- the same snapshot conversions
    every other commit path uses -- so nothing here is a parallel pricing
    representation. Never touches Quote or QuoteVersion: an
    approval-required scenario is a valid alternative and may be saved.

    Callers that have their own draft/staleness concept (e.g. Streamlit's
    PricingState) validate that before calling this -- this function only
    requires a non-empty name and an already-evaluated configuration/result.
    """
    if not name or not name.strip():
        raise ScenarioError("Scenario name is required before saving.")
    configuration_snapshot = ConfigurationSnapshot.from_request(configuration)
    pricing_snapshot = PricingSnapshot.from_pricing_result(result)
    scenario = Scenario(
        name=name.strip(),
        source_version_number=workspace.base_version_number,
        configuration_snapshot=configuration_snapshot,
        pricing_snapshot=pricing_snapshot,
        source=ScenarioSource.MANUAL,
    )
    workspace.add_scenario(scenario)
    return scenario


def resolve_quote_version(quote: Quote, version_number: int) -> QuoteVersion:
    """Look up one historical QuoteVersion by number -- shared by
    comparison and workspace-baseline display so both resolve a
    workspace's anchor the same way rather than assuming it's always
    quote.current_version."""
    if version_number < 1 or version_number > len(quote.versions):
        raise ScenarioError(
            f"Quote {quote.quote_id} has no version {version_number} "
            f"(it has {len(quote.versions)})"
        )
    # Quote enforces sequential, gap-free numbering starting at 1, so this
    # index is always exact -- no separate lookup structure is needed.
    return quote.versions[version_number - 1]


def promote_selected_scenario(quote: Quote, workspace: ScenarioWorkspace) -> QuoteVersion:
    """Create the next durable QuoteVersion from the workspace's selected
    scenario.

    A thin wrapper around ScenarioWorkspace.promote_selected -- that
    domain method already validates quote/workspace correspondence and
    staleness, requires a selection, maps ScenarioSource to
    QuoteVersionSource, and reuses the scenario's own configuration/
    pricing snapshots without recalculating anything or calling
    Quote.add_version with anything but those exact snapshots. This
    helper only translates the domain's ValueError into ScenarioError,
    the one exception type every caller here catches.
    """
    try:
        return workspace.promote_selected(quote)
    except ValueError as exc:
        raise ScenarioError(str(exc)) from exc


#: Human-readable labels for BudgetFitField values -- presentation only,
#: used to build NegotiationContext's free-form attribute labels.
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


def budget_fit_scenario_name(recommendation: BudgetFitRecommendation) -> str:
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
    source_version_number: int,
    request: BudgetFitRequest,
    recommendation: BudgetFitRecommendation,
) -> Scenario:
    """Build a Scenario directly from an already-evaluated Budget Fit
    recommendation.

    Reuses recommendation.configuration_snapshot and .pricing_snapshot
    exactly as returned by find_budget_fit -- no recalculation. Refuses a
    recommendation anchored to an earlier pricing version (the Quote has
    since advanced) and refuses the unchanged-baseline recommendation,
    since the committed quote is already the baseline in comparison and
    doesn't need a duplicate Scenario representing itself.
    """
    if source_version_number != quote.current_version.version_number:
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
        name=budget_fit_scenario_name(recommendation),
        source_version_number=source_version_number,
        configuration_snapshot=recommendation.configuration_snapshot,
        pricing_snapshot=recommendation.pricing_snapshot,
        source=ScenarioSource.BUDGET_FIT,
        negotiation_context=build_budget_fit_negotiation_context(
            request.target_budget, request.constraints
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
    not by scenario_id (random per instance), not by final_price alone,
    and not by full PricingSnapshot equality (which would fail to
    recognize a commercially identical recommendation produced by an
    independent Budget Fit rerun, since calculated_at is always fresh).

    NegotiationContext is deliberately NOT part of this identity: two
    identical evaluated commercial outcomes count as one alternative
    regardless of which Budget Fit run under which target budget/
    constraints discovered them.
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
    source_version_number: int,
    request: BudgetFitRequest,
    recommendation: BudgetFitRecommendation,
) -> ScenarioWorkspace:
    """Add one Budget Fit recommendation to the quote's negotiation
    workspace -- creating a new workspace if none exists yet, or reusing
    an existing one anchored to the same quote/base version so manual and
    Budget Fit scenarios coexist in one workspace (never a parallel
    Budget Fit workspace).

    Raises ScenarioError if: the workspace belongs to a different quote
    or a different base version than this Budget Fit result, the
    recommendation is stale or the unchanged baseline (see
    create_budget_fit_scenario), or an equivalent recommendation has
    already been added.
    """
    if workspace is not None and workspace.quote_id != quote.quote_id:
        raise ScenarioError(
            f"The current negotiation workspace belongs to a different quote "
            f"({workspace.quote_id}). Start exploration again from the current quote."
        )
    if workspace is not None and workspace.base_version_number != source_version_number:
        raise ScenarioError(
            "The current negotiation workspace is based on a different pricing "
            "version than this Budget Fit result. Return to Review Pricing and "
            "start from the current quote."
        )

    scenario = create_budget_fit_scenario(quote, source_version_number, request, recommendation)

    if workspace is not None and budget_fit_recommendation_is_added(workspace, scenario):
        raise ScenarioError("This recommendation has already been added to Alternatives.")

    if workspace is None:
        workspace = ScenarioWorkspace(quote_id=quote.quote_id, base_version_number=source_version_number)
    workspace.add_scenario(scenario)
    return workspace
