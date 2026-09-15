# Northstar Frontend Experience Spike

An isolated React + TypeScript + Vite prototype of one screen —
**Optimize to Budget** — built to answer one question: can a dedicated
frontend materially improve on the Streamlit implementation's visual
fidelity to the approved Northstar wireframes?

See [`docs/FRONTEND_SPIKE.md`](../docs/FRONTEND_SPIKE.md) at the repo root
for the full write-up. This is a spike, not a migration: it renders a
static typed fixture (`src/fixtures/budgetFitFixture.ts`), never calls the
Python domain, and can be deleted without affecting the Streamlit app.

## Run it

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # production build to dist/
```

## Structure

```
src/
├── components/   Northstar UI primitives + the Optimize to Budget screen
├── fixtures/     static, realistic Budget Fit negotiation data
├── types/        typed shape the fixture (and later, a real API) fills
├── styles/       tokens.css (design tokens) + global.css (reset)
├── utils/        formatMoney (mirrors the Python app's format_money)
├── App.tsx
└── main.tsx
```

## What's real vs. mocked

- **Real**: layout, typography, interaction (editable target budget,
  constraint checkboxes, Find Options, Add to Compare).
- **Mocked**: the recommendations themselves are a static fixture, not a
  live call into `src/budget_fit`. No persistence, no Scenario or
  QuoteVersion creation.
