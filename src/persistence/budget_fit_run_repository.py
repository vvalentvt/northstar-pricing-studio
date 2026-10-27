"""Persistence boundary for quote-linked Budget Fit run lineage.

Not analytical history -- operational negotiation state (see ADR-005 /
Phase 6E spec sections 12-13). It exists purely so a Recommendation
rendered from a quote-linked POST /api/quotes/{quoteId}/budget-fit call
can later become a Scenario (POST .../alternatives/from-budget-fit)
without recalculating it or trusting a client-supplied price -- the
exact BudgetFitRequest/BudgetFitResult that produced the recommendation
is persisted and reread.

BudgetFitRun is defined here, not in src/budget_fit, because no
existing domain concept represents "a request/result pair persisted
under a run id" -- it is the thing this repository exists to store, not
a pricing or optimization concept. It composes the real
BudgetFitRequest/BudgetFitResult rather than re-deriving their fields.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from budget_fit import BudgetFitRequest, BudgetFitResult
from pydantic import BaseModel, ConfigDict, Field


class BudgetFitRunNotFoundError(Exception):
    """No persisted Budget Fit run exists with the given run_id."""


class BudgetFitRun(BaseModel):
    """One persisted quote-linked Budget Fit search -- the exact
    request/result pair, so a later recommendation lookup never
    recalculates anything."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1)
    quote_id: str = Field(min_length=1)
    base_version_number: int = Field(ge=1)
    request: BudgetFitRequest
    result: BudgetFitResult
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BudgetFitRunRepository(Protocol):
    """Deliberately two methods only -- this is write-once lineage, not
    a queryable history. There is no update, no listing, and no
    standalone-demo persistence (see spec section 12: only quote-linked
    runs are persisted)."""

    def create_run(self, run: BudgetFitRun) -> None:
        """Persist a new Budget Fit run under its run_id."""
        ...

    def get_run(self, run_id: str) -> BudgetFitRun:
        """Load a previously persisted run. Raises
        BudgetFitRunNotFoundError if run_id is unknown."""
        ...
