"""Shared FastAPI dependencies.

get_quote_repository reads the live repository off app.state (set once
during the lifespan startup in api/main.py) rather than constructing a
hardcoded global -- so tests can override it via
app.dependency_overrides with a repository pointed at a temp-path
SQLite file, never the real data/northstar.db.

get_pricing_rules is the one canonical rules loader every pricing-aware
router (budget_fit, quotes, pricing) calls -- previously each router
defined its own identical @lru_cache-wrapped load_rules() call; this is
the single shared copy, so config/pricing_rules.yaml is never
re-parsed into three loaders that could drift.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from fastapi import Request

from persistence import BudgetFitRunRepository, QuoteRepository, ScenarioRepository, SQLiteQuoteRepository
from pricing_engine import load_rules

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "data" / "northstar.db"
RULES_PATH = ROOT / "config" / "pricing_rules.yaml"


def resolve_db_path() -> Path:
    override = os.environ.get("NORTHSTAR_DB_PATH")
    return Path(override) if override else DEFAULT_DB_PATH


def get_quote_repository(request: Request) -> QuoteRepository:
    return request.app.state.quote_repository


def get_scenario_repository(request: Request) -> ScenarioRepository:
    return request.app.state.scenario_repository


def get_budget_fit_run_repository(request: Request) -> BudgetFitRunRepository:
    return request.app.state.budget_fit_run_repository


@lru_cache(maxsize=1)
def get_pricing_rules() -> dict:
    return load_rules(RULES_PATH)
