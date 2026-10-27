"""Presentation-neutral ScenarioWorkspace persistence boundary.

This module defines the *interface* only -- exceptions and a Protocol
every ScenarioRepository implementation satisfies. src/quotes never
imports from here and never depends on any storage technology; only
api/ depends on a concrete implementation such as
SQLiteScenarioRepository.

A ScenarioWorkspace is exploratory negotiation state, not commercial
history (see ADR-005): unlike QuoteRepository, this repository's writes
are genuinely mutable (selecting a different Scenario, clearing a
workspace after promotion) because nothing it stores is a committed
pricing decision.
"""

from __future__ import annotations

from typing import Protocol

from quotes import Scenario, ScenarioWorkspace


class WorkspaceNotFoundError(Exception):
    """No active ScenarioWorkspace exists for the given quote_id."""


class DuplicateWorkspaceError(Exception):
    """A ScenarioWorkspace already exists for this quote_id. Only one
    active workspace per quote is supported -- see Phase 6E spec
    section 5."""


class ScenarioNotFoundError(Exception):
    """The workspace exists, but not the requested scenario_id."""


class ScenarioRepository(Protocol):
    """ScenarioWorkspace-aggregate persistence. Deliberately not a
    generic CRUD repository -- every method mirrors an operation the
    domain's own ScenarioWorkspace already supports (add_scenario,
    select_scenario, clear_selection), plus the lifecycle operations
    (create/clear) a durable, one-workspace-per-quote model needs.
    """

    def workspace_exists(self, quote_id: str) -> bool: ...

    def get_workspace(self, quote_id: str) -> ScenarioWorkspace:
        """Load the active workspace and every Scenario in it. Raises
        WorkspaceNotFoundError if none exists for this quote."""
        ...

    def create_workspace(self, workspace: ScenarioWorkspace) -> None:
        """Persist a brand-new active workspace (and any Scenarios it
        already contains, though it is typically empty at creation).
        Raises DuplicateWorkspaceError if quote_id already has one."""
        ...

    def add_scenario(self, quote_id: str, scenario: Scenario) -> None:
        """Append one Scenario to the quote's active workspace. Raises
        WorkspaceNotFoundError if there is no active workspace."""
        ...

    def select_scenario(self, quote_id: str, scenario_id: str) -> None:
        """Mark one Scenario in the active workspace as selected.
        Raises WorkspaceNotFoundError or ScenarioNotFoundError."""
        ...

    def clear_selection(self, quote_id: str) -> None:
        """Clear the active workspace's selection, if any. Raises
        WorkspaceNotFoundError if there is no active workspace."""
        ...

    def clear_workspace(self, quote_id: str) -> None:
        """Delete the active workspace and all of its Scenarios --
        never touches quotes or quote_versions. Used after a successful
        promotion and when starting fresh exploration. Raises
        WorkspaceNotFoundError if there is no active workspace."""
        ...
