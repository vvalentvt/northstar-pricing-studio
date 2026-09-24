# ADR-004: Persist the Quote resource behind the API using SQLite

- **Status:** Accepted
- **Date:** 2026-09-24
- **Decision owners:** Northstar Pricing Studio portfolio project

## Context

Through Phase 6A, `api/` is entirely stateless: `POST /api/budget-fit` calculates and returns a result but never stores it. Streamlit's own Quote history (`app/app_state.py`) lives only in `st.session_state` — real per-user commercial history, but scoped to one browser tab's process memory and gone the moment the session ends.

A browser/API application cannot rely on that model. A quote committed through the React/FastAPI path must survive a page reload, a server restart, and being looked up by a second request — none of which session state can do. Northstar needed its first durable, application-owned resource.

The domain already models exactly what needs to survive: `Quote` (`src/quotes/models.py`) is an aggregate with an append-only, sequentially-validated tuple of immutable `QuoteVersion` snapshots. The persistence question was narrowly "how do we make this durable," not "what should be durable" — the shape was already decided by ADR-001's quote-versioning design.

## Decision

Introduce a repository boundary, `QuoteRepository` (`src/persistence/quote_repository.py`), as a `typing.Protocol` with exactly the operations this phase (and the append-only invariant future phases depend on) needs: `create`, `get`, `get_version`, `exists`, `append_version` — deliberately not a generic CRUD interface.

Implement it once, concretely, with SQLite (`SQLiteQuoteRepository`, `src/persistence/sqlite_quote_repository.py`) using Python's stdlib `sqlite3` directly — no ORM. Two tables mirror the domain's own shape:

```text
quotes          -- one row per Quote (aggregate metadata)
quote_versions  -- one row per QuoteVersion, composite PK (quote_id, version_number), FK to quotes
```

`ConfigurationSnapshot`, `PricingSnapshot`, and `NegotiationContext` are stored as JSON text via each frozen Pydantic model's own `model_dump_json()`, and rehydrated via `model_validate_json()` on read. The domain models remain the sole authority on what a valid persisted state looks like — the repository does not re-implement or duplicate validation, and never recomputes a version's pricing from current rules on load.

`append_version` never updates or replaces a row; a revision is always a new row at `version_number = current + 1`, enforced by an optimistic-concurrency check (`expected_current_version` must match the stored current version, executed inside an explicit `BEGIN IMMEDIATE` transaction so the check-then-write sequence is atomic against concurrent writers) that raises `QuoteVersionConflict` — never a raw `sqlite3.IntegrityError` — on mismatch.

`POST /api/quotes` always calculates v1 server-side via the same shared `src/application/quotes.py` orchestration Streamlit's commit flow now also delegates to (extracted this phase to avoid duplicating the quote-creation algorithm between presentation layers) — a client can only ever supply a configuration, never a price.

Streamlit is explicitly **not** migrated to SQLite in this phase. It continues to use `st.session_state` exactly as before. The two Quote stores — Streamlit's session-backed quotes and the API's SQLite-backed quotes — are separate and unsynchronized; a quote created in one is not visible in the other. Scenario, ScenarioWorkspace, and Budget Fit view state also remain entirely unpersisted.

## Why SQLite now

- Single-file, zero-infrastructure, stdlib-supported — no new dependency, no server process, matches the portfolio project's local-first scope.
- Real transactional guarantees (ACID, foreign keys, atomic multi-row writes) that an append-only, integrity-sensitive history (Quote → QuoteVersion) genuinely needs — a flat-file/JSON store would not give this for free.
- The relational shape (one Quote, many QuoteVersions) is a natural fit for two normalized tables with a foreign key, not a document blob.

## Why not earlier

Phases 1–5 (pricing engine, quote versioning, scenario negotiation, Budget Fit) were correctly scoped to get the domain model right first. Persisting a resource whose shape was still evolving would have meant repeated schema churn for no benefit — Streamlit's session state was sufficient for validating the domain through Phase 6A. Durable storage only became necessary once a stateless HTTP client (React) needed to look up a quote it didn't just create in the same request.

## Why not DuckDB

`.gitignore` already anticipated a `data/*.duckdb` path, but DuckDB is an analytical (OLAP) engine, optimized for large read-heavy scans and columnar aggregation — not the small, high-integrity, single-row transactional writes (`INSERT ... one Quote`, `INSERT ... one QuoteVersion`, all-or-nothing) this phase needs. SQLite is the standard choice for this OLTP-shaped, single-writer workload; DuckDB remains a reasonable future choice if Northstar ever needs analytical queries over quote history at scale, but that is not this phase's problem.

## Consequences

**Positive**

- Quotes created through the API now survive process restarts — proven by the Persistence Survival Test (`tests/test_quote_repository.py`): a second `SQLiteQuoteRepository` opened against the same file, independent of the one that wrote the data, reads back an identical `Quote`.
- Historical pricing fidelity is structurally guaranteed, not just tested by convention: a `PricingSnapshot` is stored and rehydrated verbatim, so changing pricing rules after the fact cannot alter what a historical version reports — proven by the Historical Rule Change Test.
- The repository boundary (`QuoteRepository` Protocol) means the concrete storage technology is swappable without touching `api/` call sites or the domain.
- No business logic leaked into SQL: every query is either a primary-key lookup or a version-ordering scan; pricing, approval, and version-sequencing rules stay entirely in `src/quotes` and `src/pricing_engine`.

**Trade-offs / known limitations**

- Streamlit and the API now have two independent, unsynchronized Quote stores. This is an explicit, temporary state of the strangler migration, not an oversight — see ADR-003.
- No migrations tooling (Alembic or similar) is introduced; schema changes so far are additive (`CREATE TABLE IF NOT EXISTS`), which is sufficient for a single-developer, pre-production project but will need real migration tooling before this survives a shared/production deployment.
- `SQLiteQuoteRepository` assumes a single-process, single-writer workload (appropriate for local/portfolio use); it has not been evaluated under concurrent multi-process write load.
- Quote search, listing/dashboarding, and any form of query beyond by-ID and by-version lookup are out of scope for this phase.

## Configuration

The database path is configurable via the `NORTHSTAR_DB_PATH` environment variable, defaulting to `data/northstar.db`. Schema initialization is idempotent and runs once at process startup via FastAPI's `lifespan` context (`api/main.py`), not the deprecated `@app.on_event("startup")`.
