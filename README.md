# Northstar Pricing Studio

A portfolio case study showing how a complex B2B pricing workflow can be transformed from disconnected spreadsheets and manual proposal creation into a governed, configurable, auditable pricing application.

> **Portfolio note:** This project is entirely fictional. It does not contain employer data, source code, pricing rules, customer information, or proprietary business logic.

## Why this project exists

Commercial teams often manage pricing through a mix of spreadsheets, tribal knowledge, approval emails, and manually edited proposal documents. That creates four common problems: pricing logic is difficult to govern, sales teams cannot confidently self-serve, proposal creation takes too long, and pricing decisions are hard to audit or reproduce.

## Fictional business scenario

**Northstar Analytics** sells B2B market-intelligence subscriptions to enterprise customers. Pricing varies by subscription tier, number of users, geographic data coverage, historical data depth, contract term, premium support, implementation services, discount level, and renewal status.

## Product goal

Create a pricing application that allows a commercial user to configure a deal, calculate governed pricing, understand every adjustment, identify approval exceptions, save the quote, and produce proposal-ready output.

## MVP capabilities

- Configure a customer quote
- Evaluate pricing rules from YAML
- Produce an itemized price breakdown
- Flag approval-required discounts
- Save quote history
- Generate proposal-ready output
- Preserve an auditable record of the configuration and rules applied

## Architecture

```text
Streamlit UI
    |
    v
Application / Service Layer
    |
    +--> Pricing Engine ----> YAML Rule Configuration
    |
    +--> Quote Repository --> DuckDB / SQLite
    |
    +--> Proposal Renderer
```

## What this project demonstrates

**Product:** problem framing, personas/JTBD, MVP definition, metrics, roadmap, tradeoffs.  
**Strategy:** tiered pricing, discount governance, packaging, explainability, commercial workflow design.  
**Technical:** Python, config-driven rules, validation, modular architecture, tests, persistence, CI.

## Planned success metrics

| Metric | Target |
| --- | ---: |
| Median quote configuration time | < 10 minutes |
| Supported standard pricing configurations | >= 80% |
| Quotes reproducible from saved configuration | 100% |
| Pricing adjustments explained in breakdown | 100% |
| Invalid configuration caught before proposal | 100% |
| Automated test coverage of core pricing rules | >= 90% |

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

See `docs/PRD.md`, `docs/PRODUCT_DESIGN.md`, `docs/WIREFRAMES.md`, `docs/DESIGN_SYSTEM.md`, `docs/ARCHITECTURE.md`, and `docs/ROADMAP.md`.
