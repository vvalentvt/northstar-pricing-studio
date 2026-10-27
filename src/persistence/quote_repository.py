"""Presentation-neutral Quote persistence boundary.

This module defines the *interface* only -- exceptions and a Protocol
every QuoteRepository implementation satisfies. The domain packages
(src/quotes, src/pricing_engine, src/budget_fit) never import from
here and never depend on any storage technology; only api/ (and, if
ever needed, other presentation layers) depends on a concrete
repository implementation such as SQLiteQuoteRepository.
"""

from __future__ import annotations

from typing import Protocol

from quotes import Quote, QuoteSummary, QuoteVersion


class QuoteNotFoundError(Exception):
    """No quote exists with the given quote_id."""


class QuoteVersionNotFoundError(Exception):
    """The quote exists, but not the requested version_number."""


class DuplicateQuoteError(Exception):
    """A quote with this quote_id already exists."""


class QuoteVersionConflict(Exception):
    """append_version's optimistic-concurrency guard failed: either the
    quote has advanced past `expected_current_version`, or the supplied
    version's number isn't the next sequential one. Mirrors the
    in-memory stale-workspace protection ScenarioWorkspace already
    enforces (see src/quotes/scenarios.py) -- the same invariant, now
    also enforced at the storage boundary."""


class QuoteRepository(Protocol):
    """Quote-aggregate persistence. Deliberately not a generic CRUD
    repository -- every method exists because this phase (or the
    append-only invariant a future phase depends on) actually needs it.
    """

    def create(self, quote: Quote) -> None:
        """Persist a brand-new Quote (including its initial version).
        Raises DuplicateQuoteError if quote_id already exists."""
        ...

    def get(self, quote_id: str) -> Quote:
        """Load a Quote with its full, sequentially-validated version
        history. Raises QuoteNotFoundError if it doesn't exist."""
        ...

    def exists(self, quote_id: str) -> bool: ...

    def get_version(self, quote_id: str, version_number: int) -> QuoteVersion:
        """Load one historical version without reconstructing the whole
        Quote. Raises QuoteNotFoundError or QuoteVersionNotFoundError."""
        ...

    def append_version(
        self, quote_id: str, version: QuoteVersion, expected_current_version: int
    ) -> None:
        """Append a new QuoteVersion -- never updates or replaces an
        existing row. Only succeeds when the stored current version
        equals `expected_current_version` and `version.version_number`
        is exactly `expected_current_version + 1`; otherwise raises
        QuoteVersionConflict. Raises QuoteNotFoundError if the quote
        doesn't exist."""
        ...

    def list_recent(self, limit: int = 50) -> tuple[QuoteSummary, ...]:
        """The most recently created Quotes (most-recent-first, bounded
        to `limit`) for the Quotes index -- each summary reflects that
        Quote's current version only. Not a generic search/filter/sort
        capability; just this one bounded listing."""
        ...
