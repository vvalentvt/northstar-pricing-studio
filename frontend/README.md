# Northstar Frontend

React + TypeScript + Vite frontend for Northstar Pricing Studio, connected
to the real Python domain through a FastAPI boundary (`../api`).

Promoted from the `spike/frontend-experience` visual feasibility spike
(see [`../docs/FRONTEND_SPIKE.md`](../docs/FRONTEND_SPIKE.md)) once that
spike proved a material visual improvement over the Streamlit
implementation. See [`../docs/adr/003-frontend-api-separation.md`](../docs/adr/003-frontend-api-separation.md)
for the migration decision and strategy.

This is one screen (**Optimize to Budget**) of an incremental,
workflow-by-workflow migration -- not a full replacement of the Streamlit
app (`../app`), which remains fully functional. See the repo root
[`README.md`](../README.md) for the current split between the two.

## Run it

Requires the API running first (see `../api`):

```bash
# Terminal 1, from the repo root
python -m uvicorn api.main:app --reload

# Terminal 2
cd frontend
npm install
npm run dev       # http://localhost:5173
```

```bash
npm run build      # production build to dist/
```

## Structure

```
src/
├── api/            typed API client (client.ts, budgetFit.ts) + wire DTOs (types.ts)
├── components/      generic reusable UI primitives (PageHeader, Panel, StatusBadge)
├── features/
│   └── budget-fit/  the Optimize to Budget screen and its own components
├── layouts/         AppShell (branded sidebar + nav canvas)
├── fixtures/        local fixture for quote/account context (no durable quote API yet)
├── types/           the UI's own working types (src/api maps DTOs into these)
├── styles/          tokens.css (design tokens) + global.css (reset)
├── utils/           formatMoney/formatTier/formatCoverage (mirror the Python app's own formatting)
├── App.tsx
└── main.tsx
```

## What's real vs. still fixture-based

- **Real**: Budget Fit recommendations -- `src/api/budgetFit.ts` calls the
  live FastAPI endpoint, which calls the real optimizer
  (`src/budget_fit` in the Python domain). Loading, error, and no-fit
  states are all driven by genuine API responses.
- **Fixture-based**: quote/account context and the committed
  configuration (`src/fixtures/budgetFitFixture.ts`) -- there is no
  durable quote resource yet (see ADR-003's non-goals).
- **Frontend-local only**: "Add to Compare" toggles local UI state. It
  does not call `ScenarioWorkspace` -- that's a later migration slice.
