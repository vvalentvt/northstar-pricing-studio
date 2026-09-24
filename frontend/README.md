# Northstar Frontend

React + TypeScript + Vite frontend for Northstar Pricing Studio, promoted
from the `spike/frontend-experience` visual feasibility spike (see
[`../docs/FRONTEND_SPIKE.md`](../docs/FRONTEND_SPIKE.md)) into a
production-oriented workspace.

This checkpoint is structural only: the spike's components are reorganized
into `layouts/`, `components/`, and `features/budget-fit/`, but the
**Optimize to Budget** screen still renders its recommendations from a
static fixture, exactly as the spike did. Connecting it to a real API is
the next commit.

## Run it

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # production build to dist/
```

## Structure

```
src/
├── components/      generic reusable UI primitives (PageHeader, Panel, StatusBadge)
├── features/
│   └── budget-fit/  the Optimize to Budget screen and its own components
├── layouts/          AppShell (branded sidebar + nav canvas)
├── fixtures/         static, realistic Budget Fit negotiation data
├── types/            typed shape the fixture (and later, a real API) fills
├── styles/            tokens.css (design tokens) + global.css (reset)
├── utils/             formatMoney (mirrors the Python app's format_money)
├── App.tsx
└── main.tsx
```

## What's real vs. mocked

- **Real**: layout, typography, interaction (editable target budget,
  constraint checkboxes, Find Options, Add to Compare).
- **Mocked**: the recommendations themselves are a static fixture, not a
  live call into `src/budget_fit`. No persistence, no Scenario or
  QuoteVersion creation.
