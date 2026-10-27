"""Alternatives / negotiation-workspace HTTP endpoints.

Thin translation + persistence-wiring boundary only: every actual
decision (staleness, duplicate detection, promotion mapping, Budget Fit
ranking) is made by src/application/scenarios.py, src/quotes/scenarios.py,
or src/budget_fit -- never recreated here. See ADR-005 for the
persistence design and the scenario/commercial-history distinction this
router exists to preserve.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from application import (
    ScenarioError,
    budget_fit_recommendation_is_added,
    create_budget_fit_scenario,
    create_manual_scenario,
    create_scenario_workspace,
    promote_selected_scenario,
    resolve_quote_version,
)
from budget_fit import BudgetFitConstraints, BudgetFitRequest, find_budget_fit
from pricing_engine import calculate_quote
from persistence import (
    BudgetFitRun,
    BudgetFitRunNotFoundError,
    BudgetFitRunRepository,
    DuplicateWorkspaceError,
    QuoteNotFoundError,
    QuoteRepository,
    QuoteVersionConflict,
    ScenarioNotFoundError,
    ScenarioRepository,
    WorkspaceNotFoundError,
)
from quotes import Quote, ScenarioWorkspace

from api.dependencies import (
    get_budget_fit_run_repository,
    get_pricing_rules,
    get_quote_repository,
    get_scenario_repository,
)
from api.dto_mapping import (
    configuration_dto_to_request,
    configuration_snapshot_to_dto,
    parse_locked_fields,
    pricing_snapshot_to_dto,
    recommendation_to_dto,
    scenario_to_dto,
)
from api.models import (
    AddFromBudgetFitRequestDto,
    AlternativesBaselineDto,
    AlternativesResponseDto,
    ManualAlternativeRequestDto,
    QuoteLinkedBudgetFitRequestDto,
    QuoteLinkedBudgetFitResponseDto,
    QuoteResponseDto,
    SelectAlternativeRequestDto,
)
from api.routers.quotes import _quote_to_response_dto

router = APIRouter(prefix="/api/quotes", tags=["alternatives"])


def _load_quote(repository: QuoteRepository, quote_id: str) -> Quote:
    try:
        return repository.get(quote_id)
    except QuoteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _get_or_create_workspace(
    scenario_repository: ScenarioRepository, quote: Quote
) -> ScenarioWorkspace:
    """One active workspace per quote (Phase 6E spec section 5): load it
    if one exists, otherwise create a brand-new one anchored to the
    quote's current committed version the first time it's needed."""
    if scenario_repository.workspace_exists(quote.quote_id):
        return scenario_repository.get_workspace(quote.quote_id)
    workspace = create_scenario_workspace(quote)
    try:
        scenario_repository.create_workspace(workspace)
    except DuplicateWorkspaceError:
        # Lost a race with another request that created it first --
        # the existing workspace is equally valid to use.
        return scenario_repository.get_workspace(quote.quote_id)
    return workspace


def _is_stale(quote: Quote, workspace: ScenarioWorkspace) -> bool:
    return workspace.base_version_number != quote.current_version.version_number


def _require_fresh_workspace(quote: Quote, workspace: ScenarioWorkspace) -> None:
    if _is_stale(quote, workspace):
        raise HTTPException(
            status_code=409,
            detail=(
                f"These alternatives were created from pricing version "
                f"v{workspace.base_version_number}. The quote is now on version "
                f"v{quote.current_version.version_number}. Start new exploration "
                "from the current pricing."
            ),
        )


def _alternatives_to_dto(quote: Quote, workspace: ScenarioWorkspace) -> AlternativesResponseDto:
    baseline_version = resolve_quote_version(quote, workspace.base_version_number)
    return AlternativesResponseDto(
        quoteId=quote.quote_id,
        baseVersionNumber=workspace.base_version_number,
        currentVersionNumber=quote.current_version.version_number,
        stale=_is_stale(quote, workspace),
        baseline=AlternativesBaselineDto(
            versionNumber=baseline_version.version_number,
            configuration=configuration_snapshot_to_dto(baseline_version.configuration_snapshot),
            pricing=pricing_snapshot_to_dto(baseline_version.pricing_snapshot),
        ),
        scenarios=[scenario_to_dto(s) for s in workspace.scenarios],
        selectedScenarioId=workspace.selected_scenario_id,
    )


@router.get("/{quote_id}/alternatives", response_model=AlternativesResponseDto)
def get_alternatives(
    quote_id: str,
    quote_repository: QuoteRepository = Depends(get_quote_repository),
    scenario_repository: ScenarioRepository = Depends(get_scenario_repository),
) -> AlternativesResponseDto:
    quote = _load_quote(quote_repository, quote_id)
    workspace = _get_or_create_workspace(scenario_repository, quote)
    return _alternatives_to_dto(quote, workspace)


@router.post("/{quote_id}/alternatives/manual", response_model=AlternativesResponseDto, status_code=201)
def create_manual_alternative(
    quote_id: str,
    request: ManualAlternativeRequestDto,
    quote_repository: QuoteRepository = Depends(get_quote_repository),
    scenario_repository: ScenarioRepository = Depends(get_scenario_repository),
) -> AlternativesResponseDto:
    """Calculate the candidate via the canonical pricing engine and save
    it as a Scenario -- never a QuoteVersion. Pricing is calculated once,
    here; the resulting Scenario snapshot is then fixed."""
    quote = _load_quote(quote_repository, quote_id)
    workspace = _get_or_create_workspace(scenario_repository, quote)
    _require_fresh_workspace(quote, workspace)

    try:
        configuration = configuration_dto_to_request(request.configuration)
        result = calculate_quote(configuration, get_pricing_rules())
        scenario = create_manual_scenario(request.name, workspace, configuration, result)
    except (ValidationError, ValueError, ScenarioError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        scenario_repository.add_scenario(quote_id, scenario)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _alternatives_to_dto(quote, workspace)


@router.post(
    "/{quote_id}/alternatives/from-budget-fit",
    response_model=AlternativesResponseDto,
    status_code=201,
)
def add_budget_fit_alternative(
    quote_id: str,
    request: AddFromBudgetFitRequestDto,
    quote_repository: QuoteRepository = Depends(get_quote_repository),
    scenario_repository: ScenarioRepository = Depends(get_scenario_repository),
    budget_fit_run_repository: BudgetFitRunRepository = Depends(get_budget_fit_run_repository),
) -> AlternativesResponseDto:
    """Reuse a persisted Budget Fit run's exact recommendation snapshots
    -- never recalculated. `rank` selects the recommendation
    unambiguously within that run's deterministically-ordered result."""
    quote = _load_quote(quote_repository, quote_id)

    try:
        run = budget_fit_run_repository.get_run(request.run_id)
    except BudgetFitRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if run.quote_id != quote_id:
        raise HTTPException(
            status_code=404, detail=f"Budget Fit run {request.run_id} does not belong to this quote"
        )
    if request.rank < 1 or request.rank > len(run.result.recommendations):
        raise HTTPException(
            status_code=404,
            detail=f"Run {request.run_id} has no recommendation with rank {request.rank}",
        )
    if run.base_version_number != quote.current_version.version_number:
        raise HTTPException(
            status_code=409,
            detail=(
                "This Budget Fit result is based on an earlier pricing version. "
                "Run Budget Fit again from the current quote before adding it to Alternatives."
            ),
        )

    workspace = _get_or_create_workspace(scenario_repository, quote)
    _require_fresh_workspace(quote, workspace)

    recommendation = run.result.recommendations[request.rank - 1]
    try:
        scenario = create_budget_fit_scenario(quote, run.base_version_number, run.request, recommendation)
    except ScenarioError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if budget_fit_recommendation_is_added(workspace, scenario):
        raise HTTPException(
            status_code=409, detail="This recommendation has already been added to Alternatives."
        )

    try:
        scenario_repository.add_scenario(quote_id, scenario)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    # Persisted successfully -- reflect it in the in-memory workspace too
    # (unlike create_manual_scenario, this endpoint never called
    # workspace.add_scenario itself), so the response reflects the write
    # that just happened rather than a stale pre-add snapshot.
    workspace.add_scenario(scenario)

    return _alternatives_to_dto(quote, workspace)


@router.put("/{quote_id}/alternatives/selection", response_model=AlternativesResponseDto)
def select_alternative(
    quote_id: str,
    request: SelectAlternativeRequestDto,
    quote_repository: QuoteRepository = Depends(get_quote_repository),
    scenario_repository: ScenarioRepository = Depends(get_scenario_repository),
) -> AlternativesResponseDto:
    """Selection is exploratory state only -- never creates a
    QuoteVersion and never calculates a price."""
    quote = _load_quote(quote_repository, quote_id)
    if not scenario_repository.workspace_exists(quote_id):
        raise HTTPException(status_code=404, detail=f"No active workspace for quote {quote_id}")
    workspace = scenario_repository.get_workspace(quote_id)
    _require_fresh_workspace(quote, workspace)

    try:
        if request.scenario_id is None:
            scenario_repository.clear_selection(quote_id)
        else:
            scenario_repository.select_scenario(quote_id, request.scenario_id)
    except (WorkspaceNotFoundError, ScenarioNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    workspace = scenario_repository.get_workspace(quote_id)
    return _alternatives_to_dto(quote, workspace)


@router.post("/{quote_id}/alternatives/restart", response_model=AlternativesResponseDto)
def restart_alternatives(
    quote_id: str,
    quote_repository: QuoteRepository = Depends(get_quote_repository),
    scenario_repository: ScenarioRepository = Depends(get_scenario_repository),
) -> AlternativesResponseDto:
    """Discard the active (possibly stale) workspace and begin fresh
    exploration from the quote's current committed version. Never
    copies old alternatives forward; never touches Quote history."""
    quote = _load_quote(quote_repository, quote_id)
    if scenario_repository.workspace_exists(quote_id):
        scenario_repository.clear_workspace(quote_id)
    workspace = create_scenario_workspace(quote)
    scenario_repository.create_workspace(workspace)
    return _alternatives_to_dto(quote, workspace)


@router.post(
    "/{quote_id}/revisions/from-selected-alternative",
    response_model=QuoteResponseDto,
)
def create_revision_from_selected_alternative(
    quote_id: str,
    quote_repository: QuoteRepository = Depends(get_quote_repository),
    scenario_repository: ScenarioRepository = Depends(get_scenario_repository),
) -> QuoteResponseDto:
    """The explicit commitment boundary for negotiation: promotes the
    workspace's selected Scenario into the next durable QuoteVersion,
    reusing its snapshots exactly (no calculate_quote call), then clears
    the workspace. QuoteRepository.append_version's expected-version
    guard is the authoritative concurrency protection -- this endpoint's
    own staleness check is an early, friendlier rejection for the common
    (non-racing) case, not a substitute for it.
    """
    quote = _load_quote(quote_repository, quote_id)
    if not scenario_repository.workspace_exists(quote_id):
        raise HTTPException(status_code=404, detail=f"No active workspace for quote {quote_id}")
    workspace = scenario_repository.get_workspace(quote_id)
    _require_fresh_workspace(quote, workspace)

    if workspace.selected_scenario is None:
        raise HTTPException(status_code=400, detail="No alternative has been selected for promotion.")

    try:
        new_version = promote_selected_scenario(quote, workspace)
    except ScenarioError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        quote_repository.append_version(
            quote_id, new_version, expected_current_version=workspace.base_version_number
        )
    except QuoteVersionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    scenario_repository.clear_workspace(quote_id)

    promoted_quote = quote_repository.get(quote_id)
    return _quote_to_response_dto(promoted_quote)


@router.post("/{quote_id}/budget-fit", response_model=QuoteLinkedBudgetFitResponseDto)
def quote_linked_budget_fit(
    quote_id: str,
    request: QuoteLinkedBudgetFitRequestDto,
    quote_repository: QuoteRepository = Depends(get_quote_repository),
    budget_fit_run_repository: BudgetFitRunRepository = Depends(get_budget_fit_run_repository),
) -> QuoteLinkedBudgetFitResponseDto:
    """Runs the real optimizer against the Quote's own current committed
    configuration -- the client never resends a baseline -- and persists
    the run so a chosen recommendation can later become a Scenario
    without recalculation."""
    quote = _load_quote(quote_repository, quote_id)
    version = quote.current_version

    constraints = BudgetFitConstraints(
        locked_fields=parse_locked_fields(request.constraints.locked_fields),
        minimum_users=request.constraints.minimum_users,
        required_premium_support=request.constraints.required_premium_support,
        required_implementation_services=request.constraints.required_implementation_services,
    )

    try:
        domain_request = BudgetFitRequest(
            target_budget=request.target_budget,
            baseline_configuration=version.configuration_snapshot,
            constraints=constraints,
            max_recommendations=request.max_recommendations,
        )
        result = find_budget_fit(domain_request, get_pricing_rules())
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    run = BudgetFitRun(
        quote_id=quote_id,
        base_version_number=version.version_number,
        request=domain_request,
        result=result,
    )
    budget_fit_run_repository.create_run(run)

    return QuoteLinkedBudgetFitResponseDto(
        runId=run.run_id,
        quoteId=quote_id,
        baseVersionNumber=version.version_number,
        targetBudget=result.target_budget,
        baselinePrice=result.baseline_price,
        feasibleCandidateCount=result.feasible_candidate_count,
        recommendations=[recommendation_to_dto(rec, request.target_budget) for rec in result.recommendations],
        noFitReason=result.no_fit_reason,
    )
