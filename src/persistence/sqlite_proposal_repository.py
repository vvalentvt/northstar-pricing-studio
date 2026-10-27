"""SQLite implementation of ProposalRepository.

One row per generated Proposal, storing the full ProposalSnapshot as
JSON text (via its own model_dump_json()/model_validate_json(), so the
domain model remains the final authority on validity) and the exact
rendered PDF as a BLOB -- never regenerated on read. Foreign-keyed to
the specific (quote_id, version_number) the snapshot was frozen from,
matching quote_versions' own composite primary key.

Rows are never updated: there is no UPDATE statement anywhere in this
module, matching the domain's immutability guarantee (see ADR-006).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from proposals import Proposal, ProposalSnapshot

from .proposal_repository import DuplicateProposalError, ProposalNotFoundError

_SCHEMA = """
CREATE TABLE IF NOT EXISTS proposals (
    proposal_id TEXT PRIMARY KEY,
    quote_id TEXT NOT NULL,
    quote_version_number INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    template_version TEXT NOT NULL,
    filename TEXT NOT NULL,
    proposal_snapshot_json TEXT NOT NULL,
    pdf_bytes BLOB NOT NULL,
    FOREIGN KEY (quote_id, quote_version_number)
        REFERENCES quote_versions(quote_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_proposals_quote_id ON proposals(quote_id);
"""


class SQLiteProposalRepository:
    """See ProposalRepository (src/persistence/proposal_repository.py)
    for the interface contract this implements."""

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

    def create(self, proposal: Proposal, pdf_bytes: bytes) -> None:
        with self._transaction() as conn:
            try:
                conn.execute(
                    "INSERT INTO proposals "
                    "(proposal_id, quote_id, quote_version_number, created_at, "
                    " template_version, filename, proposal_snapshot_json, pdf_bytes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        proposal.proposal_id,
                        proposal.quote_id,
                        proposal.quote_version_number,
                        proposal.created_at.isoformat(),
                        proposal.template_version,
                        proposal.filename,
                        proposal.snapshot.model_dump_json(),
                        sqlite3.Binary(pdf_bytes),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                if "FOREIGN KEY" in str(exc).upper():
                    raise
                raise DuplicateProposalError(
                    f"Proposal {proposal.proposal_id} already exists"
                ) from exc

    def get(self, proposal_id: str) -> Proposal:
        conn = self._raw_connect()
        try:
            row = conn.execute(
                "SELECT proposal_id, quote_id, quote_version_number, created_at, "
                "template_version, filename, proposal_snapshot_json "
                "FROM proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            raise ProposalNotFoundError(f"No proposal {proposal_id}")
        return self._row_to_proposal(row)

    def get_pdf(self, proposal_id: str) -> bytes:
        conn = self._raw_connect()
        try:
            row = conn.execute(
                "SELECT pdf_bytes FROM proposals WHERE proposal_id = ?", (proposal_id,)
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            raise ProposalNotFoundError(f"No proposal {proposal_id}")
        return bytes(row[0])

    def list_for_quote(self, quote_id: str) -> tuple[Proposal, ...]:
        conn = self._raw_connect()
        try:
            rows = conn.execute(
                "SELECT proposal_id, quote_id, quote_version_number, created_at, "
                "template_version, filename, proposal_snapshot_json "
                "FROM proposals WHERE quote_id = ? ORDER BY created_at, proposal_id",
                (quote_id,),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._row_to_proposal(row) for row in rows)

    @staticmethod
    def _row_to_proposal(row: tuple) -> Proposal:
        (
            proposal_id,
            quote_id,
            quote_version_number,
            created_at,
            template_version,
            filename,
            snapshot_json,
        ) = row
        return Proposal(
            proposal_id=proposal_id,
            quote_id=quote_id,
            quote_version_number=quote_version_number,
            created_at=created_at,
            template_version=template_version,
            filename=filename,
            snapshot=ProposalSnapshot.model_validate_json(snapshot_json),
        )
