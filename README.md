# Northstar Pricing Studio

A governed commercial pricing workspace for B2B SaaS: configurable pricing, explainable price breakdowns, budget-constrained negotiation, approval authority, and durable proposal generation — built as a flagship portfolio case study.

> **Portfolio note:** Northstar Analytics is fictional. This repository does not contain employer data, source code, pricing rules, customer information, terminology, or proprietary business logic.

## What it solves

Commercial pricing often lives across spreadsheets, tribal knowledge, approval emails, and manually edited proposal documents. That creates recurring problems:

- pricing logic is difficult to govern and reproduce;
- sellers cannot confidently self-serve standard configurations;
- negotiations often default to discretionary discounting instead of deliberate scope tradeoffs;
- approvals lack a consistent explanation of pricing drivers and exceptions;
- proposals can become disconnected from the exact pricing decision that was approved.

Northstar treats **configurable B2B pricing, pricing authority, negotiation alternatives, budget-constrained optimization, immutable quote revisions, and proposal artifacts** as one governed commercial decision system rather than six disconnected tools.

## Fictional business scenario

**Northstar Analytics** sells B2B market-intelligence subscriptions to enterprise customers. Pricing varies by subscription tier, users, geographic coverage, historical depth, contract term, support, implementation services, discount level, and renewal status.

A customer may also enter a negotiation with a fixed budget. Instead of simply discounting the original package until it fits, Northstar evaluates alternative valid configurations and recommends the strongest product/service mix that satisfies the customer's budget and must-have requirements — **Budget Fit**.

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

The optimizer never calculates prices independently — every candidate runs through the same deterministic pricing engine used everywhere else, preserving one source of truth for price.

## Product workflow

```text
Quotes (index)
    |
    v
Deal Setup
    |
    v
Configure --------> Pricing Preview
    |
    v
Quote v1 (committed)
    |
    v
Review Pricing
    |
    v
Alternatives  <---- Manual Alternative
    |          <---- Budget Fit
    v
Quote Revision (v2, immutable)
    |
    v
Review Pricing (v2)
    |
    v
Proposal -> downloadable PDF
```

Negotiation (Alternatives / Budget Fit) is a branch from Review Pricing, not a mandatory wizard step. The entire workflow runs in the browser — no Swagger, no separate admin tool.

## Key product decisions

- **Configuration vs. commitment** — editing a configuration and previewing a price never touches durable state; a Quote is only created on explicit commitment, and the server always recalculates canonically at that moment (a client can never supply its own price).
- **Immutable QuoteVersions** — a committed Quote's pricing history is append-only. Revising a Quote creates a new version; it never rewrites one.
- **Exploratory Scenarios** — Alternatives are a mutable negotiation workspace, explicitly separate from commercial history, until one is promoted into the next QuoteVersion.
- **Budget Fit optimization** — a search layer above the pricing engine, never a second pricing engine.
- **Explainable pricing** — every adjustment on a price carries a human-readable reason; approval state is derived and stored, never guessed from today's rules later.
- **Snapshot-based proposals** — a generated Proposal freezes the exact ConfigurationSnapshot/PricingSnapshot of the QuoteVersion it came from. Later quote revisions or rule changes never alter a previously generated Proposal or its PDF.

## Architecture

```text
React SPA (frontend/)
        |  HTTP (JSON + typed DTOs)
        v
FastAPI boundary (api/)
        |
        v
Application services (src/application) -- Quotes, Scenarios, Proposals
        |
        v
Domain (src/) -- Pricing Engine, Budget Fit, Quote Versioning, Scenario Lifecycle
        |
        v
SQLite (src/persistence)
```

In production, FastAPI serves the built React SPA same-origin alongside the API — one process, one deployable unit. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full breakdown and [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for how to run it.

Neither `src/pricing_engine`, `src/quotes`, nor `src/budget_fit` has a second implementation for the API — the FastAPI boundary calls the same domain functions and shared orchestration (`src/application/quotes.py`, `src/application/scenarios.py`, `src/application/proposals.py`) that are directly unit-tested. SQLite persists three distinct things, each with a different mutability contract:

- `Quote` / `QuoteVersion` — immutable commercial history ([ADR-004](docs/adr/004-quote-persistence.md));
- the active `ScenarioWorkspace` / `Scenario` and quote-linked Budget Fit run state — mutable exploratory negotiation state ([ADR-005](docs/adr/005-negotiation-workspace-persistence.md));
- generated `Proposal` artifacts, including the rendered PDF bytes — immutable, append-only ([ADR-006](docs/adr/006-proposal-artifacts.md)).

## Screenshots

_Not yet captured in this environment — see [`docs/PUBLIC_RELEASE_CHECKLIST.md`](docs/PUBLIC_RELEASE_CHECKLIST.md) for the capture checklist (Quotes, Configure, Review Pricing, Budget Fit, Alternatives, Proposal workspace, generated PDF)._

## Running locally

```bash
npm install          # once, at the repo root -- installs the dev-runner only
pip install -r requirements.txt   # or: .venv\Scripts\python.exe -m pip install -r requirements.txt
npm run dev           # starts FastAPI (http://localhost:8000) and Vite (http://localhost:5173) together
```

Open `http://localhost:5173` — `/` lands on the Quotes index. Swagger is still available at `http://localhost:8000/docs` for manual API poking, but the full workflow never needs it.

The root `npm run dev` script invokes `.venv\Scripts\python.exe` directly for the API process; adjust `package.json`'s `dev:api` script if your virtualenv lives elsewhere.

### Manual, two terminals

```bash
# Terminal 1 — API
pip install -r requirements.txt
python -m uvicorn api.main:app --reload    # http://localhost:8000

# Terminal 2 — frontend
cd frontend
npm install
npm run dev                                # http://localhost:5173
```

## Testing

From the repo root (delegates to the commands below):

```bash
npm test            # Python domain, application, and API tests
npm run test:web    # React component tests (Vitest + React Testing Library)
npm run build        # TypeScript typecheck + production build
npm run validate     # build + test:web + test, in that order
```

Or directly:

```bash
python -m pytest tests/ -q       # Python domain, application, and API tests
cd frontend && npm run test      # React component tests (Vitest + React Testing Library)
cd frontend && npm run build     # TypeScript typecheck + production build
```

## Deployment

Northstar deploys as one process: FastAPI serves the API and the built React SPA from the same origin, backed by a single SQLite file on persistent storage. See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for the Docker image, environment variables, and persistence requirements.

```text
Demo environment — use fictional or non-sensitive data. There is no authentication.
```

## What this project demonstrates

**Product thinking:** problem framing, workflow design, MVP boundaries, negotiation experience, and product tradeoffs.
**Pricing & monetization:** packaging, configurable rules, discount governance, scenario modeling, value-preserving negotiation, and explainability.
**Solution architecture:** domain modeling, quote versioning, immutable pricing snapshots, service boundaries, auditability, and proposal lineage.
**Engineering:** Python, Pydantic, FastAPI, React/TypeScript, SQLite, deterministic document generation, and a comprehensive automated test suite across domain, application, API, persistence, and React layers.

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
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — solution architecture and domain model
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — running the production Docker image
- [`docs/PUBLIC_RELEASE_CHECKLIST.md`](docs/PUBLIC_RELEASE_CHECKLIST.md) — public-release readiness checklist
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — staged implementation roadmap
- [`docs/adr/`](docs/adr/) — architecture decision records: [ADR-003](docs/adr/003-frontend-api-separation.md) (frontend/API migration, including the now-retired Streamlit prototype), [ADR-004](docs/adr/004-quote-persistence.md) (Quote persistence), [ADR-005](docs/adr/005-negotiation-workspace-persistence.md) (negotiation workspace persistence), [ADR-006](docs/adr/006-proposal-artifacts.md) (Proposal artifacts)
- [`docs/FRONTEND_SPIKE.md`](docs/FRONTEND_SPIKE.md) — the visual feasibility spike that motivated the frontend migration

## Portfolio notes

Northstar Pricing Studio is a fictional product built for a portfolio. It contains no employer-proprietary code, pricing rules, customer data, or terminology. It has no authentication and is not a production system — see `docs/ARCHITECTURE.md` section 15 for the explicit security/portfolio boundaries this project does and does not implement.
