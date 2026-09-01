# Documentation Change Summary — Negotiation & Budget Fit

## Why this change

Northstar's original product design covered configuration, explainable pricing, approvals, scenario comparison, and proposal readiness. The negotiation discussion surfaced two domain requirements that should be designed before more UI code is written:

1. pricing configurations must be versioned so negotiation does not overwrite history; and
2. a customer budget should be treated as a constraint for finding valid configurations, not merely as a target used to calculate a larger discount.

## Product decision

Northstar now treats **Budget Fit Optimization** as a flagship negotiation capability available from Review Pricing.

```text
Review Pricing
    ↕
Negotiate / Explore
├── Manual Scenario
└── Optimize to Budget
          ↓
   Compare Scenarios
          ↓
   Select Quote Version
          ↓
 Approval / Proposal
```

## Architecture decisions

- `Quote` is a durable container; `QuoteVersion` is an immutable saved commercial state.
- A `PricingSnapshot` freezes the pricing facts associated with a saved quote version.
- `NegotiationContext` records target budget, must-haves, and flexible dimensions.
- Budget Fit generates valid candidate configurations and prices each through the canonical pricing engine.
- Budget Fit does not run pricing formulas backward and does not contain a second pricing engine.
- A proposal references a specific eligible quote version and pricing snapshot.

## Files changed

- `README.md`
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/PRODUCT_DESIGN.md`
- `docs/WIREFRAMES.md`
- `docs/DESIGN_SYSTEM.md`
- `docs/ROADMAP.md`
- `docs/wireframes/06-budget-fit.svg`

## Files added

- `docs/adr/README.md`
- `docs/adr/001-quote-versioning.md`
- `docs/adr/002-budget-fit-optimization.md`

## Recommended commit

```text
docs: add negotiation and budget-fit architecture
```
