# Northstar Pricing Studio — Product Requirements Document

## 1. Product

**Northstar Pricing Studio**
Fictional company: **Northstar Analytics**

> All company names, products, customers, prices, policies, examples, and workflows in this repository are fictional and intentionally separated from proprietary employer information.

---

## 2. Product vision

Northstar Pricing Studio is an internal commercial workspace that helps teams configure a valid B2B offer, calculate governed pricing, explain the economics, negotiate intelligently when customer constraints emerge, secure approval for exceptions, and generate a customer-facing proposal from the exact pricing decision that was approved.

The product is not intended to be a generic CPQ replacement. Its portfolio purpose is to demonstrate how **product strategy, pricing policy, workflow design, and maintainable Python architecture** can work together in a focused commercial application.

---

## 3. Problem statement

Northstar's fictional commercial team relies on spreadsheets, manually maintained pricing guidance, approval messages, and proposal templates. The operating model creates several problems:

1. Standard quotes require repeated data entry and manual calculation.
2. Pricing decisions are difficult to reproduce because rules and judgment are scattered.
3. Sellers do not always know which decisions fall inside self-service authority.
4. Negotiations frequently become a question of "how much discount is required?" rather than "what valid offer best fits the customer's constraints?"
5. Scenario comparison is cumbersome because changing the spreadsheet often destroys the previous configuration.
6. Proposal documents can become detached from the exact quote version and pricing rules that were approved.

---

## 4. Product goals

### Primary goals

- Make standard pricing configuration self-service and governed.
- Make every material price adjustment explainable.
- Preserve pricing decisions as versioned, reproducible commercial records.
- Support negotiation through explicit scenarios rather than destructive edits.
- Help a seller fit an offer to a customer budget while preserving required capabilities and policy constraints.
- Separate configuration changes from discretionary commercial concessions.
- Ensure proposals are derived from an approved pricing snapshot rather than recalculated independently.

### Non-goals for the first portfolio releases

- Full CRM/CPQ replacement
- Real user authentication or enterprise identity management
- Production approval routing or notification infrastructure
- Machine-learning price recommendations
- Autonomous negotiation
- Free-form pricing-rule editing in the UI
- Production-grade document management
- Complex tax, currency, billing, or revenue-recognition logic

---

## 5. Primary users and jobs to be done

### Account Executive — primary workflow owner

**JTBD: standard pricing**
When I am preparing a commercial offer, I want to configure a valid package and immediately understand its price and approval implications so I can move standard deals forward without waiting for a pricing expert.

**JTBD: negotiation**
When a customer tells me their available budget is below the current quote, I want to identify valid alternatives that preserve their most important requirements so I can negotiate scope intelligently instead of defaulting immediately to discounting.

### Pricing / Commercial Strategy — policy owner

**JTBD**
When pricing policy evolves, I want commercial behavior to be configurable, explainable, and traceable so the business can change packaging and monetization without introducing hidden spreadsheet logic.

### Finance / Commercial Approver — governance user

**JTBD**
When a quote exceeds self-service authority, I want to see the commercial context, price bridge, scenario history, and requested exception so I can make an informed approval decision without reverse-engineering the calculation.

---

## 6. Product principles

1. **Configuration over hard-coding.** Changeable pricing policy belongs in versioned configuration where practical.
2. **Explainability over cleverness.** A recommendation that cannot be explained is not a good commercial recommendation.
3. **Configuration before concession.** When a customer has a budget constraint, first explore valid scope/package alternatives; discounting is a distinct commercial lever.
4. **Governed self-service over unrestricted flexibility.** Standard paths should be fast; policy exceptions should be visible and deliberate.
5. **Preserve decision history.** Negotiation should create versions/scenarios rather than overwrite the only record of the original offer.
6. **One pricing source of truth.** Standard quotes and optimizer-generated candidates must use the same pricing engine.
7. **Proposal lineage matters.** Customer-facing output must reference the specific approved pricing snapshot that produced it.
8. **Useful MVP over simulated enterprise complexity.** Do not imply persistence, approvals, or document generation are production-ready before they exist.

---

## 7. Core user journey

### Standard path

1. Create a quote and enter customer/deal context.
2. Configure package, scope, term, services, and discount request.
3. Calculate the quote using the active pricing-rule version.
4. Review final price, price bridge, policy status, and explanations.
5. Save the configuration as a quote version.
6. If required, request approval for the selected quote version.
7. Once pricing is approved or within authority, select the proposal basis.
8. Generate a proposal from the approved pricing snapshot.

### Negotiation / budget-constrained path

1. Begin from an existing priced quote.
2. Record the customer's target budget.
3. Identify **must-have** requirements that cannot be removed.
4. Identify **flexible** attributes that Northstar may vary.
5. Choose **Optimize to Budget**.
6. Northstar generates valid candidate configurations.
7. Every candidate is priced by the canonical pricing engine.
8. Northstar removes candidates that violate hard constraints or exceed the target budget.
9. Remaining candidates are ranked and explained.
10. The user compares recommended candidates with the current quote and/or manually created scenarios.
11. The user selects a scenario and saves it as a new quote version.
12. The selected version proceeds through normal approval and proposal rules.

---

## 8. Functional requirements

### FR-1 — Deal setup

The product shall capture a minimal deal context before exposing detailed pricing controls.

**Minimum data**
- Customer name
- Deal type: new business or renewal
- Optional opportunity/reference name

### FR-2 — Configurable pricing

The product shall accept a validated configuration and calculate pricing using externalized pricing rules.

**Example configuration dimensions**
- Subscription tier
- Users
- Geographic coverage
- Historical depth
- Contract term
- Renewal status
- Premium support
- Implementation services
- Requested discount

### FR-3 — Explainable pricing

Every non-zero material pricing adjustment shall have a plain-language explanation. Review screens shall show a price bridge from base price through final price.

### FR-4 — Pricing authority

The product shall distinguish:
- valid and within self-service authority;
- valid but requiring approval;
- invalid / blocked by policy.

Approval-required pricing is a valid commercial state, not a calculation failure.

### FR-5 — Quote versioning

A saved commercial decision shall be represented by a `QuoteVersion` rather than destructively replacing prior pricing history.

Each quote version shall retain enough information to reproduce and explain the decision, including:
- configuration snapshot;
- pricing result snapshot;
- pricing-rule version;
- creation timestamp;
- origin (manual configuration, manual scenario, or optimizer recommendation);
- negotiation context when applicable.

See [`adr/001-quote-versioning.md`](adr/001-quote-versioning.md).

### FR-6 — Scenario modeling

Users shall be able to create and compare alternative configurations within the same quote.

Scenario comparison should prioritize differences in:
- configuration;
- final price;
- budget variance;
- discount;
- approval state;
- must-have coverage;
- source/origin of the scenario.

### FR-7 — Budget Fit Optimization

The product shall support a target-budget workflow that returns valid, priced scenario recommendations.

**Inputs**
- Target budget
- Required/must-have attributes
- Flexible attributes
- Optional ranking priorities

**Hard constraints**
- Recommended price must not exceed the target budget unless the UI explicitly labels an alternative as over budget.
- Every declared must-have requirement must be satisfied.
- Every recommendation must be a valid configuration.
- Every recommendation must be priced by the canonical pricing engine.
- Pricing-policy constraints remain enforceable.

**Output expectations**
- Up to three meaningfully differentiated recommendations for the first portfolio implementation.
- Recommended final price.
- Difference from current quote.
- Difference from target budget.
- Configuration changes required to reach the recommendation.
- Must-have coverage.
- Discount required, if any.
- Approval state.
- Plain-language reason the option was ranked.

**Optimization principle**

Budget Fit should maximize useful commercial/customer value under constraints, not simply return the most expensive configuration below the budget.

For v1, exhaustive/structured candidate enumeration is preferred over an optimization library because the fictional configuration space is small and discrete. See [`adr/002-budget-fit-optimization.md`](adr/002-budget-fit-optimization.md).

### FR-8 — Separate scope changes from discounting

Northstar shall show configuration changes and commercial concessions as different categories of change.

The user should be able to understand whether a lower price was achieved by:
- reducing/changing product scope;
- changing commercial terms;
- applying a discount or override;
- some combination of the above.

### FR-9 — Approval state

A selected quote version that exceeds configured authority shall be prevented from progressing directly to proposal until the approval condition is satisfied.

A production approval engine is deferred; initial releases may model the state without external routing.

### FR-10 — Proposal lineage

A proposal shall be generated from a specific approved or within-authority `PricingSnapshot` associated with a specific `QuoteVersion`.

Proposal generation shall not silently recalculate pricing from mutable UI state.

A proposal record should retain:
- proposal ID/version;
- quote ID;
- quote-version ID;
- pricing-snapshot ID;
- template version;
- generated timestamp.

---

## 9. Domain concepts

| Object | Purpose |
| --- | --- |
| Account | Customer/commercial context |
| Quote | Durable container for one commercial opportunity/decision thread |
| QuoteVersion | Immutable saved state of a quote at a point in time |
| Configuration | Product/service and commercial choices being priced |
| PricingResult | Result returned by the pricing engine |
| PricingSnapshot | Frozen pricing facts attached to a saved quote version |
| NegotiationContext | Target budget, hard requirements, flexible attributes, priorities |
| Scenario | Alternative configuration being evaluated within a quote |
| Approval | Governance decision associated with a specific quote version |
| Proposal | Customer-facing artifact derived from a specific approved snapshot |

---

## 10. UX requirements

- The workflow should remain **Deal Setup → Configure → Review Pricing → Proposal**.
- Negotiation is available from Review Pricing rather than becoming a mandatory wizard step.
- The Review screen should expose the current price, customer budget when known, and budget gap.
- Budget Fit must ask the user what is required vs flexible before generating recommendations.
- System-generated options must be visually distinguishable from manually created scenarios without implying they are automatically correct.
- A user must explicitly select a scenario before it becomes the proposal basis.
- The product should show why an optimizer recommendation differs from the current quote.

---

## 11. Non-functional requirements

### Reproducibility
Given the same configuration and rule version, the pricing engine should return the same pricing result.

### Auditability
Saved quote versions should make it possible to determine what was configured, which rule version was used, what price was produced, what negotiation context existed, and what downstream artifact referenced the decision.

### Testability
Pricing and optimization logic should be testable without Streamlit.

### Explainability
Ranking and pricing outputs should be explainable through deterministic rules and human-readable reason codes.

### Performance
The v1 optimizer should complete quickly enough for interactive use with the bounded fictional configuration space. If candidate growth becomes material, introduce pruning or a solver deliberately rather than prematurely.

### Privacy / portfolio safety
No proprietary employer data, pricing logic, product names, customer data, or confidential workflows should be introduced.

---

## 12. MVP acceptance criteria

A reviewer should be able to:

- configure and calculate a valid quote;
- understand how the engine arrived at the final price;
- see whether approval is required and why;
- save/represent an alternative scenario without losing the baseline;
- enter a fictional target budget and define must-have vs flexible requirements;
- receive multiple valid Budget Fit recommendations priced by the canonical engine;
- compare optimizer-generated and manually created scenarios;
- select a quote version as the commercial basis for the next step;
- understand that proposal output is tied to a versioned pricing decision.

---

## 13. Success metrics

| Metric | Target |
| --- | ---: |
| Median standard quote configuration time | < 10 minutes |
| Standard configurations supported without specialist intervention | >= 80% |
| Saved quote versions reproducible from configuration + rule version | 100% |
| Non-zero price adjustments with explanations | 100% |
| Budget Fit recommendations satisfying declared hard constraints | 100% |
| Budget Fit recommendations priced by canonical pricing engine | 100% |
| Proposal artifacts traceable to a quote version and pricing snapshot | 100% |
| Invalid configuration blocked before proposal | 100% |
| Automated test coverage of core pricing rules | >= 90% |

---

## 14. Open product questions

These are intentional future decisions, not blockers for the documentation phase:

- How should customer-value priorities be scored when multiple under-budget configurations are valid?
- Should the user be allowed to authorize specific flexible dimensions or should Northstar derive flexibility from defaults?
- Should Budget Fit ever propose a discount automatically, or only show a discount-enabled option when explicitly allowed?
- When persistence is introduced, which quote changes create a new `QuoteVersion` automatically vs only on explicit save?
- What approval metadata is sufficient for the portfolio version before implementing real routing?
- Which parts of proposal narrative are editable versus controlled template content?
