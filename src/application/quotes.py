"""Presentation-neutral quote-creation orchestration.

Pure functions over the existing domain (Quote, PricingSnapshot,
QuoteRequest) -- no Streamlit, no HTTP, no persistence. Both the
Streamlit app (app/app_state.py) and the API (api/) call these so the
quote-commit algorithm is never duplicated between presentation layers;
each still owns its own transport/session concerns (DealContext,
ConfigurationInput, DTOs, ...) and translates into the plain
QuoteRequest / QuoteResult shapes these functions take.
"""

from __future__ import annotations

from uuid import uuid4

from pricing_engine import QuoteRequest, QuoteResult
from quotes import PricingSnapshot, Quote


def generate_quote_id() -> str:
    return f"Q-{uuid4().int % 100000:05d}"


def create_quote(
    customer_name: str,
    owner: str,
    configuration: QuoteRequest,
    result: QuoteResult,
) -> Quote:
    """Build a durable Quote (v1) from an already-calculated configuration.

    Reuses Quote.create and PricingSnapshot.from_pricing_result directly
    -- no pricing or version logic is reimplemented here. Never accepts
    a caller-supplied PricingSnapshot for the initial version: v1 always
    comes from calculate_quote's own QuoteResult, so a client can never
    invent its own committed price.
    """
    pricing_snapshot = PricingSnapshot.from_pricing_result(result)
    return Quote.create(
        quote_id=generate_quote_id(),
        customer_name=customer_name,
        owner=owner,
        configuration=configuration,
        pricing_snapshot=pricing_snapshot,
    )
