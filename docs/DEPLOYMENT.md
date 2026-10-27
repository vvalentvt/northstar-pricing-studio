# Deployment

Northstar deploys as **one process**: FastAPI serves both the JSON API
(`/api/*`) and the built React SPA (everything else), backed by a
single SQLite file. There is no separate frontend host, load balancer,
or second service to run.

```text
Browser
    |
    v
FastAPI (api/main.py)
    +--> /api/*                      -- JSON API
    +--> everything else             -- React static build, SPA fallback
            |
            v
    SQLite file (NORTHSTAR_DB_PATH), on a persistent volume
```

This document is provider-neutral; it does not pick or provision a
hosting platform.

## Building the image

```bash
docker build -t northstar-pricing-studio .
```

The `Dockerfile` is a two-stage build: a Node stage builds the React
SPA (`frontend/dist`), and a Python stage installs `requirements.txt`,
copies `api/`, `src/`, `config/`, and the built SPA, then runs
uvicorn. See the `Dockerfile` itself for the exact steps.

## Running it

```bash
docker run -p 8000:8000 \
  -e NORTHSTAR_DB_PATH=/data/northstar.db \
  -v northstar-data:/data \
  northstar-pricing-studio
```

Open `http://localhost:8000` — the SPA and API are both served from
that one origin.

## Environment variables

See `.env.example` for the reference list. The three that matter in
production:

| Variable | Purpose | Default |
| --- | --- | --- |
| `NORTHSTAR_DB_PATH` | Where SQLite persists Quotes/Proposals/negotiation state | `data/northstar.db` (repo-relative) |
| `NORTHSTAR_ENV` | `production` serves the built SPA same-origin and skips dev-only CORS | `development` |
| `PORT` | Port uvicorn binds to (read by the Dockerfile's `CMD`, not by Python code) | `8000` |

## Persistent storage is required

**Container-local storage does not survive a redeploy or restart of a
fresh container.** `NORTHSTAR_DB_PATH` must point at a volume that
outlives the container (a Docker named volume, a mounted disk, or
whatever persistent-volume mechanism the chosen platform offers) if
Quote and Proposal history should survive beyond one container's
lifetime. The application creates the configured database's parent
directory automatically if it doesn't exist; it does not create or
manage the volume itself.

## Production start command

Without Docker, the equivalent bare command is:

```bash
NORTHSTAR_ENV=production python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Never pass `--reload` in production. Build the frontend first
(`npm run build` from `frontend/`, or from the repo root) so
`frontend/dist` exists for FastAPI to serve — without it, `api/main.py`
quietly serves the API only, with no SPA routes mounted.

## Health check

`GET /api/health` returns `{"status": "ok"}` and does no expensive
work — safe for a platform's liveness/readiness probe.

## What this does not cover

No authentication, no multi-instance/HA setup, no managed database,
no CDN, no observability stack. Northstar is a single-process
portfolio application; none of that is in scope (see the Non-Goals in
each phase's spec and `docs/ARCHITECTURE.md` section 15).
