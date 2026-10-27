# ADR-005: Persist the negotiation workspace (Scenarios + Budget Fit runs) in SQLite

- **Status:** Accepted
- **Date:** 2026-10-26
- **Decision owners:** Northstar Pricing Studio portfolio project

## Context

Phase 6B gave the API durable commercial history: `Quote`/`QuoteVersion`, persisted in SQLite, append-only. But Northstar's negotiation workflow — Explore Alternatives, Optimize to Budget, comparing options, selecting one, promoting it into the next `QuoteVersion` — existed only in Streamlit's `st.session_state` (`ScenarioWorkspace`, `Scenario`, `BudgetFitViewState`). An HTTP client can't rely on that: a React page that creates a Budget Fit recommendation in one request and wants to "Add to Alternatives" in a later request needs that recommendation's exact snapshots to still exist on the server.

Two distinct things needed to survive requests:

1. **The exploratory workspace itself** — `ScenarioWorkspace` and the `Scenario`s a user has saved or is comparing, anchored to a specific committed `QuoteVersion`.
2. **Budget Fit recommendation lineage** — the exact `BudgetFitRequest`/`BudgetFitResult` a quote-linked search produced, so "Add to Alternatives" never needs to recalculate or trust a client-supplied price for a recommendation it already showed the user.

## Decision

Two repositories, both SQLite-backed, both following the same pattern `QuoteRepository` already established (a `typing.Protocol` interface, a concrete `sqlite3`-based implementation, no ORM, idempotent `CREATE TABLE IF NOT EXISTS` schema init):

- **`ScenarioRepository`** (`src/persistence/scenario_repository.py`, `sqlite_scenario_repository.py`) — `scenario_workspaces` (one row per quote's active workspace) + `scenarios` (one row per `Scenario` it contains), mirroring the domain's own `ScenarioWorkspace`/`Scenario` shape. Unlike `quote_versions`, these rows are genuinely mutable: `select_scenario`/`clear_selection` update a column in place, and `clear_workspace` deletes rows outright. This is deliberate — a `ScenarioWorkspace` is exploratory state, not commercial history.
- **`BudgetFitRunRepository`** (`budget_fit_run_repository.py`, `sqlite_budget_fit_run_repository.py`) — one `budget_fit_runs` row per quote-linked Budget Fit search, storing the exact `BudgetFitRequest`/`BudgetFitResult` via their own `model_dump_json()`. Write-once: `create_run` and `get_run` only, no update, no listing. This is not analytical history — it exists purely so a recommendation shown to the user can later become a `Scenario` without recalculation.

Application-layer orchestration (`src/application/scenarios.py`, extracted from `app/app_state.py` in this same phase) decides *when* a workspace is stale, *how* promotion maps a `Scenario` into the next `QuoteVersion`, and *which* `QuoteVersionSource` to use. The repositories never make those decisions — they store exactly what the domain/application layer hands them and return exactly what was stored.

## Clarifications

- **Scenarios are exploratory.** Saving or selecting one never creates a `QuoteVersion`. Only explicit promotion (`ScenarioWorkspace.promote_selected`, via `application.scenarios.promote_selected_scenario`) does, and it reuses the selected `Scenario`'s own `ConfigurationSnapshot`/`PricingSnapshot`/`NegotiationContext` — it never calls `calculate_quote()`.
- **QuoteVersions remain immutable.** This phase adds no new way to write to `quote_versions`; promotion still goes through the existing `QuoteRepository.append_version`'s optimistic-concurrency guard.
- **Budget Fit run persistence is operational, not analytical.** It exists only to preserve recommendation identity across the two requests ("run Budget Fit" → "add this recommendation") that a stateless HTTP API splits into separate calls. Standalone `/api/budget-fit` demo calls are never persisted.
- **A successful promotion clears the exploratory workspace.** The next exploration starts fresh from the new `QuoteVersion` — old alternatives are not carried forward or reinterpreted against the new baseline.
- **A stale workspace** (`base_version_number != quote.current_version.version_number`) is rejected by promotion, not silently rebased. The repository has no opinion on staleness; it's a property the API computes by comparing what the workspace repository and quote repository each return.

## Consequences

**Positive**

- The full negotiation lifecycle — create alternatives, compare, select, promote — now works identically whether accessed from React/FastAPI or (unchanged) from Streamlit's own session state, without either presentation layer reimplementing scenario rules.
- Recommendation lineage survives across HTTP requests without ever re-running the optimizer or trusting a client-supplied price.
- Clearing a workspace is a targeted, explicit delete (`scenarios` + `scenario_workspaces` rows only) — it can never touch `quotes`/`quote_versions`, since the repository has no method that does.

**Trade-offs / known limitations**

- One active workspace per quote only; no history of past exploration rounds once a workspace is cleared.
- `budget_fit_runs` has no expiry/cleanup — a run row persists even after its base version goes stale. Acceptable at this scale; would need pruning before production use.
- As with `QuoteRepository`, this assumes a single-process, single-writer workload.
