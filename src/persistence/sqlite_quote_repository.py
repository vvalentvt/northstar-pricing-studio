"""SQLite implementation of QuoteRepository.

Storage model mirrors Northstar's own domain shape rather than one
mutable JSON blob per Quote:

    quotes            (1 row per Quote -- quote-level metadata only)
    quote_versions    (append-only, 1 row per QuoteVersion)

ConfigurationSnapshot / PricingSnapshot / NegotiationContext are stored
as JSON text via each model's own model_dump_json(), and rehydrated via
model_validate_json() -- the domain models are the final authority on
whether persisted state is valid; this repository never hand-rolls
field-by-field reconstruction or reinterprets a historical snapshot
against current pricing rules.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from quotes import (
    ConfigurationSnapshot,
    NegotiationContext,
    PricingSnapshot,
    Quote,
    QuoteSummary,
    QuoteVersion,
    QuoteVersionSource,
)

from .quote_repository import (
    DuplicateQuoteError,
    QuoteNotFoundError,
    QuoteVersionConflict,
    QuoteVersionNotFoundError,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS quotes (
    quote_id TEXT PRIMARY KEY,
    customer_name TEXT NOT NULL,
    owner TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quote_versions (
    quote_id TEXT NOT NULL REFERENCES quotes(quote_id),
    version_number INTEGER NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    configuration_snapshot_json TEXT NOT NULL,
    pricing_snapshot_json TEXT NOT NULL,
    negotiation_context_json TEXT,
    PRIMARY KEY (quote_id, version_number)
);
"""


class SQLiteQuoteRepository:
    """See QuoteRepository (src/persistence/quote_repository.py) for the
    interface contract this implements."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _raw_connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        conn = self._raw_connect()
        try:
            conn.executescript(_SCHEMA)
            conn.execute("PRAGMA journal_mode = WAL")
            conn.commit()
        finally:
            conn.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        """One atomic unit of work: BEGIN IMMEDIATE acquires the write
        lock before any statement runs (not SQLite's default deferred
        mode), so a read-then-check-then-write sequence -- the
        optimistic concurrency guard in append_version -- can never
        interleave with another writer. Commits on success, rolls back
        and re-raises on any exception, always closes the connection.
        """
        conn = self._raw_connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create(self, quote: Quote) -> None:
        with self._transaction() as conn:
            try:
                conn.execute(
                    "INSERT INTO quotes (quote_id, customer_name, owner, status, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        quote.quote_id,
                        quote.customer_name,
                        quote.owner,
                        quote.status,
                        quote.created_at.isoformat(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise DuplicateQuoteError(f"Quote {quote.quote_id} already exists") from exc
            for version in quote.versions:
                self._insert_version(conn, quote.quote_id, version)

    def exists(self, quote_id: str) -> bool:
        conn = self._raw_connect()
        try:
            row = conn.execute(
                "SELECT 1 FROM quotes WHERE quote_id = ?", (quote_id,)
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def get(self, quote_id: str) -> Quote:
        conn = self._raw_connect()
        try:
            quote_row = conn.execute(
                "SELECT quote_id, customer_name, owner, status, created_at "
                "FROM quotes WHERE quote_id = ?",
                (quote_id,),
            ).fetchone()
            if quote_row is None:
                raise QuoteNotFoundError(f"Quote {quote_id} not found")
            version_rows = conn.execute(
                "SELECT version_number, source, created_at, configuration_snapshot_json, "
                "pricing_snapshot_json, negotiation_context_json "
                "FROM quote_versions WHERE quote_id = ? ORDER BY version_number",
                (quote_id,),
            ).fetchall()
        finally:
            conn.close()

        versions = tuple(self._row_to_version(row) for row in version_rows)
        # Quote's own validator enforces sequential, gap-free numbering --
        # persistence doesn't re-implement that check, just supplies the
        # ordered rows and lets the domain model have the final say.
        return Quote(
            quote_id=quote_row[0],
            customer_name=quote_row[1],
            owner=quote_row[2],
            status=quote_row[3],
            created_at=quote_row[4],
            versions=versions,
        )

    def get_version(self, quote_id: str, version_number: int) -> QuoteVersion:
        conn = self._raw_connect()
        try:
            row = conn.execute(
                "SELECT version_number, source, created_at, configuration_snapshot_json, "
                "pricing_snapshot_json, negotiation_context_json "
                "FROM quote_versions WHERE quote_id = ? AND version_number = ?",
                (quote_id, version_number),
            ).fetchone()
            if row is not None:
                return self._row_to_version(row)
            quote_exists = (
                conn.execute(
                    "SELECT 1 FROM quotes WHERE quote_id = ?", (quote_id,)
                ).fetchone()
                is not None
            )
        finally:
            conn.close()

        if not quote_exists:
            raise QuoteNotFoundError(f"Quote {quote_id} not found")
        raise QuoteVersionNotFoundError(f"Quote {quote_id} has no version {version_number}")

    def append_version(
        self, quote_id: str, version: QuoteVersion, expected_current_version: int
    ) -> None:
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT MAX(version_number) FROM quote_versions WHERE quote_id = ?",
                (quote_id,),
            ).fetchone()
            current = row[0]
            if current is None:
                raise QuoteNotFoundError(f"Quote {quote_id} not found")
            if current != expected_current_version:
                raise QuoteVersionConflict(
                    f"Quote {quote_id} is at version {current}, "
                    f"but the append expected version {expected_current_version}"
                )
            if version.version_number != expected_current_version + 1:
                raise QuoteVersionConflict(
                    f"New version must be {expected_current_version + 1}, "
                    f"got {version.version_number}"
                )
            self._insert_version(conn, quote_id, version)

    def list_recent(self, limit: int = 50) -> tuple[QuoteSummary, ...]:
        # One join against each quote's own latest version -- reads only
        # the pricing_snapshot_json column (never the full snapshot
        # payload a GET /api/quotes/{id} loads) and pulls just the two
        # fields a listing row needs out of it.
        conn = self._raw_connect()
        try:
            rows = conn.execute(
                "SELECT q.quote_id, q.customer_name, q.owner, q.status, q.created_at, "
                "       v.version_number, v.pricing_snapshot_json "
                "FROM quotes q "
                "JOIN quote_versions v ON v.quote_id = q.quote_id "
                "WHERE v.version_number = ("
                "    SELECT MAX(version_number) FROM quote_versions WHERE quote_id = q.quote_id"
                ") "
                "ORDER BY q.created_at DESC, q.quote_id DESC "
                "LIMIT ?",
                (limit,),
            ).fetchall()
        finally:
            conn.close()

        summaries = []
        for quote_id, customer_name, owner, status, created_at, version_number, pricing_json in rows:
            pricing = json.loads(pricing_json)
            summaries.append(
                QuoteSummary(
                    quote_id=quote_id,
                    customer_name=customer_name,
                    owner=owner,
                    status=status,
                    created_at=created_at,
                    current_version_number=version_number,
                    final_price=pricing["final_price"],
                    approval_required=pricing["approval_required"],
                )
            )
        return tuple(summaries)

    @staticmethod
    def _insert_version(conn: sqlite3.Connection, quote_id: str, version: QuoteVersion) -> None:
        conn.execute(
            "INSERT INTO quote_versions "
            "(quote_id, version_number, source, created_at, "
            " configuration_snapshot_json, pricing_snapshot_json, negotiation_context_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                quote_id,
                version.version_number,
                version.source.value,
                version.created_at.isoformat(),
                version.configuration_snapshot.model_dump_json(),
                version.pricing_snapshot.model_dump_json(),
                version.negotiation_context.model_dump_json()
                if version.negotiation_context is not None
                else None,
            ),
        )

    @staticmethod
    def _row_to_version(row: tuple) -> QuoteVersion:
        version_number, source, created_at, config_json, pricing_json, negotiation_json = row
        return QuoteVersion(
            version_number=version_number,
            source=QuoteVersionSource(source),
            created_at=created_at,
            configuration_snapshot=ConfigurationSnapshot.model_validate_json(config_json),
            pricing_snapshot=PricingSnapshot.model_validate_json(pricing_json),
            negotiation_context=(
                NegotiationContext.model_validate_json(negotiation_json)
                if negotiation_json is not None
                else None
            ),
        )
