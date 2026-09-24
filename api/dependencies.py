"""Shared FastAPI dependencies.

get_quote_repository reads the live repository off app.state (set once
during the lifespan startup in api/main.py) rather than constructing a
hardcoded global -- so tests can override it via
app.dependency_overrides with a repository pointed at a temp-path
SQLite file, never the real data/northstar.db.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import Request

from persistence import QuoteRepository, SQLiteQuoteRepository

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "data" / "northstar.db"


def resolve_db_path() -> Path:
    override = os.environ.get("NORTHSTAR_DB_PATH")
    return Path(override) if override else DEFAULT_DB_PATH


def get_quote_repository(request: Request) -> QuoteRepository:
    return request.app.state.quote_repository
