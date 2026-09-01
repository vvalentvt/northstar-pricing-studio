# Architecture

## Design goals
Simple enough for a portfolio project, structured like a maintainable business application.

### Streamlit UI
User input and presentation only; no pricing math in the UI.

### Domain models
Pydantic models validate quote configuration and outputs.

### Pricing engine
Pure Python functions receive validated configuration + rules and return list price, adjustments, discount, final price, approval status, and explanations.

### Rule configuration
YAML stores changeable pricing rules so strategy can evolve independently of application architecture.

### Persistence
Later milestone: DuckDB quote history and audit data.

### Proposal renderer
Later milestone: approved quote to HTML/PDF.

## Future extensions
Rule versioning, approval workflow, CRM integration, scenario comparison, pricing analytics, role-based access.
