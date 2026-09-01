# Northstar Pricing Studio — Development Roadmap

This roadmap intentionally sequences **product decisions before implementation**. Completed boxes describe work already present in the portfolio repository; planned boxes should not be represented as production-ready functionality in the application.

## Phase 0 — Product framing and UX

- [x] Fictional business scenario and portfolio boundary
- [x] Initial PRD
- [x] Initial solution architecture
- [x] Initial success metrics
- [x] Product experience blueprint
- [x] Low-fidelity core workflow wireframes
- [x] UI design system
- [x] Define negotiation as a branch from Review Pricing
- [x] Define Budget Fit Optimization product concept
- [x] Define quote versioning / pricing snapshot architecture
- [x] ADR-001: Quote versioning
- [x] ADR-002: Budget Fit optimization approach
- [ ] ADR: Python + Streamlit application choice

## Phase 1 — Pricing-engine foundation

- [x] YAML pricing configuration
- [x] Validated quote/configuration model
- [x] Deterministic pricing engine
- [x] Initial unit tests
- [x] GitHub Actions CI
- [ ] Expand edge-case tests
- [ ] Strengthen configuration validation
- [ ] Formalize structured reason codes / explanations
- [ ] Make rule version explicit in calculation output

## Phase 2 — Quote and scenario domain

**Goal:** create the domain foundation required for negotiation, auditability, and proposal lineage before adding advanced UI behavior.

- [ ] Add `Quote` model
- [ ] Add immutable `QuoteVersion` model
- [ ] Add `PricingSnapshot` model
- [ ] Add `NegotiationContext` model
- [ ] Add `Scenario` model with origin metadata
- [ ] Implement in-memory quote/version service
- [ ] Implement in-memory scenario management
- [ ] Add versioning and scenario unit tests

## Phase 3 — Commercial quote workspace

**Goal:** replace the current demo-form experience with the designed product workflow.

- [x] Streamlit shell
- [ ] Enterprise navigation/application frame
- [ ] Deal Setup experience
- [ ] Configure workspace + persistent summary
- [ ] Review Pricing hierarchy
- [ ] Explainable price bridge
- [ ] Approval-required state
- [ ] Manual scenario creation
- [ ] Scenario comparison
- [ ] Quote/version context in UI

## Phase 4 — Budget Fit Optimization

**Goal:** demonstrate a differentiated negotiation capability without creating a second pricing engine.

- [ ] Budget target and negotiation-context UI
- [ ] Must-have vs flexible attribute controls
- [ ] Candidate configuration generator
- [ ] Canonical-engine candidate pricing
- [ ] Hard-constraint and budget filtering
- [ ] Deterministic scoring/ranking
- [ ] Recommendation diversification
- [ ] Recommendation explanations
- [ ] Budget Fit results screen
- [ ] Feed recommendations into existing scenario comparison
- [ ] Save selected recommendation as a new quote version
- [ ] No-solution UX
- [ ] Budget Fit unit/integration tests

### Budget Fit v1 scope guardrails

- No machine learning
- No autonomous discount decisions
- No separate pricing formulas in the optimizer
- No solver library unless candidate-space growth justifies it
- No claim of "optimal" where the scoring function cannot support that claim; prefer "recommended" or "best-ranked under configured criteria"

## Phase 5 — Persistence and governance

- [ ] Select SQLite or DuckDB persistence
- [ ] Quote history
- [ ] Quote-version persistence
- [ ] Pricing-snapshot persistence
- [ ] Rule-version metadata
- [ ] Activity/audit timeline
- [ ] Approval record model
- [ ] Demonstration approval workflow or state transition

## Phase 6 — Proposal generation

**Goal:** generate customer-facing output from a frozen, eligible pricing decision.

- [ ] Proposal domain model
- [ ] Proposal eligibility check
- [ ] Proposal assembler
- [ ] HTML/Jinja template
- [ ] Proposal preview
- [ ] PDF renderer
- [ ] Proposal version metadata
- [ ] Verify proposal lineage to quote version + pricing snapshot
- [ ] Regression tests preventing proposal repricing/mutation

## Phase 7 — Portfolio polish

- [ ] Live demo deployment
- [ ] Product screenshots / GIF
- [ ] Updated architecture diagram
- [ ] Negotiation/Budget Fit workflow diagram
- [ ] One-page case study
- [ ] Three-minute demo video
- [ ] README demo walkthrough
- [ ] LinkedIn/project write-up

## Suggested GitHub implementation sequence

1. `docs/budget-fit-design` — documentation and ADRs
2. `feat/quote-versioning` — Quote / QuoteVersion / PricingSnapshot models
3. `feat/scenario-management` — scenario state and comparison domain
4. `feat/quote-workspace` — redesigned Streamlit workflow
5. `feat/budget-fit-optimizer` — candidate generation, pricing, ranking
6. `feat/quote-persistence` — durable history and snapshots
7. `feat/proposal-generation` — approved-snapshot-to-document flow

This sequence gives the repository a visible story of **product discovery → UX decision → architecture decision → implementation → validation**.
