# Frontend Experience Spike

## Question

Can a dedicated frontend materially improve Northstar's product experience
relative to Streamlit?

## Prototype

React + TypeScript + Vite (`frontend-spike/`), CSS Modules with a small
`src/styles/tokens.css` custom-property layer instead of Tailwind — chosen
because a single-screen prototype doesn't need a utility-class framework's
build surface, and CSS variables let the token layer stay just as small
and intentional without adding a dependency.

One screen implemented: **Optimize to Budget**, built against a static
typed fixture (`src/fixtures/budgetFitFixture.ts`, shaped by
`src/types/budgetFit.ts`), not the live Python domain. No API call, no
persistence, no Scenario/QuoteVersion integration — this spike isolates
the frontend-technology question from the integration question.

## What is being evaluated

- visual fidelity to the approved wireframe language
- information density (does it fix Streamlit's report-card sprawl?)
- interaction quality (does editing/revealing/comparing feel immediate?)
- maintainability of the component/token structure
- migration cost, if the answer to the first question is yes

## Not yet decided

- whether Northstar will migrate off Streamlit
- final frontend stack (this spike is not a commitment past React/TS/Vite)
- API framework or contract between a frontend and the Python domain
- deployment architecture

This document records evidence from one prototype screen. It is not an
architecture decision — no ADR has been written, and none should be
inferred from this spike existing.

## Result of this spike

See the final chat response for the full assessment. Screenshots comparing
the approved wireframe, the current Streamlit implementation, and this
prototype are the primary evidence; this document intentionally doesn't
restate a verdict that belongs in the conversation record, since screenshots
are what should actually be reviewed to decide.
