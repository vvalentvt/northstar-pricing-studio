# ADR-003: Introduce a React/TypeScript frontend behind a FastAPI boundary

- **Status:** Accepted
- **Date:** 2026-09-24
- **Decision owners:** Northstar Pricing Studio portfolio project

## Context

Northstar's Python domain and application architecture (deterministic pricing engine, immutable QuoteVersions, scenario negotiation, Budget Fit optimization, Budget Fit → Scenario → QuoteVersion promotion) has become substantially more sophisticated than the visual experience Streamlit could comfortably deliver.

Several rounds of visual hardening (Phase 5) improved Streamlit's density, typography, and hierarchy through scoped CSS and theme tokens, but hit a ceiling: default Streamlit widget chrome, layout primitives, and interaction model kept the application reading as "a styled internal tool" rather than the compact, decision-oriented commercial workspace the approved wireframes (`docs/wireframes/*.svg`) depict.

A frontend feasibility spike (`docs/FRONTEND_SPIKE.md`, branch `spike/frontend-experience`) built one representative screen — Optimize to Budget — in React + TypeScript + Vite against a static fixture. Side-by-side comparison against both the wireframe and the Streamlit implementation showed a material, not incremental, improvement in visual hierarchy, information density, and recommendation-comparison clarity.

The open question the spike could not answer on its own: does that visual improvement survive contact with the real Python domain, or does it only work with hand-picked fixture data?

## Decision

Adopt an incremental, strangler-style migration:

```text
React + TypeScript frontend (frontend/)
        |
        v  HTTP (typed JSON)
FastAPI API boundary (api/)
        |
        v  direct function calls
existing Python application/domain (src/, app/)
```

Streamlit (`app/`) remains fully available and unmodified during the transition. Both presentation layers call the same underlying domain:

```text
Streamlit  ---> app/app_state.py ---> src/pricing_engine, src/quotes, src/budget_fit
React      ---> api/             ---> src/pricing_engine, src/quotes, src/budget_fit
```

The API layer is a thin translation boundary only: it converts HTTP request DTOs into existing domain calls (`BudgetFitRequest`, `BudgetFitConstraints`, `find_budget_fit`, ...) and translates domain results back into response DTOs. It must never reimplement pricing, scoring, or scenario logic — the domain in `src/` remains the single source of commercial truth for both presentation layers.

Migration proceeds workflow by workflow, not as a single cutover. The first slice (Phase 6A) is Budget Fit: a stateless `POST /api/budget-fit` endpoint, proven end-to-end from the React UI through to real optimizer results. Later slices will cover Review Pricing, Configure, and Scenario negotiation, each only after its React equivalent is validated against the real domain.

## Consequences

**Positive**

- A materially stronger product UI, validated against the real domain rather than only a static fixture.
- Clean frontend/backend separation: the React app depends only on the typed API contract, never on Python internals.
- The API's typed DTOs create an explicit, stable contract instead of ad hoc dict-shaped Streamlit session state.
- The Python domain investment (pricing engine, quote versioning, Budget Fit, scenario promotion) is fully preserved — the API adapts to the domain, not the reverse.
- Streamlit remains a working fallback and a reference implementation throughout the transition.

**Trade-offs**

- Two runtimes (Streamlit + FastAPI/React) must be developed and run locally during the transition.
- API request/response contracts must be maintained deliberately as the domain evolves; a schema change now has two consumers to update.
- Frontend build, type-checking, and (eventually) testing add a second toolchain to the repository alongside pytest.
- Duplication risk at the presentation-mapping edges (e.g. field display labels) exists on both sides unless deliberately shared; Phase 6A accepts a small, explicitly-scoped duplication here rather than introducing a coupling between the API and Streamlit's own `app/app_state.py`.

## Migration strategy

Workflow-by-workflow, proven end-to-end before the next slice begins:

1. **Phase 6A (this phase):** Budget Fit only. Stateless API endpoint, real optimizer results rendered in React. No persistence, no Scenario API, no auth.
2. **Later phases (not yet scoped):** Review Pricing, Configure, and the Budget Fit → Scenario → QuoteVersion promotion flow, each requiring its own API surface and, eventually, a durable quote resource once persistence is introduced.

Streamlit is not removed until a workflow's React equivalent has been built, connected to the real API, and visually/functionally validated. This ADR does not commit to a removal timeline for Streamlit or to a final decision that the migration will reach 100% completion — see `docs/FRONTEND_SPIKE.md` for what remains explicitly undecided.
