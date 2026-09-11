"""Budget Fit: deterministic constrained configuration search.

Implements ADR-002 (docs/adr/002-budget-fit-optimization.md). Budget Fit
sits *above* the canonical pricing engine and never reimplements pricing:

    Target budget + constraints
            |
            v
    Candidate ConfigurationSnapshots  (bounded, rule-backed enumeration)
            |
            v
    pricing_engine.calculate_quote    (the one and only pricing calculation)
            |
            v
    Feasibility filter (constraints already baked into candidate
    generation; only "within budget" is checked here)
            |
            v
    Transparent multi-factor ranking + diversity
            |
            v
    BudgetFitResult

v1 constraints, all deliberate:

* Discrete enumeration only (itertools.product) -- no solver library. The
  fictional configuration space is small enough for this to be instant.
* `requested_discount_percent` is never searched -- it is carried forward
  unchanged from the baseline. Budget Fit solves budget problems through
  product/service configuration *before* discretionary discount.
* The `users` dimension is bounded to [floor, baseline.users] -- see
  `_users_domain` -- so v1 fits an existing proposed scope to budget
  rather than proposing an upsell beyond what the customer already asked
  for. A future phase can accept an explicit upper bound if that becomes
  a real requirement.
* Every other flexible dimension's candidate values are read directly
  from the active pricing rules (`rules["tiers"]`, `rules["coverage"]`,
  ...) so Budget Fit never maintains a second copy of what Northstar
  actually sells.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from pydantic import ValidationError

from pricing_engine import QuoteRequest, QuoteResult, calculate_quote
from quotes import ConfigurationSnapshot, PricingSnapshot

from .models import (
    BudgetFitConstraints,
    BudgetFitField,
    BudgetFitRecommendation,
    BudgetFitRequest,
    BudgetFitResult,
    CapabilityComponent,
    FieldChange,
)

# Capability is scored only for genuine product/service dimensions.
# Commercial mechanics (contract term, renewal) remain searchable and are
# still reported in changed/preserved fields, but per ADR-002 / product
# guidance they are not automatically "more capability".
_CAPABILITY_FIELDS: tuple[BudgetFitField, ...] = (
    BudgetFitField.TIER,
    BudgetFitField.USERS,
    BudgetFitField.COVERAGE,
    BudgetFitField.HISTORY_YEARS,
    BudgetFitField.PREMIUM_SUPPORT,
    BudgetFitField.IMPLEMENTATION_SERVICES,
)

_ALL_FIELDS: tuple[BudgetFitField, ...] = tuple(BudgetFitField)


@dataclass(frozen=True)
class _CandidateEvaluation:
    """Internal working representation -- never exposed outside this
    module. BudgetFitRecommendation is built from this once a candidate
    has survived ranking and diversification."""

    configuration: ConfigurationSnapshot
    result: QuoteResult
    capability_score: float
    capability_breakdown: tuple[CapabilityComponent, ...]
    budget_utilization: float
    changed_fields: tuple[FieldChange, ...]
    preserved_fields: tuple[BudgetFitField, ...]
    configuration_signature: tuple


def find_budget_fit(request: BudgetFitRequest, rules: dict) -> BudgetFitResult:
    """Search for configurations at or below `request.target_budget`.

    `rules` is passed alongside the request (not embedded in it), matching
    calculate_quote's own (request, rules) shape used throughout the
    pricing engine and app_state.py.
    """
    baseline = request.baseline_configuration
    constraints = request.constraints

    users_lower = max(1, constraints.minimum_users or 1)
    users_upper = baseline.users

    baseline_request = QuoteRequest(**baseline.model_dump())
    baseline_result = calculate_quote(baseline_request, rules)

    if baseline_result.final_price <= request.target_budget and _baseline_satisfies_constraints(
        baseline, constraints
    ):
        # Hard constraints are gates everywhere (ADR-002), including this
        # shortcut: a baseline that fits on price but violates a locked
        # field, minimum, or required service must still go through the
        # normal search below rather than being returned unchanged.
        return _baseline_fits_result(
            request, baseline, baseline_result, rules, users_lower, users_upper
        )

    domains = (
        _tier_domain(rules, baseline, constraints),
        _users_domain(users_lower, users_upper),
        _coverage_domain(rules, baseline, constraints),
        _history_years_domain(rules, baseline, constraints),
        _contract_months_domain(rules, baseline, constraints),
        _renewal_domain(rules, baseline, constraints),
        _premium_support_domain(rules, baseline, constraints),
        _implementation_services_domain(rules, baseline, constraints),
    )

    evaluated = 0
    evaluations: list[_CandidateEvaluation] = []

    # itertools.product over duplicate-free domains cannot itself yield a
    # duplicate combination, so no separate dedup step is needed here.
    for values in product(*domains):
        evaluated += 1
        configuration = _build_configuration(baseline, values)

        try:
            candidate_request = QuoteRequest(**configuration.model_dump())
        except ValidationError:
            # Expected: some combination pydantic itself rejects. Every
            # value here already comes from a rule-derived or
            # constraint-respecting domain, so this should not trigger
            # today, but a future rule/model change could add a stricter
            # validator -- skip deliberately rather than crash.
            continue

        try:
            result = calculate_quote(candidate_request, rules)
        except ValueError:
            # Expected: the engine itself rejects an unsupported
            # combination (unsupported tier/coverage/etc). Anything other
            # than ValueError is not caught and fails loudly.
            continue

        if result.final_price > request.target_budget:
            continue

        evaluations.append(
            _evaluate_candidate(
                rules, baseline, configuration, result, request.target_budget,
                users_lower, users_upper,
            )
        )

    feasible_count = len(evaluations)
    if not evaluations:
        if evaluated == 0:
            reason = "No candidate configurations could be generated within the given constraints."
        else:
            reason = (
                f"No valid configuration was found at or below ${request.target_budget:,.0f} "
                "given the current constraints."
            )
        return BudgetFitResult(
            target_budget=request.target_budget,
            baseline_price=baseline_result.final_price,
            evaluated_candidate_count=evaluated,
            feasible_candidate_count=0,
            recommendations=(),
            no_fit_reason=reason,
        )

    ranked = sorted(evaluations, key=_rank_key)
    diversified = _diversify(ranked, request.max_recommendations)
    recommendations = tuple(
        _to_recommendation(evaluation, rank=index + 1)
        for index, evaluation in enumerate(diversified)
    )

    return BudgetFitResult(
        target_budget=request.target_budget,
        baseline_price=baseline_result.final_price,
        evaluated_candidate_count=evaluated,
        feasible_candidate_count=feasible_count,
        recommendations=recommendations,
        no_fit_reason=None,
    )


def _baseline_satisfies_constraints(
    baseline: ConfigurationSnapshot, constraints: BudgetFitConstraints
) -> bool:
    """Locked fields are trivially satisfied by the baseline (its own
    value always equals itself), so only the two constraint kinds that
    the baseline could actually violate are checked here."""
    if constraints.minimum_users is not None and baseline.users < constraints.minimum_users:
        return False
    if constraints.required_premium_support and not baseline.premium_support:
        return False
    if constraints.required_implementation_services and not baseline.implementation_services:
        return False
    return True


def _baseline_fits_result(
    request: BudgetFitRequest,
    baseline: ConfigurationSnapshot,
    baseline_result: QuoteResult,
    rules: dict,
    users_lower: int,
    users_upper: int,
) -> BudgetFitResult:
    """The committed baseline already fits -- return it unchanged as the
    sole recommendation rather than letting the general search possibly
    prefer some other, equally-valid-but-different configuration. Budget
    Fit must not downgrade (or upgrade) a configuration that was never
    the problem."""
    evaluation = _evaluate_candidate(
        rules, baseline, baseline, baseline_result, request.target_budget,
        users_lower, users_upper,
    )
    recommendation = _to_recommendation(evaluation, rank=1).model_copy(
        update={"is_baseline": True}
    )
    return BudgetFitResult(
        target_budget=request.target_budget,
        baseline_price=baseline_result.final_price,
        evaluated_candidate_count=1,
        feasible_candidate_count=1,
        recommendations=(recommendation,),
        no_fit_reason=None,
    )


# ---------------------------------------------------------------------------
# Search-space domains -- every flexible dimension is derived from `rules`,
# never hard-coded, and a locked/required constraint narrows a domain to a
# single value rather than being checked after the fact.
# ---------------------------------------------------------------------------


def _tier_domain(rules: dict, baseline: ConfigurationSnapshot, constraints: BudgetFitConstraints) -> tuple[str, ...]:
    if BudgetFitField.TIER in constraints.locked_fields:
        return (baseline.tier,)
    return tuple(rules["tiers"].keys())


def _users_domain(users_lower: int, users_upper: int) -> tuple[int, ...]:
    if users_lower > users_upper:
        return ()
    return tuple(range(users_lower, users_upper + 1))


def _coverage_domain(rules: dict, baseline: ConfigurationSnapshot, constraints: BudgetFitConstraints) -> tuple[str, ...]:
    if BudgetFitField.COVERAGE in constraints.locked_fields:
        return (baseline.coverage,)
    return tuple(rules["coverage"].keys())


def _history_years_domain(rules: dict, baseline: ConfigurationSnapshot, constraints: BudgetFitConstraints) -> tuple[int, ...]:
    if BudgetFitField.HISTORY_YEARS in constraints.locked_fields:
        return (baseline.history_years,)
    return tuple(rules["history_years"].keys())


def _contract_months_domain(rules: dict, baseline: ConfigurationSnapshot, constraints: BudgetFitConstraints) -> tuple[int, ...]:
    if BudgetFitField.CONTRACT_MONTHS in constraints.locked_fields:
        return (baseline.contract_months,)
    return tuple(rules["contract_term"].keys())


def _renewal_domain(rules: dict, baseline: ConfigurationSnapshot, constraints: BudgetFitConstraints) -> tuple[bool, ...]:
    if BudgetFitField.RENEWAL in constraints.locked_fields:
        return (baseline.renewal,)
    return tuple(rules["renewal"].keys())


def _premium_support_domain(rules: dict, baseline: ConfigurationSnapshot, constraints: BudgetFitConstraints) -> tuple[bool, ...]:
    if constraints.required_premium_support:
        return (True,)
    if BudgetFitField.PREMIUM_SUPPORT in constraints.locked_fields:
        return (baseline.premium_support,)
    return tuple(rules["premium_support"].keys())


def _implementation_services_domain(rules: dict, baseline: ConfigurationSnapshot, constraints: BudgetFitConstraints) -> tuple[bool, ...]:
    if constraints.required_implementation_services:
        return (True,)
    if BudgetFitField.IMPLEMENTATION_SERVICES in constraints.locked_fields:
        return (baseline.implementation_services,)
    return tuple(rules["implementation_services"].keys())


def _build_configuration(baseline: ConfigurationSnapshot, values: tuple) -> ConfigurationSnapshot:
    tier, users, coverage, history_years, contract_months, renewal, premium_support, implementation_services = values
    return ConfigurationSnapshot(
        customer_name=baseline.customer_name,
        tier=tier,
        users=users,
        coverage=coverage,
        history_years=history_years,
        contract_months=contract_months,
        premium_support=premium_support,
        implementation_services=implementation_services,
        renewal=renewal,
        # Never searched -- preserved exactly. See module docstring / ADR-002.
        requested_discount_percent=baseline.requested_discount_percent,
    )


# ---------------------------------------------------------------------------
# Capability scoring -- each dimension normalized to [0, 1] against its
# rule-defined range, then averaged into a single transparent score used
# for ranking (see _rank_key below).
# ---------------------------------------------------------------------------


def _normalized(value: float, low: float, high: float) -> float:
    if high == low:
        return 1.0
    return (value - low) / (high - low)


def _tier_score(rules: dict, tier: str) -> float:
    prices = [option["base_price"] for option in rules["tiers"].values()]
    return _normalized(float(rules["tiers"][tier]["base_price"]), float(min(prices)), float(max(prices)))


def _coverage_score(rules: dict, coverage: str) -> float:
    prices = list(rules["coverage"].values())
    return _normalized(float(rules["coverage"][coverage]), float(min(prices)), float(max(prices)))


def _history_years_score(rules: dict, history_years: int) -> float:
    prices = list(rules["history_years"].values())
    return _normalized(float(rules["history_years"][history_years]), float(min(prices)), float(max(prices)))


def _users_score(users: int, users_lower: int, users_upper: int) -> float:
    return _normalized(float(users), float(users_lower), float(users_upper))


def _boolean_score(value: bool) -> float:
    return 1.0 if value else 0.0


def _format_value(field: BudgetFitField, value: object) -> str:
    if field is BudgetFitField.TIER:
        return str(value).title()
    if field is BudgetFitField.COVERAGE:
        return str(value).replace("_", " ").title()
    if field is BudgetFitField.HISTORY_YEARS:
        return f"{value} year" + ("s" if value != 1 else "")
    if field is BudgetFitField.CONTRACT_MONTHS:
        return f"{value} months"
    if field in (BudgetFitField.RENEWAL, BudgetFitField.PREMIUM_SUPPORT, BudgetFitField.IMPLEMENTATION_SERVICES):
        return "Yes" if value else "No"
    return str(value)


def _evaluate_candidate(
    rules: dict,
    baseline: ConfigurationSnapshot,
    configuration: ConfigurationSnapshot,
    result: QuoteResult,
    target_budget: float,
    users_lower: int,
    users_upper: int,
) -> _CandidateEvaluation:
    breakdown = (
        CapabilityComponent(field=BudgetFitField.TIER, score=_tier_score(rules, configuration.tier)),
        CapabilityComponent(field=BudgetFitField.USERS, score=_users_score(configuration.users, users_lower, users_upper)),
        CapabilityComponent(field=BudgetFitField.COVERAGE, score=_coverage_score(rules, configuration.coverage)),
        CapabilityComponent(field=BudgetFitField.HISTORY_YEARS, score=_history_years_score(rules, configuration.history_years)),
        CapabilityComponent(field=BudgetFitField.PREMIUM_SUPPORT, score=_boolean_score(configuration.premium_support)),
        CapabilityComponent(field=BudgetFitField.IMPLEMENTATION_SERVICES, score=_boolean_score(configuration.implementation_services)),
    )
    capability_score = sum(component.score for component in breakdown) / len(breakdown)

    changed: list[FieldChange] = []
    preserved: list[BudgetFitField] = []
    for field in _ALL_FIELDS:
        baseline_value = getattr(baseline, field.value)
        candidate_value = getattr(configuration, field.value)
        if baseline_value == candidate_value:
            preserved.append(field)
        else:
            changed.append(
                FieldChange(
                    field=field,
                    baseline_value=_format_value(field, baseline_value),
                    candidate_value=_format_value(field, candidate_value),
                )
            )

    signature = tuple(getattr(configuration, field.value) for field in _ALL_FIELDS)

    return _CandidateEvaluation(
        configuration=configuration,
        result=result,
        capability_score=capability_score,
        capability_breakdown=breakdown,
        budget_utilization=result.final_price / target_budget,
        changed_fields=tuple(changed),
        preserved_fields=tuple(preserved),
        configuration_signature=signature,
    )


def _rank_key(evaluation: _CandidateEvaluation) -> tuple:
    """Deterministic ranking (ADR-002 / spec order):
    1. higher capability score
    2. within-authority preferred over approval-required
    3. higher budget utilization
    4. fewer changed dimensions from baseline
    5. stable tie-breaker: the candidate's own field values, so identical
       requests always produce identical order regardless of generation
       order.
    """
    return (
        -evaluation.capability_score,
        1 if evaluation.result.approval_required else 0,
        -evaluation.budget_utilization,
        len(evaluation.changed_fields),
        evaluation.configuration_signature,
    )


def _diversify(
    ranked: list[_CandidateEvaluation], max_recommendations: int
) -> list[_CandidateEvaluation]:
    """Greedily keep the best-ranked candidate for each distinct *set* of
    changed fields, skipping later candidates that changed the exact same
    dimensions as one already selected. Returns fewer than
    max_recommendations if genuinely distinct options run out -- never
    pads with near-duplicates."""
    selected: list[_CandidateEvaluation] = []
    seen_change_signatures: set[frozenset[BudgetFitField]] = set()
    for evaluation in ranked:
        signature = frozenset(change.field for change in evaluation.changed_fields)
        if signature in seen_change_signatures:
            continue
        selected.append(evaluation)
        seen_change_signatures.add(signature)
        if len(selected) >= max_recommendations:
            break
    return selected


def _to_recommendation(evaluation: _CandidateEvaluation, *, rank: int) -> BudgetFitRecommendation:
    return BudgetFitRecommendation(
        configuration_snapshot=evaluation.configuration,
        pricing_snapshot=PricingSnapshot.from_pricing_result(evaluation.result),
        rank=rank,
        capability_score=evaluation.capability_score,
        capability_breakdown=evaluation.capability_breakdown,
        budget_utilization=evaluation.budget_utilization,
        changed_fields=evaluation.changed_fields,
        preserved_fields=evaluation.preserved_fields,
        is_baseline=False,
    )
