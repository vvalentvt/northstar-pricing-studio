# Northstar Development History

This document tells the honest evolution of Northstar Pricing Studio as a product and a software system — not a reformatted `git log`. It exists so a reader can understand *why* the system looks the way it does, in the order decisions were actually made.

For the decisions with lasting technical consequences, see [`docs/adr/`](adr/). This document is the narrative; the ADRs are the record.

## Foundation

**Problem.** A portfolio pricing tool is only credible if it is grounded in a real (if fictional) commercial problem, not a bare CRUD form. Before any code, Northstar needed a product framing: who uses it, what decisions it supports, and where the boundary of the MVP sits.

**Decision.** Establish the product shape first — [`docs/PRD.md`](PRD.md), [`docs/PRODUCT_DESIGN.md`](PRODUCT_DESIGN.md), [`docs/WIREFRAMES.md`](WIREFRAMES.md), and [`docs/DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md) — plus a target architecture ([`docs/ARCHITECTURE.md`](ARCHITECTURE.md)) describing a pricing engine as one capability inside a larger commercial decision system, before building UI screens.

**Outcome.** A deterministic, YAML-driven pricing engine (Pydantic request/result models, itemized adjustments, discount-policy evaluation) with automated tests and CI, plus documented negotiation and Budget Fit architecture, landed as the project's starting point.

## Quote Domain

**Problem.** A pricing configuration changes during negotiation. If a quote were a single mutable record, editing it would destroy the answer to basic commercial questions: what was originally offered, what changed, and which exact configuration a proposal was generated from.

**Decision.** [ADR-001](adr/001-quote-versioning.md) models a `Quote` as a durable container of append-only, immutable `QuoteVersion`s, each carrying its own `ConfigurationSnapshot` and `PricingSnapshot`. Versions are never edited in place; a change always produces a new version.

**Outcome.** `feat(quotes): add immutable quote-versioning domain model`, hardened immediately after by `fix(quotes): enforce deep immutability of quote version history` once nested-mutation gaps were found. The invariant proven by tests: no operation on a `Quote` can alter an already-saved `QuoteVersion`.

## Pricing Workflow

**Problem.** A pricing engine and a versioning domain are not yet a usable tool. Someone needs to walk through configuring a deal and reviewing the resulting price.

**Decision.** Build the Streamlit application shell around the linear path a seller actually follows: Deal Setup → Configure → Review Pricing. Quote commitment was deliberately placed *behind* an explicit Review Pricing boundary rather than happening implicitly on configuration, so a `QuoteVersion` is only created for a state a user has actually reviewed.

**Outcome.** `feat(app): build application shell, Deal Setup, and Configure UI`, followed by `fix(app): move Quote commitment behind an explicit Review Pricing boundary` and `feat(app): build Review Pricing screen and minimal Proposal placeholder`.

## Pricing Governance

**Problem.** A price without an explanation is not a governable commercial decision. Sellers and approvers need to see *why* a price is what it is, and discount-authority thresholds must survive exactly as computed, not be silently re-derived from possibly-changed rules.

**Decision.** Carry itemized pricing adjustments and discount-authority/approval state through the `PricingSnapshot` itself rather than recomputing them at display time.

**Outcome.** `fix(pricing): preserve discount-authority thresholds in PricingSnapshot` and `fix(app): fix bold price-bridge rendering and align decision-header states` — both fixes converging on the same principle: what a user reviewed and what gets displayed/approved must be the same data, not a fresh recalculation.

## Negotiation

**Problem.** Real negotiations are not single-shot: a customer proposes alternatives, a seller explores them, compares them against the original, and only one path is ultimately promoted into the quote's real history.

**Decision.** Introduce a `Scenario` domain (exploration, comparison, promotion) that sits *alongside* a `Quote`'s committed versions without mutating them until a scenario is explicitly promoted. A `ScenarioWorkspace` tracks staleness against the quote's `current_version` so a promotion can never silently apply against an configuration that has since moved on.

**Outcome.** `feat(scenarios): add scenario exploration and promotion domain model`, hardened by `fix(scenarios): reject stale promotions and duplicate scenario ids`, then surfaced in the UI across three incremental phases: `feat(app): add manual scenario exploration to Review Pricing`, `feat(app): add scenario comparison to Review Pricing` (corrected by `fix(app): resolve scenario comparison baseline from workspace, not current_version`), and `feat(app): add scenario selection and quote-revision promotion`. The invariant proven by tests: selecting or comparing scenarios never changes `quote.versions`; only an explicit promotion appends a new version.

## Budget Fit

**Problem.** When a customer's budget doesn't fit the current configuration, the default commercial move is discretionary discounting. That erodes margin and isn't reproducible. A better answer is: search for an alternative, valid configuration that fits the budget through product/service trade-offs *before* touching discount.

**Decision.** [ADR-002](adr/002-budget-fit-optimization.md) places Budget Fit *above* the canonical pricing engine, never re-implementing pricing logic: it enumerates a bounded, rule-derived configuration space, prices every candidate through the same `pricing_engine.calculate_quote` used everywhere else, filters by budget and hard constraints, and ranks the survivors by a transparent, deterministic, multi-factor score. Capability scoring went through two subsequent refinements — decoupling it from pricing-rule dollar amounts, then reframing it as *baseline-relative preservation* (how much of the customer's already-committed capability a candidate keeps, not an absolute catalog score) — because both are the kind of scoring bias that quietly turns "costs more" or "has one bonus dimension" into "is a better recommendation," which is exactly what a governed pricing tool should avoid.

**Outcome.** A pure-Python `src/budget_fit` package (`models.py`, `optimizer.py`) with no UI or persistence dependency, deterministic across repeated runs, verified to never mutate the baseline `Quote` it searches from, with a dedicated test suite covering feasibility, ranking, diversity, no-fit behavior, and capability-scoring price-independence.

## What comes after this document

This history stops at whatever the repository's `main` actually contains as of the retrofit that introduced this file — see [`docs/DEVELOPMENT_WORKFLOW.md`](DEVELOPMENT_WORKFLOW.md) for how future milestones should be branched, committed, and reviewed, and [`README.md`](../README.md#how-northstar-evolved) for the short version of this same arc.
