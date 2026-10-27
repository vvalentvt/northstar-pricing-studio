# ADR-006: Generate customer-facing Proposal artifacts from a committed QuoteVersion

- **Status:** Accepted
- **Date:** 2026-10-27
- **Decision owners:** Northstar Pricing Studio portfolio project

## Context

Northstar's commercial workflow ends with a committed `QuoteVersion` (ADR-004) and, since Phase 6E, an immutable revision history built from negotiated alternatives. What's still missing is the customer-facing output: a durable, downloadable document representing one specific pricing decision the way a real buyer would see it — not the internal Review Pricing governance surface, and not a live view that could silently change underneath the customer.

## Decision

A **Proposal** is a durable artifact generated from one specific committed `QuoteVersion`, never a live view of current pricing:

```text
QuoteVersion (configuration + pricing, frozen)
    + narrative (small, plain-text, user-edited)
    ↓
ProposalSnapshot (frozen copy of both)
    ↓
rendered PDF (ReportLab, server-side, deterministic)
    ↓
Proposal (immutable metadata row + PDF bytes, SQLite)
```

`src/proposals/models.py` defines `ProposalNarrative` (title, executive summary, optional commercial notes/valid-through — plain text, length-capped, never HTML), `ProposalSnapshot` (the narrative plus a direct copy of the QuoteVersion's `ConfigurationSnapshot`/`PricingSnapshot`), and `Proposal` (the artifact: id, quote id/version, created_at, template_version, filename, snapshot). `src/application/proposals.py` orchestrates generation — load Quote, verify the caller's `expectedVersionNumber` still matches `current_version`, block if `pricing_snapshot.approval_required`, build the snapshot, render, persist. It never calls `calculate_quote()`.

Rendering is a `ProposalRenderer` Protocol (`src/proposals/renderer.py`) with one concrete implementation, `ReportLabProposalRenderer` — pure-Python, no browser process, no OS-level binary, deterministic given the same snapshot. Persistence is `ProposalRepository` (`src/persistence/proposal_repository.py` + SQLite implementation): `create`/`get`/`get_pdf`/`list_for_quote` only — no update, no overwrite.

## Why not regenerate dynamically

A PDF generated on the fly from the *current* Quote/rules would change meaning retroactively: a later pricing-rule change, template redesign, or Quote revision would silently rewrite what a customer was already shown. Freezing a `ProposalSnapshot` at generation time — and never reading current rules or the live Quote object to reinterpret it — is what makes a Proposal a real commercial record instead of a changeable report.

## Why PDF BLOB in SQLite

Portfolio scale, small document volume: storing the exact rendered bytes as a BLOB means a Proposal survives a process restart with zero filesystem-sync risk, and a later template change (`northstar-proposal-v2`) can never alter a `v1` artifact, because nothing ever re-renders it. Object storage (S3 or similar) could replace this repository implementation later without changing the `ProposalRepository` interface or anything above it.

## Approval gate

Generation is blocked server-side whenever the source `PricingSnapshot.approval_required` is true — the frontend disabling its button is a courtesy, not the enforcement. There is no approval-routing workflow in this phase; the only way to unblock generation today is a compliant Quote revision (Phase 6E's existing Alternatives → promotion flow).
