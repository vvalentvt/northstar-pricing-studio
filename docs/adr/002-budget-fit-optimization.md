# ADR-002: Implement Budget Fit as constrained configuration search above the pricing engine

- **Status:** Accepted
- **Date:** 2026-09-01
- **Decision owners:** Northstar Pricing Studio portfolio project

## Context

During negotiation, a customer may reveal a fixed budget that is below the current quote. For example, a quoted configuration may cost $62,500 while the customer has only $45,000 available.

A naive response is to calculate the discount required to force the existing configuration to $45,000. That may violate commercial policy or unnecessarily give away value when a different product/service configuration would better fit the customer's constraints.

Northstar should instead answer:

> Given a target budget and customer requirements, what valid product/service configurations can be offered, and which alternatives best preserve customer and commercial value?

The existing pricing engine is intentionally deterministic and forward-oriented:

```text
Configuration + Rules -> PricingResult
```

Real pricing configurations can include discrete tiers, included entitlements, fixed fees, thresholds, conditional adjustments, term multipliers, and discount policies. These rules are not guaranteed to be algebraically invertible.

## Decision

Budget Fit will be implemented as a **constrained configuration-search and ranking service above the canonical pricing engine**.

```text
Target Budget + Negotiation Constraints
                 |
                 v
        BudgetFitOptimizer
                 |
                 +--> Generate candidate configurations
                 |
                 +--> Validate each candidate
                 |
                 +--> Call canonical PricingEngine
                 |
                 +--> Filter invalid / over-budget results
                 |
                 +--> Score + diversify eligible results
                 |
                 v
        Ranked Scenario Recommendations
```

The optimizer will not contain separate pricing formulas and will not modify the pricing engine to "run backward."

### V1 search strategy

V1 will use transparent bounded enumeration / structured candidate generation because the fictional configuration space is small and mostly discrete.

Candidate generation will vary only dimensions the user or product policy marks as flexible. Hard requirements are preserved.

Example:

```text
Target budget: $45,000

Must preserve
- Core product access
- External usage rights
- >= 24 months history

Flexible
- support level
- number of users
- update frequency
- optional modules
```

Each candidate is priced using the same rule version as the negotiation baseline unless the user intentionally reprices under a newer rule version.

### Ranking strategy

Hard constraints are gates, not weighted preferences. An option that violates a must-have requirement cannot outrank a valid option.

Eligible candidates may then be ranked using explicit criteria such as:

- preserved capabilities / customer priorities;
- closeness to baseline configuration;
- revenue utilization of target budget;
- amount of discretionary discount;
- approval friction;
- number/severity of configuration changes.

The scoring function must remain explainable and deterministic.

### Recommendation diversity

Northstar should avoid returning three nearly identical candidates. The recommendation layer may select representative alternatives from the highest-ranked candidates, such as:

- balanced recommendation;
- scope-preserving recommendation;
- budget-utilization recommendation.

The UI should describe these as **recommendations under configured criteria**, not claim a mathematically global optimum unless the implementation can support that claim.

## Consequences

### Positive

- The pricing engine remains the single source of truth.
- Optimization can evolve independently of pricing formulas.
- Recommendations can be tested and explained.
- The product encourages configuration tradeoffs before discretionary discounting.
- Generated alternatives feed naturally into existing scenario comparison and quote versioning.
- The approach demonstrates meaningful algorithmic engineering without unnecessary ML.

### Costs / tradeoffs

- Candidate generation may grow combinatorially as configuration dimensions expand.
- Ranking requires explicit product decisions about "value."
- Some budgets/constraints may have no valid solution.
- A bounded enumeration approach may eventually require pruning or a solver.

## Alternatives considered

### 1. Algebraically reverse the pricing engine

**Rejected.** Not robust across discrete tiers, thresholds, fixed fees, conditionals, and future rule types. It would also tightly couple optimization logic to every pricing formula.

### 2. Apply whatever discount makes the baseline fit the budget

**Rejected as the default behavior.** It collapses negotiation into discounting, may violate policy, and does not explore legitimate product/scope alternatives.

### 3. Introduce PuLP / OR-Tools immediately

**Deferred.** A solver may become appropriate if the configuration space or constraints become materially larger. For v1, explicit enumeration is easier to understand, test, and demonstrate.

### 4. Machine-learning recommendation model

**Rejected for this project phase.** There is no credible fictional training dataset, and ML would reduce explainability while adding little product value.

## Guardrails

Budget Fit must satisfy the following invariants:

1. Every returned configuration is valid.
2. Every returned price is generated by the canonical pricing engine.
3. Every hard customer constraint is satisfied.
4. Standard recommendations do not exceed the target budget.
5. Policy/approval state is preserved and displayed.
6. Ranking is deterministic for identical inputs and rule version.
7. The recommendation explains what changed from the baseline and why it was surfaced.
8. No recommendation automatically becomes the active quote; the user must select it.

## Follow-up decisions

Future ADRs may be warranted if:

- a mathematical solver is introduced;
- scoring becomes configurable pricing policy;
- optimization spans multiple products or bundles;
- optimizer performance requires caching or parallel evaluation.
