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

- `app/` — the original, complete Streamlit application (Deal Setup through Review Pricing, Scenario negotiation, Budget Fit, Budget Fit → Scenario → QuoteVersion promotion). Still the only complete workflow, and still entirely `st.session_state`-backed — it has **not** been migrated to SQLite.
- `frontend/` + `api/` — two migrated screens so far:
  - **Optimize to Budget** (`/budget-fit`) — calls a real `POST /api/budget-fit` endpoint that runs the actual optimizer (`src/budget_fit.find_budget_fit`). Stateless by default (a static baseline fixture); when launched as `/budget-fit?quoteId=<id>`, the baseline instead comes from a real persisted Quote.
  - **Review Pricing** (`/quotes/{quoteId}/review`) — a read-only view of a durable Quote's current committed `QuoteVersion` / `PricingSnapshot`, fetched from `GET /api/quotes/{quoteId}`. It never recalculates pricing; every figure shown (final price, price bridge, approval state, guardrail thresholds) is exactly what was persisted at commit time. Directly linkable and refresh-safe — Quote identity lives in the database, not in frontend session state.

Neither `src/pricing_engine`, `src/quotes`, nor `src/budget_fit` has a second implementation for the API — both presentation layers call the same domain functions, including the shared quote-creation orchestration in `src/application/quotes.py`.

**Durable Quote persistence (Phase 6B).** The API has its own durable Quote resource: `POST /api/quotes`, `GET /api/quotes/{quoteId}`, and `GET /api/quotes/{quoteId}/versions/{versionNumber}`, backed by SQLite (`src/persistence`, see [ADR-004](docs/adr/004-quote-persistence.md)). This is **not** the same Quote store Streamlit uses — a quote created through the API is not visible in Streamlit and vice versa; the two presentation layers' Quote histories are independent and unsynchronized during this migration.

**Still in Streamlit only:** Deal Setup, Configure, Scenario negotiation / Explore Alternatives, and the Proposal workflow. Quote listing/search, scenario persistence, and approval routing do not exist in either presentation layer yet.

## Local setup

### Streamlit

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

### React + FastAPI

```bash
# Terminal 1 — API
pip install -r requirements.txt
python -m uvicorn api.main:app --reload    # http://localhost:8000

# Terminal 2 — frontend
cd frontend
npm install
npm run dev                                # http://localhost:5173
```

`/` redirects to `/budget-fit`. To open Review Pricing directly during development, create a quote via the API's Swagger UI (`http://localhost:8000/docs` → `POST /api/quotes`) and navigate to `http://localhost:5173/quotes/{quoteId}/review` — this route is directly linkable and survives a browser refresh, since Quote identity lives in SQLite, not frontend state.

### Tests

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
- [`docs/adr/`](docs/adr/) — architecture decision records, including [ADR-003](docs/adr/003-frontend-api-separation.md) on the frontend/API migration and [ADR-004](docs/adr/004-quote-persistence.md) on Quote persistence
- [`docs/FRONTEND_SPIKE.md`](docs/FRONTEND_SPIKE.md) — the visual feasibility spike that motivated the migration
