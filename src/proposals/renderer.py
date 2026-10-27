"""The PDF rendering boundary.

A ProposalRenderer turns an already-frozen ProposalSnapshot into PDF
bytes. The application layer (src/application/proposals.py) only calls
`render()` -- it has no idea how the document is drawn, which library
is used, or what the template looks like. See
src/proposals/reportlab_renderer.py for the one concrete implementation
this phase ships.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from .models import ProposalSnapshot


class ProposalRenderer(Protocol):
    def render(
        self,
        snapshot: ProposalSnapshot,
        *,
        proposal_id: str,
        template_version: str,
        generated_at: datetime,
    ) -> bytes:
        """Render one PDF document. Must be deterministic given the
        same inputs, and must never read live pricing rules or call
        back into the pricing engine -- every commercial fact it draws
        comes from `snapshot`."""
        ...
