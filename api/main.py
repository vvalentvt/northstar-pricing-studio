"""Northstar API — a thin FastAPI boundary in front of the existing
Python domain (src/pricing_engine, src/quotes, src/budget_fit).

Run locally with:

    python -m uvicorn api.main:app --reload

See ADR-003 (docs/adr/003-frontend-api-separation.md) for why this
exists alongside the Streamlit app rather than replacing it.
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from persistence import (
    SQLiteBudgetFitRunRepository,
    SQLiteProposalRepository,
    SQLiteQuoteRepository,
    SQLiteScenarioRepository,
)
from proposals import ReportLabProposalRenderer

from api.dependencies import resolve_db_path
from api.routers.alternatives import router as alternatives_router
from api.routers.budget_fit import router as budget_fit_router
from api.routers.pricing import router as pricing_router
from api.routers.proposals import router as proposals_router
from api.routers.quotes import router as quotes_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Each repository's __init__ runs its own idempotent CREATE TABLE IF
    # NOT EXISTS schema init -- one instance per repository, opened once
    # at startup and reused for the process lifetime, not per-request.
    # SQLiteQuoteRepository must be constructed first: scenario_workspaces,
    # scenarios, budget_fit_runs, and proposals all have a foreign key to
    # quotes/quote_versions.
    db_path = resolve_db_path()
    app.state.quote_repository = SQLiteQuoteRepository(db_path)
    app.state.scenario_repository = SQLiteScenarioRepository(db_path)
    app.state.budget_fit_run_repository = SQLiteBudgetFitRunRepository(db_path)
    app.state.proposal_repository = SQLiteProposalRepository(db_path)
    app.state.proposal_renderer = ReportLabProposalRenderer()
    yield


app = FastAPI(
    title="Northstar Pricing Studio API",
    description="Typed HTTP boundary in front of the existing Python pricing/quote/Budget Fit domain.",
    version="0.1.0",
    lifespan=lifespan,
)

# Local development only -- the Vite dev server's origin. No wildcard,
# no production origins configured yet (see ADR-003; auth/deployment
# are explicitly out of scope for this phase).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)

app.include_router(alternatives_router)
app.include_router(budget_fit_router)
app.include_router(pricing_router)
app.include_router(proposals_router)
app.include_router(quotes_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
