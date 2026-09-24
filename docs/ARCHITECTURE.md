# Northstar Pricing Studio — Solution Architecture

## 1. Purpose

This document defines the target solution architecture for Northstar Pricing Studio. The architecture is deliberately sized for a portfolio application while preserving patterns that matter in real commercial systems: deterministic pricing, clear domain boundaries, quote versioning, explainable optimization, approval governance, and proposal lineage.

The architecture should demonstrate maintainability without simulating enterprise infrastructure the project does not need.

---

## 2. Architectural principles

1. **The pricing engine is the canonical source of price.** UI, optimizer, persistence, and proposal code do not duplicate pricing formulas.
2. **Pricing is deterministic.** Validated configuration + explicit rule version produces a reproducible result.
3. **Saved pricing decisions are versioned.** Negotiation creates new quote versions/scenarios rather than rewriting history.
4. **Optimization sits above pricing.** Budget Fit proposes configurations; it does not contain a second pricing engine.
5. **Proposal generation consumes an approved snapshot.** It does not calculate a fresh price from mutable UI state.
6. **Domain logic is independent of Streamlit.** Streamlit orchestrates user interaction and presentation.
7. **Rules are configuration, not UI code.** Changeable pricing behavior is externalized to YAML where appropriate.
8. **Explainability is a domain concern.** Price adjustments and optimizer rankings should emit structured reasons.
9. **Build complexity only when earned.** Start with in-memory services and bounded enumeration before database/event/solver complexity.

---

## 3. System context

```text
+-----------------------+
| Commercial User       |
| AE / Pricing / Finance|
+-----------+-----------+
            |
            v
+------------------------------+
| Northstar Pricing Studio     |
| Streamlit application        |
+------------------------------+
            |
            +----> Versioned pricing rules (YAML)
            |
            +----> Persistence [later: SQLite/DuckDB]
            |
            +----> Proposal artifact [later: HTML/PDF]
```

Northstar is intentionally modeled as a self-contained internal application. CRM integration, identity, notifications, and external document storage are future integration boundaries rather than MVP dependencies.

---

## 4. Target component architecture

```text
┌──────────────────────────────────────────────────────────────────────┐
│                         Streamlit UI                                 │
│  Deal Setup | Configure | Review | Budget Fit | Compare | Proposal   │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               v
┌──────────────────────────────────────────────────────────────────────┐
│                  Application / Workflow Services                     │
│                                                                      │
│  QuoteService        ScenarioService        ProposalService          │
│       │                    │                      │                   │
│       │                    ├── BudgetFitOptimizer │                   │
│       │                    │         │            │                   │
│       └────────────────────┴─────────┼────────────┘                   │
└──────────────────────────────────────┼───────────────────────────────┘
                                       │
                         candidate/configuration requests
                                       │
                                       v
┌──────────────────────────────────────────────────────────────────────┐
│                         Domain Layer                                 │
│                                                                      │
│  Pydantic Models      Pricing Engine       Policy Evaluation         │
│       │                    │                                          │
│       │                    └──────────────> Price explanations        │
└───────┼──────────────────────────┬───────────────────────────────────┘
        │                          │
        │                          v
        │                ┌────────────────────┐
        │                │ Versioned YAML     │
        │                │ Pricing Rules      │
        │                └────────────────────┘
        │
        v
┌──────────────────────────────┐       ┌───────────────────────────────┐
│ Repository / Persistence     │       │ Proposal Renderer [later]     │
│ Quote + versions + snapshots │       │ Jinja/HTML -> PDF             │
│ SQLite or DuckDB [later]     │       │                               │
└──────────────────────────────┘       └───────────────────────────────┘
```

---

## 5. Domain model

### Quote

The durable container for one commercial opportunity or pricing decision thread.

```text
Quote
- quote_id
- customer / account context
- owner
- created_at
- current_version_id
- status
```

A Quote should not itself contain the only mutable copy of pricing inputs.

### QuoteVersion

An immutable saved commercial state at a point in time.

```text
QuoteVersion
- quote_version_id
- quote_id
- version_number
- created_at
- created_by [later]
- origin
- configuration_snapshot
- pricing_snapshot
- negotiation_context?
- parent_version_id?
- selected_for_proposal: bool
```

Possible `origin` values:
- `manual_configuration`
- `manual_scenario`
- `budget_fit_recommendation`

See [ADR-001](adr/001-quote-versioning.md).

### Configuration

The validated choices submitted to the pricing engine.

```text
Configuration
- tier
- users
- coverage
- historical_depth
- contract_term
- renewal
- services
- requested_discount
```

### PricingResult

The transient structured output returned by the canonical pricing engine.

```text
PricingResult
- base_price
- adjustments[]
- subtotal_before_discount
- discount_amount
- final_price
- approval_state
- explanations[]
- rule_version
```

### PricingSnapshot

The frozen pricing facts attached to a saved `QuoteVersion`.

A snapshot exists so historical decisions remain interpretable even after the active pricing policy changes.

```text
PricingSnapshot
- pricing_snapshot_id
- quote_version_id
- rule_version
- calculated_at
- input/configuration hash [optional]
- base_price
- adjustments
- subtotal
- discount
- final_price
- approval_state
- explanations
```

### NegotiationContext

The customer constraints used to generate or evaluate alternatives.

```text
NegotiationContext
- target_budget
- hard_constraints / must_haves
- flexible_dimensions
- priorities [optional]
- source_quote_version_id
```

### Scenario

A temporary or saved alternative configuration associated with the Quote.

A Scenario becomes durable commercial history when it is saved as a `QuoteVersion`.

```text
Scenario
- scenario_id
- quote_id
- label
- origin
- configuration
- pricing_result
- negotiation_context?
- ranking_explanation?
```

### Approval

A governance record tied to a specific quote version.

```text
Approval
- approval_id
- quote_version_id
- reason
- status
- approver [later]
- comments [later]
- decided_at [later]
```

The first portfolio release can model approval state without implementing external routing.

### Proposal

A customer-facing artifact generated from a specific approved/within-authority pricing snapshot.

```text
Proposal
- proposal_id
- proposal_version
- quote_id
- quote_version_id
- pricing_snapshot_id
- template_version
- generated_at
- artifact_path / bytes [implementation dependent]
```

A proposal must never silently move to a newer quote version after it has been generated.

---

## 6. Standard pricing data flow

```text
User configuration
      |
      v
Pydantic validation
      |
      v
PricingEngine.calculate(configuration, rules)
      |
      +--> base price
      +--> adjustments
      +--> discount evaluation
      +--> approval state
      +--> explanations
      |
      v
PricingResult
      |
      v
Review Pricing UI
      |
      v
Save as QuoteVersion + PricingSnapshot [when persistence exists]
```

The UI renders the result; it does not reproduce the calculation.

---

## 7. Budget Fit optimization data flow

Budget Fit is a **configuration-search service** above the pricing engine.

```text
Current QuoteVersion
        +
Target Budget
        +
Must-have Constraints
        +
Flexible Dimensions
        |
        v
BudgetFitOptimizer
        |
        +--> generate candidate Configuration objects
        |
        +--> validate candidate
        |
        +--> PricingEngine.calculate(candidate, same rule version)
        |
        +--> reject invalid / over-budget candidates
        |
        +--> score remaining candidates
        |
        +--> remove dominated / duplicate recommendations
        |
        v
Ranked Scenario Recommendations
        |
        v
Scenario Comparison
        |
        v
User explicitly selects one
        |
        v
New QuoteVersion
```

### Why the optimizer does not "run the engine backward"

Pricing functions are not always invertible. A real configuration can include discrete tiers, included entitlements, fixed fees, thresholds, conditional adjustments, term multipliers, and policy rules. Attempting to algebraically reverse the final price would tightly couple optimization to implementation details of every pricing rule.

Instead, the optimizer searches **valid configurations** and asks the canonical engine to price them.

See [ADR-002](adr/002-budget-fit-optimization.md).

---

## 8. Budget Fit v1 algorithm

The fictional configuration space is intentionally bounded and mostly discrete. V1 should use transparent candidate enumeration plus pruning/ranking.

Pseudo-flow:

```python
candidates = generate_candidates(
    baseline=current_configuration,
    hard_constraints=must_haves,
    flexible_dimensions=flexible_dimensions,
)

priced_candidates = []
for configuration in candidates:
    validated = validate(configuration)
    result = pricing_engine.calculate(validated, rules)

    if result.final_price <= target_budget:
        priced_candidates.append((validated, result))

recommendations = rank_and_diversify(
    priced_candidates,
    baseline=current_configuration,
    priorities=priorities,
)
```

### Candidate scoring

The score should be explicit and inspectable. A first implementation can combine:

- hard-constraint satisfaction — mandatory gate, not a score;
- product/capability preservation;
- closeness to the baseline configuration;
- customer-priority coverage;
- revenue utilization of available budget;
- avoidance of discretionary discount;
- approval friction.

No hidden ML model is required.

### Recommendation diversity

The top three results should not be near-duplicates. The ranking service may deliberately expose different commercial strategies, for example:

- **Recommended** — balanced value + minimal concession;
- **Preserve Scope** — maximizes must-have/optional capability preservation;
- **Maximize Value** — uses the available budget most fully.

Exact labels can evolve with implementation.

---

## 9. Proposal generation flow

```text
Selected QuoteVersion
      |
      v
Confirm within authority / approved
      |
      v
PricingSnapshot (immutable)
      |
      v
ProposalAssembler
      |
      +--> locked pricing facts
      +--> configuration/scope
      +--> controlled terms
      +--> editable narrative fields
      |
      v
ProposalDocument model
      |
      v
Template Renderer
      |
      v
HTML / PDF artifact
```

The ProposalAssembler may allow editable customer-facing narrative, but approved pricing facts remain locked to the snapshot.

---

## 10. Service responsibilities

### PricingEngine

**Owns**
- price calculation;
- rule application;
- price adjustments;
- discount/policy evaluation;
- pricing explanations.

**Does not own**
- UI state;
- persistence;
- scenario ranking;
- proposal formatting.

### QuoteService

**Owns**
- quote lifecycle orchestration;
- saving versions;
- selecting current/active version;
- retrieving quote history.

### ScenarioService

**Owns**
- manually created scenarios;
- scenario labels/origin;
- comparison-ready views;
- conversion of a selected scenario into a quote version.

### BudgetFitOptimizer

**Owns**
- candidate generation;
- hard-constraint filtering;
- calls to the canonical pricing engine;
- candidate scoring and diversification;
- ranking explanations.

**Does not own** pricing formulas.

### ProposalService / Assembler

**Owns**
- verifying eligible proposal basis;
- transforming a frozen snapshot into proposal content;
- template/version metadata;
- invoking document renderer.

---

## 11. Persistence strategy

**Implemented (Phase 6B, API only — see [ADR-004](adr/004-quote-persistence.md)):** the Quote resource is durable behind the API, via a `QuoteRepository` protocol (`src/persistence/quote_repository.py`) implemented with SQLite (`src/persistence/sqlite_quote_repository.py`, stdlib `sqlite3`, no ORM):

```text
quotes           -- one row per Quote (quote_id, customer_name, owner, status, created_at)
quote_versions   -- one row per QuoteVersion (composite PK: quote_id, version_number; FK to quotes)
                    configuration/pricing/negotiation-context snapshots stored as JSON text
                    via each frozen Pydantic model's own model_dump_json()/model_validate_json()
```

Rows are never updated — `quote_versions` is append-only, matching the domain's own immutable `QuoteVersion` history. This is deliberately **not** a single mutable JSON blob per quote: the two-table shape mirrors the domain's actual one-Quote-to-many-QuoteVersions relationship.

This is scoped to the API path only. Streamlit (`app/`) remains entirely `st.session_state`-backed and has not been migrated; the two Quote stores are independent during the ongoing frontend migration (ADR-003).

**Still deferred:**

```text
scenarios        [optional if transient scenarios need persistence]
approvals
proposals
```

Pricing adjustments/explanations are stored as structured JSON within the `pricing_snapshot` column rather than further-normalized tables — sufficient for portfolio scope, and consistent with treating the domain model (not the schema) as the source of truth for what a valid snapshot looks like.

---

## 12. Rule versioning

Every saved pricing snapshot should identify the pricing-rule version used for calculation.

V1 may continue loading YAML from the repository, but the application should treat a rule version as explicit metadata rather than infer it from current file contents.

Historical quote reproduction should use the saved snapshot and version metadata; a future extension could retain historical YAML rule sets as versioned assets.

---

## 13. Validation and policy boundaries

Three categories should remain distinct:

1. **Configuration validation** — input cannot form a valid product configuration.
2. **Pricing policy state** — configuration is valid but requires approval.
3. **Optimization constraints** — configuration is valid/priced but unsuitable for the current target budget or declared customer requirements.

This prevents Budget Fit from confusing "not recommended" with "invalid" and prevents approval-required pricing from being treated as an application error.

---

## 14. Testing strategy

### Pricing engine tests
- deterministic calculations;
- base price;
- each adjustment family;
- discount boundaries;
- approval thresholds;
- invalid configurations.

### Quote/version tests
- new version preserves previous version;
- version references correct rule version/snapshot;
- proposal basis points to an immutable saved version.

### Budget Fit tests
- never returns an invalid configuration;
- never prices a candidate outside the pricing engine;
- respects target budget;
- respects all hard constraints;
- handles no-solution cases;
- ranking is deterministic for identical inputs;
- recommendations are sufficiently differentiated when alternatives exist.

### Proposal tests
- proposal uses expected quote version/snapshot;
- later quote changes do not mutate prior proposal data;
- locked pricing facts match snapshot.

---

## 15. Security and portfolio boundaries

Northstar is not a production system and should not imply production controls it does not implement.

Before public commits:
- use only fictional data;
- do not copy employer pricing formulas, labels, customer examples, screenshots, or workflow terminology;
- do not include credentials or secrets;
- do not describe fictional approval behavior as an actual employer process.

---

## 16. Future architecture extensions

Potential future work, introduced only when it materially improves the product demonstration:

- real approval workflow and roles;
- CRM integration;
- editable/versioned pricing administration;
- solver-based optimization if configuration search outgrows bounded enumeration;
- pricing analytics and exception analysis;
- multi-product bundles;
- proposal template library;
- authentication/authorization;
- API boundary around pricing services.
