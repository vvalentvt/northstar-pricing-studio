"""SQLite implementation of BudgetFitRunRepository.

One row per persisted quote-linked Budget Fit search. request/result
are stored as JSON text via BudgetFitRequest/BudgetFitResult's own
model_dump_json(), and rehydrated via model_validate_json() -- so a
later recommendation lookup gets back the exact ConfigurationSnapshot/
PricingSnapshot the optimizer produced, never a recalculated one.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from budget_fit import BudgetFitRequest, BudgetFitResult

from .budget_fit_run_repository import BudgetFitRun, BudgetFitRunNotFoundError

_SCHEMA = """
CREATE TABLE IF NOT EXISTS budget_fit_runs (
    run_id TEXT PRIMARY KEY,
    quote_id TEXT NOT NULL REFERENCES quotes(quote_id),
    base_version_number INTEGER NOT NULL,
    request_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class SQLiteBudgetFitRunRepository:
    """See BudgetFitRunRepository (src/persistence/budget_fit_run_repository.py)
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

    def create_run(self, run: BudgetFitRun) -> None:
        with self._transaction() as conn:
            conn.execute(
                "INSERT INTO budget_fit_runs "
                "(run_id, quote_id, base_version_number, request_json, result_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    run.run_id,
                    run.quote_id,
                    run.base_version_number,
                    run.request.model_dump_json(),
                    run.result.model_dump_json(),
                    run.created_at.isoformat(),
                ),
            )

    def get_run(self, run_id: str) -> BudgetFitRun:
        conn = self._raw_connect()
        try:
            row = conn.execute(
                "SELECT run_id, quote_id, base_version_number, request_json, result_json, "
                "created_at FROM budget_fit_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            raise BudgetFitRunNotFoundError(f"No Budget Fit run {run_id}")

        run_id_, quote_id, base_version_number, request_json, result_json, created_at = row
        return BudgetFitRun(
            run_id=run_id_,
            quote_id=quote_id,
            base_version_number=base_version_number,
            request=BudgetFitRequest.model_validate_json(request_json),
            result=BudgetFitResult.model_validate_json(result_json),
            created_at=created_at,
        )
