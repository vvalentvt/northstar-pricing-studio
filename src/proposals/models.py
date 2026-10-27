"""The Proposal domain: a durable, customer-facing artifact generated
from one specific committed QuoteVersion.

A Proposal is not a live view of current pricing. It freezes the
commercial facts (ConfigurationSnapshot, PricingSnapshot) from the
QuoteVersion it was generated from, plus a small amount of editable
narrative -- then stays that way even if the Quote later advances, the
pricing rules change, or the proposal template changes. See
docs/adr/006-proposal-artifacts.md.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from quotes import ConfigurationSnapshot, PricingSnapshot


class ProposalNarrative(BaseModel):
    """The only editable part of a Proposal -- plain text, never HTML,
    never a replacement for the frozen commercial facts below."""

    model_config = ConfigDict(frozen=True)

    proposal_title: str = Field(min_length=1, max_length=200)
    executive_summary: str = Field(min_length=1, max_length=4000)
    commercial_notes: str | None = Field(default=None, max_length=4000)
    valid_through: date | None = None


class ProposalSnapshot(BaseModel):
    """Everything required to explain what was actually generated,
    frozen at generation time. configuration_snapshot and
    pricing_snapshot are copied directly from the committed
    QuoteVersion -- never recalculated, never reloaded from current
    pricing rules.
    """

    model_config = ConfigDict(frozen=True)

    quote_id: str = Field(min_length=1)
    quote_version_number: int = Field(ge=1)
    customer_name: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    narrative: ProposalNarrative
    configuration_snapshot: ConfigurationSnapshot
    pricing_snapshot: PricingSnapshot


class Proposal(BaseModel):
    """A durable, immutable artifact. Once created, a Proposal is never
    updated -- a new narrative or a newer QuoteVersion means generating
    a new Proposal, never mutating this one (see
    src/persistence/proposal_repository.py: there is no update method).
    """

    model_config = ConfigDict(frozen=True)

    proposal_id: str = Field(min_length=1)
    quote_id: str = Field(min_length=1)
    quote_version_number: int = Field(ge=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    template_version: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    snapshot: ProposalSnapshot
