"""SQLite implementation of ScenarioRepository.

Storage mirrors the domain's own shape -- one `scenario_workspaces` row
per active workspace, one `scenarios` row per Scenario it contains --
the same two-table-aggregate pattern SQLiteQuoteRepository uses for
Quote/QuoteVersion. Snapshots are stored as JSON text via each frozen
Pydantic model's own model_dump_json()/model_validate_json(), so the
domain models remain the final authority on validity, exactly as in
SQLiteQuoteRepository.

Unlike quote_versions, `scenarios` rows are genuinely deleted (on
clear_workspace) and `scenario_workspaces.selected_scenario_id` is
genuinely updated in place -- this is exploratory state, not append-only
commercial history (see ADR-005).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from quotes import (
    ConfigurationSnapshot,
    NegotiationContext,
    PricingSnapshot,
    Scenario,
    ScenarioSource,
    ScenarioWorkspace,
)

from .scenario_repository import (
    DuplicateWorkspaceError,
    ScenarioNotFoundError,
    WorkspaceNotFoundError,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scenario_workspaces (
    quote_id TEXT PRIMARY KEY REFERENCES quotes(quote_id),
    base_version_number INTEGER NOT NULL,
    selected_scenario_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id TEXT PRIMARY KEY,
    quote_id TEXT NOT NULL REFERENCES scenario_workspaces(quote_id),
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    source_version_number INTEGER NOT NULL,
    configuration_snapshot_json TEXT NOT NULL,
    pricing_snapshot_json TEXT NOT NULL,
    negotiation_context_json TEXT,
    created_at TEXT NOT NULL
);
"""


class SQLiteScenarioRepository:
    """See ScenarioRepository (src/persistence/scenario_repository.py)
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

    def workspace_exists(self, quote_id: str) -> bool:
        conn = self._raw_connect()
        try:
            row = conn.execute(
                "SELECT 1 FROM scenario_workspaces WHERE quote_id = ?", (quote_id,)
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def get_workspace(self, quote_id: str) -> ScenarioWorkspace:
        conn = self._raw_connect()
        try:
            workspace_row = conn.execute(
                "SELECT quote_id, base_version_number, selected_scenario_id "
                "FROM scenario_workspaces WHERE quote_id = ?",
                (quote_id,),
            ).fetchone()
            if workspace_row is None:
                raise WorkspaceNotFoundError(f"No active workspace for quote {quote_id}")
            scenario_rows = conn.execute(
                "SELECT scenario_id, name, source, source_version_number, "
                "configuration_snapshot_json, pricing_snapshot_json, negotiation_context_json, "
                "created_at "
                "FROM scenarios WHERE quote_id = ? ORDER BY created_at",
                (quote_id,),
            ).fetchall()
        finally:
            conn.close()

        scenarios = tuple(self._row_to_scenario(row) for row in scenario_rows)
        return ScenarioWorkspace(
            quote_id=workspace_row[0],
            base_version_number=workspace_row[1],
            scenarios=scenarios,
            selected_scenario_id=workspace_row[2],
        )

    def create_workspace(self, workspace: ScenarioWorkspace) -> None:
        with self._transaction() as conn:
            try:
                conn.execute(
                    "INSERT INTO scenario_workspaces "
                    "(quote_id, base_version_number, selected_scenario_id, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        workspace.quote_id,
                        workspace.base_version_number,
                        workspace.selected_scenario_id,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise DuplicateWorkspaceError(
                    f"A workspace already exists for quote {workspace.quote_id}"
                ) from exc
            for scenario in workspace.scenarios:
                self._insert_scenario(conn, workspace.quote_id, scenario)

    def add_scenario(self, quote_id: str, scenario: Scenario) -> None:
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT 1 FROM scenario_workspaces WHERE quote_id = ?", (quote_id,)
            ).fetchone()
            if row is None:
                raise WorkspaceNotFoundError(f"No active workspace for quote {quote_id}")
            self._insert_scenario(conn, quote_id, scenario)

    def select_scenario(self, quote_id: str, scenario_id: str) -> None:
        with self._transaction() as conn:
            workspace_row = conn.execute(
                "SELECT 1 FROM scenario_workspaces WHERE quote_id = ?", (quote_id,)
            ).fetchone()
            if workspace_row is None:
                raise WorkspaceNotFoundError(f"No active workspace for quote {quote_id}")
            scenario_row = conn.execute(
                "SELECT 1 FROM scenarios WHERE quote_id = ? AND scenario_id = ?",
                (quote_id, scenario_id),
            ).fetchone()
            if scenario_row is None:
                raise ScenarioNotFoundError(
                    f"No scenario {scenario_id} in quote {quote_id}'s active workspace"
                )
            conn.execute(
                "UPDATE scenario_workspaces SET selected_scenario_id = ? WHERE quote_id = ?",
                (scenario_id, quote_id),
            )

    def clear_selection(self, quote_id: str) -> None:
        with self._transaction() as conn:
            cursor = conn.execute(
                "UPDATE scenario_workspaces SET selected_scenario_id = NULL WHERE quote_id = ?",
                (quote_id,),
            )
            if cursor.rowcount == 0:
                raise WorkspaceNotFoundError(f"No active workspace for quote {quote_id}")

    def clear_workspace(self, quote_id: str) -> None:
        with self._transaction() as conn:
            conn.execute("DELETE FROM scenarios WHERE quote_id = ?", (quote_id,))
            cursor = conn.execute(
                "DELETE FROM scenario_workspaces WHERE quote_id = ?", (quote_id,)
            )
            if cursor.rowcount == 0:
                raise WorkspaceNotFoundError(f"No active workspace for quote {quote_id}")

    @staticmethod
    def _insert_scenario(conn: sqlite3.Connection, quote_id: str, scenario: Scenario) -> None:
        conn.execute(
            "INSERT INTO scenarios "
            "(scenario_id, quote_id, name, source, source_version_number, "
            " configuration_snapshot_json, pricing_snapshot_json, negotiation_context_json, "
            " created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                scenario.scenario_id,
                quote_id,
                scenario.name,
                scenario.source.value,
                scenario.source_version_number,
                scenario.configuration_snapshot.model_dump_json(),
                scenario.pricing_snapshot.model_dump_json(),
                scenario.negotiation_context.model_dump_json()
                if scenario.negotiation_context is not None
                else None,
                scenario.created_at.isoformat(),
            ),
        )

    @staticmethod
    def _row_to_scenario(row: tuple) -> Scenario:
        (
            scenario_id,
            name,
            source,
            source_version_number,
            config_json,
            pricing_json,
            negotiation_json,
            created_at,
        ) = row
        return Scenario(
            scenario_id=scenario_id,
            name=name,
            source=ScenarioSource(source),
            source_version_number=source_version_number,
            configuration_snapshot=ConfigurationSnapshot.model_validate_json(config_json),
            pricing_snapshot=PricingSnapshot.model_validate_json(pricing_json),
            negotiation_context=(
                NegotiationContext.model_validate_json(negotiation_json)
                if negotiation_json is not None
                else None
            ),
            created_at=created_at,
        )

