"""Presentation-neutral Proposal persistence boundary.

This module defines the *interface* only. src/proposals never imports
from here and never depends on any storage technology; only api/
depends on a concrete implementation such as SQLiteProposalRepository.

A Proposal is a durable, immutable artifact (see ADR-006): the
interface deliberately has no update/overwrite method. A new narrative
or a newer QuoteVersion means calling `create` again with a new
Proposal, never mutating an existing row.
"""

from __future__ import annotations

from typing import Protocol

from proposals import Proposal


class ProposalNotFoundError(Exception):
    """No Proposal exists with the given proposal_id."""


class DuplicateProposalError(Exception):
    """A Proposal with this proposal_id already exists."""


class ProposalRepository(Protocol):
    """Proposal-artifact persistence. Deliberately minimal: create,
    read, list, and read the PDF bytes -- no update, no overwrite.
    """

    def create(self, proposal: Proposal, pdf_bytes: bytes) -> None:
        """Persist a brand-new, immutable Proposal and its exact
        rendered PDF bytes. Raises DuplicateProposalError if
        proposal_id already exists."""
        ...

    def get(self, proposal_id: str) -> Proposal:
        """Load Proposal metadata (not the PDF bytes -- see
        get_pdf). Raises ProposalNotFoundError if it doesn't exist."""
        ...

    def get_pdf(self, proposal_id: str) -> bytes:
        """Load the exact persisted PDF bytes -- never regenerated.
        Raises ProposalNotFoundError if proposal_id doesn't exist."""
        ...

    def list_for_quote(self, quote_id: str) -> tuple[Proposal, ...]:
        """All Proposals ever generated for this Quote, across every
        QuoteVersion, ordered deterministically (oldest first)."""
        ...
