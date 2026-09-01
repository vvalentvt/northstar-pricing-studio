# ADR-001: Version quotes as immutable commercial decisions

- **Status:** Accepted
- **Date:** 2026-09-01
- **Decision owners:** Northstar Pricing Studio portfolio project

## Context

A pricing configuration can change after the initial quote. During negotiation, a customer may request a different product mix, term, service level, or price point. Northstar also plans to support system-generated Budget Fit recommendations.

If the application stores only one mutable configuration per quote, later edits would erase the context required to answer basic commercial questions:

- What was originally offered?
- Which configuration was approved?
- Which pricing rules produced that price?
- What changed during negotiation?
- Which configuration was used to generate a proposal?

A mutable quote record would also make proposal lineage fragile: a proposal created from one commercial decision could appear to reference newer pricing after the quote is edited.

## Decision

Northstar will model a `Quote` as a durable container and a `QuoteVersion` as an **immutable saved commercial state**.

```text
Quote Q-00124
|
+-- v1  Original configuration        $62,500
|
+-- v2  Manual negotiation scenario   $51,000
|
+-- v3  Budget Fit recommendation     $44,750  <-- selected/approved
|       |
|       +-- PricingSnapshot
|       +-- NegotiationContext
|
+-- Proposal P-001 references v3 only
```

Each saved `QuoteVersion` will contain or reference:

- a complete configuration snapshot;
- a frozen pricing snapshot;
- the pricing-rule version;
- creation timestamp;
- version origin;
- negotiation context when relevant;
- parent/source version when useful for comparison.

A later version does not mutate an earlier version.

### Quote vs Scenario

A `Scenario` is an alternative configuration being evaluated within a Quote. A scenario may remain transient while the user explores alternatives. When the user explicitly saves/selects an alternative as a commercial state, Northstar creates a new `QuoteVersion`.

This keeps exploratory UI state from generating unnecessary permanent versions while preserving meaningful commercial decisions.

### Proposal relationship

A proposal references a specific quote version and pricing snapshot:

```text
Proposal
- proposal_id
- quote_id
- quote_version_id
- pricing_snapshot_id
- template_version
- generated_at
```

Proposal generation must not silently recalculate from the current mutable UI configuration.

## Consequences

### Positive

- Historical pricing decisions remain reproducible.
- Negotiation history is explicit rather than destructive.
- Budget Fit recommendations fit naturally into the same quote model.
- Approval records can target the exact pricing state being reviewed.
- Proposal lineage is defensible.
- A reviewer can understand the commercial history without reconstructing application state.

### Costs / tradeoffs

- More domain objects and persistence relationships are required.
- The UI must distinguish current draft state, scenarios, and saved versions.
- Rules are needed for when to create a version to avoid excessive version noise.
- Historical rule version/snapshot handling becomes an explicit responsibility.

## Alternatives considered

### 1. One mutable quote record

**Rejected.** Simple initially, but edits would destroy negotiation history and weaken auditability/proposal lineage.

### 2. Duplicate each quote as a new quote

**Rejected.** Preserves states but breaks the mental model that all alternatives belong to one customer negotiation and complicates comparison/history.

### 3. Event sourcing

**Deferred.** A full event log could recreate every state, but it adds infrastructure and cognitive complexity beyond what this portfolio application needs. Immutable versions provide the key auditability benefit with a much smaller implementation surface.

## Implementation notes

The first implementation may keep quote versions in memory. Persistence can follow after the domain model and UI workflow are validated.

Version IDs should be stable and distinct from human-readable version numbers. For example:

```text
quote_id: Q-00124
quote_version_id: qv_01J...
version_number: 3
```

The exact identifier scheme is an implementation detail and may change.
