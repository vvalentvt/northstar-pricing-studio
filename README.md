# Northstar Pricing Studio

A flagship portfolio case study exploring how a configurable B2B pricing workflow can become a governed commercial workspace for **configuration, explainable pricing, negotiation, approvals, and proposal generation**.

> **Portfolio note:** Northstar Analytics is fictional. This repository does not contain employer data, source code, pricing rules, customer information, terminology, or proprietary business logic.

## Why this project exists

Commercial pricing often lives across spreadsheets, tribal knowledge, approval emails, and manually edited proposal documents. That creates recurring problems:

- pricing logic is difficult to govern and reproduce;
- sellers cannot confidently self-serve standard configurations;
- negotiations often default to discretionary discounting instead of deliberate scope tradeoffs;
- approvals lack a consistent explanation of pricing drivers and exceptions;
- proposals can become disconnected from the exact pricing decision that was approved.

Northstar Pricing Studio treats the **pricing engine as one capability inside a broader commercial decision system**.

## Fictional business scenario

**Northstar Analytics** sells B2B market-intelligence subscriptions to enterprise customers. Pricing varies by subscription tier, users, geographic coverage, historical depth, contract term, support, implementation services, discount level, and renewal status.

A customer may also enter a negotiation with a fixed budget. Instead of simply discounting the original package until it fits, Northstar can evaluate alternative valid configurations and recommend the strongest product/service mix that satisfies the customer's budget and must-have requirements.

## Product thesis

A credible pricing product should help a commercial user answer:

1. What am I selling?
2. What should it cost?
3. Why is that the price?
4. If the customer cannot buy this configuration, what can they buy within budget?
5. Does the commercial decision require approval?
6. Which exact approved configuration should become the proposal?

## Core product capabilities

### Implemented foundation

- YAML-driven pricing rules
- Pydantic configuration models
- Deterministic Python pricing engine
- Itemized pricing adjustments and explanations
- Discount-policy evaluation
- Streamlit UI shell
- Automated tests
- GitHub Actions CI

### Designed / planned workflow

- Quote and quote-version management
- Explainable quote review
- Scenario creation and comparison
- **Budget Fit Optimization** for budget-constrained negotiations
- Approval-state handling
- Versioned pricing snapshots
- Proposal assembly from an approved pricing snapshot
- Quote history and audit trail

The repository intentionally distinguishes working functionality from designed future capability.

## Budget Fit Optimization

Budget Fit is a negotiation workflow that asks:

> **Given a target budget and customer constraints, what is the highest-value valid configuration Northstar can offer without exceeding the budget?**

The optimizer does **not** calculate prices independently. It generates candidate configurations, sends each candidate through the same deterministic pricing engine, filters invalid or over-budget candidates, and ranks the remaining alternatives according to customer requirements and commercial priorities.

```text
Target Budget + Constraints
            |
            v
Configuration Optimizer
            |
            v
Candidate Configurations
            |
            v
      Pricing Engine <------ YAML Rule Configuration
            |
            v
Eligible Priced Scenarios
            |
            v
Rank + Explain Recommendations
```

This approach preserves one source of truth for pricing while allowing Northstar to support a more realistic negotiation workflow.

## Commercial workflow

```text
Deal Setup
    |
    v
Configure
    |
    v
Review Pricing <------> Negotiate / Explore
    |                        |
    |                        +--> Manual Scenario
    |                        |
    |                        +--> Optimize to Budget
    |                                  |
    |                                  v
    |                           Compare Scenarios
    |                                  |
    +----------------------------------+
    |
    v
Approval when required
    |
    v
Approved Pricing Snapshot
    |
    v
Proposal
```

Negotiation is a branch from pricing review, not a mandatory wizard step.

## Target architecture

```text
Streamlit UI
    |
    v
Application / Workflow Services
    |
    +--> Quote / Version Service ------> Persistence
    |
    +--> Scenario Service
    |       |
    |       +--> Budget Fit Optimizer
    |                |
    |                v
    +-----------> Pricing Engine ------> YAML Rule Configuration
    |
    +--> Approval Service [later]
    |
    +--> Proposal Assembler -----------> HTML/PDF Renderer [later]
```

The pricing engine remains deterministic and independent of UI, persistence, optimization, approval routing, and proposal rendering.

## Frontend migration (in progress)

Northstar's visual presentation is migrating from Streamlit to a dedicated
React frontend, incrementally and workflow by workflow. **This is not
complete.** See [ADR-003](docs/adr/003-frontend-api-separation.md) for the
full decision and [`docs/FRONTEND_SPIKE.md`](docs/FRONTEND_SPIKE.md) for the
visual feasibility spike that motivated it.

**Current, both fully functional and running against the same Python domain:**

```text
Streamlit (app/)  ---> app/app_state.py ---> src/pricing_engine, src/quotes, src/budget_fit
React (frontend/) ---> FastAPI (api/)   ---> src/pricing_engine, src/quotes, src/budget_fit
```

- `app/` — the original, complete Streamlit application (Deal Setup through Review Pricing, Scenario negotiation, Budget Fit, Budget Fit → Scenario → QuoteVersion promotion). Still entirely `st.session_state`-backed — it has **not** been migrated to SQLite, and its own Quote history is independent of the API's.
- `frontend/` + `api/` — as of Phase 6D, **the full quote-creation path is migrated and no longer needs Streamlit or Swagger**:
  - **New Quote / Deal Setup** (`/quotes/new/setup`) — captures customer, owner, and deal type (New Business / Renewal). A temporary draft only (sessionStorage-backed, see `frontend/src/features/quote-draft/`) — nothing is persisted yet.
  - **Configure** (`/quotes/new/configure`) — product/scope/services/commercial-terms form. Pricing options (tiers, coverage, terms, discount guardrails) come from `GET /api/pricing/options`, derived live from `config/pricing_rules.yaml`. "Calculate Pricing" calls the stateless `POST /api/pricing/preview` (same canonical `calculate_quote()` engine, persists nothing); the preview goes stale the moment the configuration changes again, and a stale preview can't be committed.
  - **Review Pricing →** on Configure is the commitment boundary: it calls `POST /api/quotes`, which recalculates canonically server-side and persists Quote v1 to SQLite, then navigates to `/quotes/{quoteId}/review`.
  - **Review Pricing** (`/quotes/{quoteId}/review`) — a read-only view of a durable Quote's current committed `QuoteVersion` / `PricingSnapshot`, fetched from `GET /api/quotes/{quoteId}`. Never recalculates pricing. Directly linkable and refresh-safe — Quote identity lives in the database, not in frontend session state.
  - **Optimize to Budget** (`/budget-fit`) — standalone mode (no `quoteId`) calls the stateless `POST /api/budget-fit` against a static fixture baseline. Launched from Review Pricing or Alternatives as `/budget-fit?quoteId=<id>`, it instead calls `POST /api/quotes/{quoteId}/budget-fit`: the baseline comes from the Quote's own current committed configuration (never resent by the client), and the run is persisted so a chosen recommendation can be added to Alternatives without recalculation.
  - **Explore Alternatives** (`/quotes/{quoteId}/alternatives`) — compares the committed baseline against exploratory `Scenario`s (manual, or added from a Budget Fit run) in a durable negotiation workspace (`GET/POST/PUT /api/quotes/{quoteId}/alternatives...`). Selecting a Scenario and clicking **Create Quote Revision →** (`POST /api/quotes/{quoteId}/revisions/from-selected-alternative`) is the one action that creates the next `QuoteVersion` — it reuses the selected Scenario's own snapshots exactly, never recalculating. A workspace anchored to an older `QuoteVersion` than the Quote's current one is **stale**: Select/Add/Promote are all blocked until the user starts fresh exploration from the current version.

Neither `src/pricing_engine`, `src/quotes`, nor `src/budget_fit` has a second implementation for the API — both presentation layers call the same domain functions, including the shared orchestration in `src/application/quotes.py` and `src/application/scenarios.py`. SQLite (`src/persistence`) persists `Quote`/`QuoteVersion` (immutable commercial history, [ADR-004](docs/adr/004-quote-persistence.md)) and, separately, the active `ScenarioWorkspace`/`Scenario` and quote-linked Budget Fit run state (mutable exploratory negotiation state, [ADR-005](docs/adr/005-negotiation-workspace-persistence.md)).

**Still in Streamlit only:** the Proposal workflow. Quote listing/search and approval routing do not exist in either presentation layer yet.

## Local setup

### React + FastAPI (recommended)

```bash
npm install          # once, at the repo root -- installs the dev-runner only
npm run dev           # starts FastAPI (http://localhost:8000) and Vite (http://localhost:5173) together
```

Open `http://localhost:5173` — `/` redirects straight to New Quote / Deal Setup. Swagger is still available at `http://localhost:8000/docs` for manual API poking, but normal quote creation no longer needs it.

The root `npm run dev` script assumes a `.venv` already exists with `requirements.txt` installed (see Streamlit setup below) and invokes `.venv\Scripts\python.exe` directly; adjust `package.json`'s `dev:api` script if your virtualenv lives elsewhere.

### Streamlit

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

### React + FastAPI (manual, two terminals)

```bash
# Terminal 1 — API
pip install -r requirements.txt
python -m uvicorn api.main:app --reload    # http://localhost:8000

# Terminal 2 — frontend
cd frontend
npm install
npm run dev                                # http://localhost:5173
```

### Tests

From the repo root (delegates to the same commands below):

```bash
npm test            # Python domain, application, and API tests
npm run test:web    # React component tests (Vitest + React Testing Library)
npm run build        # TypeScript typecheck + production build
```

Or directly:

```bash
python -m pytest tests/ -q       # Python domain, application, and API tests
cd frontend && npm run test      # React component tests (Vitest + React Testing Library)
cd frontend && npm run build     # TypeScript typecheck + production build
```

## What this project demonstrates

**Product thinking:** problem framing, personas/JTBD, workflow design, MVP boundaries, negotiation experience, roadmap, and product tradeoffs.
**Pricing & monetization:** packaging, configurable rules, discount governance, scenario modeling, value-preserving negotiation, and explainability.
**Solution architecture:** domain modeling, quote versioning, immutable pricing snapshots, service boundaries, auditability, and proposal lineage.
**Engineering:** Python, Pydantic, YAML, modular services, automated testing, CI, and eventually persistence and document generation.

## Planned success metrics

| Metric | Target |
| --- | ---: |
| Median standard quote configuration time | < 10 minutes |
| Supported standard pricing configurations | >= 80% |
| Saved quotes reproducible from configuration + rule version | 100% |
| Non-zero pricing adjustments explained | 100% |
| Budget Fit recommendations satisfy all declared hard constraints | 100% |
| Budget Fit recommendations priced by the canonical pricing engine | 100% |
| Invalid configuration caught before proposal | 100% |
| Proposal traceable to a specific approved quote version | 100% |
| Automated coverage of core pricing rules | >= 90% |

## Documentation

- [`docs/PRD.md`](docs/PRD.md) — product requirements and acceptance criteria
- [`docs/PRODUCT_DESIGN.md`](docs/PRODUCT_DESIGN.md) — product experience blueprint
- [`docs/WIREFRAMES.md`](docs/WIREFRAMES.md) — low-fidelity screen and interaction design
- [`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md) — UI and interaction conventions
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — target solution architecture and domain model
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — staged implementation roadmap
- [`docs/adr/`](docs/adr/) — architecture decision records, including [ADR-003](docs/adr/003-frontend-api-separation.md) on the frontend/API migration, [ADR-004](docs/adr/004-quote-persistence.md) on Quote persistence, and [ADR-005](docs/adr/005-negotiation-workspace-persistence.md) on negotiation workspace persistence
- [`docs/FRONTEND_SPIKE.md`](docs/FRONTEND_SPIKE.md) — the visual feasibility spike that motivated the migration
