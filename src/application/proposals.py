"""Presentation-neutral proposal generation orchestration.

Unlike application/quotes.py and application/scenarios.py (which are
pure functions over in-memory domain objects only), proposal
generation genuinely spans two stores and a renderer in one
transaction-shaped unit of work -- load from QuoteRepository, render,
write to ProposalRepository -- so this module takes its collaborators
as parameters rather than leaving that wiring to the API router. The
repository/renderer types here are Protocols (interfaces), not
concrete implementations: this module still has no idea it's SQLite or
ReportLab underneath.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import uuid4

from persistence import ProposalRepository, QuoteRepository
from proposals import Proposal, ProposalNarrative, ProposalRenderer, ProposalSnapshot

#: Bumped only when the visual template itself changes. Existing
#: Proposal rows and PDF bytes are never reinterpreted under a new
#: template version -- see ADR-006.
TEMPLATE_VERSION = "northstar-proposal-v1"


class ProposalError(ValueError):
    """Raised when a Proposal cannot be generated -- a stale expected
    version, or pricing that requires approval."""


def generate_proposal_id() -> str:
    return f"P-{uuid4().int % 100000:05d}"


def build_proposal_filename(customer_name: str, quote_id: str, version_number: int) -> str:
    """A filesystem/header-safe filename -- never the raw, unsanitized
    customer name (see Phase 6F spec section 53/54)."""
    safe_customer = re.sub(r"[^A-Za-z0-9]+", "_", customer_name).strip("_") or "Customer"
    return f"Northstar_Proposal_{safe_customer}_{quote_id}_v{version_number}.pdf"


def generate_proposal(
    quote_id: str,
    expected_version_number: int,
    narrative: ProposalNarrative,
    *,
    quote_repository: QuoteRepository,
    proposal_repository: ProposalRepository,
    renderer: ProposalRenderer,
) -> Proposal:
    """The one place a Proposal is generated.

    1. Load the Quote (QuoteNotFoundError propagates -- the caller
       translates that to 404).
    2. Verify expected_version_number still matches the current
       committed version (ProposalError otherwise -- stale, a 409 at
       the API layer: the Quote advanced after the caller loaded it).
    3. Block pricing that requires approval (ProposalError -- also a
       409: there is no approval-routing workflow in this phase, so a
       compliant Quote revision is the only way to unblock this).
    4. Build the ProposalSnapshot directly from the committed
       QuoteVersion's own ConfigurationSnapshot/PricingSnapshot --
       never calling calculate_quote() and never reading current
       pricing rules.
    5. Render the PDF and persist the immutable artifact.

    Never mutates the Quote, its ScenarioWorkspace, or any
    QuoteVersion -- this function calls quote_repository.get() and
    nothing else on that repository.
    """
    quote = quote_repository.get(quote_id)
    current = quote.current_version

    if current.version_number != expected_version_number:
        raise ProposalError(
            f"Quote {quote_id} is now at pricing version v{current.version_number}, but this "
            f"proposal was prepared for v{expected_version_number}. Refresh and try again."
        )
    if current.pricing_snapshot.approval_required:
        raise ProposalError(
            "Pricing approval is required before a customer-facing proposal can be generated."
        )

    snapshot = ProposalSnapshot(
        quote_id=quote_id,
        quote_version_number=current.version_number,
        customer_name=quote.customer_name,
        owner=quote.owner,
        narrative=narrative,
        configuration_snapshot=current.configuration_snapshot,
        pricing_snapshot=current.pricing_snapshot,
    )

    proposal_id = generate_proposal_id()
    filename = build_proposal_filename(quote.customer_name, quote_id, current.version_number)
    generated_at = datetime.now(timezone.utc)

    pdf_bytes = renderer.render(
        snapshot,
        proposal_id=proposal_id,
        template_version=TEMPLATE_VERSION,
        generated_at=generated_at,
    )

    proposal = Proposal(
        proposal_id=proposal_id,
        quote_id=quote_id,
        quote_version_number=current.version_number,
        created_at=generated_at,
        template_version=TEMPLATE_VERSION,
        filename=filename,
        snapshot=snapshot,
    )
    proposal_repository.create(proposal, pdf_bytes)
    return proposal
