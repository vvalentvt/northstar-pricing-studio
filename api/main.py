"""Northstar API — a thin FastAPI boundary in front of the existing
Python domain (src/pricing_engine, src/quotes, src/budget_fit).

Development:

    python -m uvicorn api.main:app --reload

Production (see docs/DEPLOYMENT.md): same command, without --reload,
plus NORTHSTAR_ENV=production so this module also serves the built
React SPA (frontend/dist) same-origin, instead of relying on a
separately-hosted Vite dev server.

See ADR-003 (docs/adr/003-frontend-api-separation.md) for the history
of this boundary; it originally existed alongside a Streamlit
prototype (retired in Phase 7A once React/FastAPI covered the full
workflow) rather than replacing it outright.
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

#: "production" enables same-origin SPA serving below and skips the
#: dev-only CORS allowance (same origin needs no CORS at all). Anything
#: else (including unset) is treated as development. See
#: docs/DEPLOYMENT.md.
NORTHSTAR_ENV = os.environ.get("NORTHSTAR_ENV", "development")
FRONTEND_DIST = ROOT / "frontend" / "dist"


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

# Dev-only: the Vite dev server runs on a different origin, so it needs
# CORS to call this API. In production the built SPA is served
# same-origin (below), which needs no CORS at all -- never a wildcard
# origin here (see Phase 7A spec section 38).
if NORTHSTAR_ENV != "production":
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


# Production SPA serving: FastAPI is the one process a deployment needs
# to run (see docs/DEPLOYMENT.md). Registered last so every /api/* route
# above always wins; only active when a production build actually
# exists -- `npm run dev`'s separate Vite server is untouched otherwise.
if FRONTEND_DIST.is_dir():
    app.mount(
        "/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets"
    )

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith("api/"):
            # An unmatched /api/* path is a real 404, never the SPA shell.
            raise HTTPException(status_code=404, detail="Not found")
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        # Any other path (including a deep client-side route like
        # /quotes/Q-123/review) falls back to the SPA shell, which
        # resolves it with React Router -- this is what makes a browser
        # refresh on a deep route work in production.
        return FileResponse(FRONTEND_DIST / "index.html")
