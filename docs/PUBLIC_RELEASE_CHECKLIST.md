# Public Release Checklist

Operational checklist for the repository owner before (and at) the public GitHub release of Northstar Pricing Studio. Not a project-management document — just the gate.

- [ ] `python -m pytest tests/ -q` green
- [ ] `cd frontend && npm run test` green
- [ ] `cd frontend && npm run build` green (or `npm run validate` from the repo root)
- [ ] `docker build -t northstar-pricing-studio .` succeeds (if Docker is available)
- [ ] `NORTHSTAR_DB_PATH` documented and pointed at persistent storage in whatever environment this is actually deployed to (see `docs/DEPLOYMENT.md`)
- [ ] Secrets scan: no API keys, tokens, passwords, or `.env` files committed (`git log -p` spot check + working-tree grep)
- [ ] Public-data/IP review: no real employer names, proprietary pricing terms, real customer data, or local absolute paths in tracked files
- [ ] README reflects the finished product (not a construction diary)
- [ ] Screenshots captured and added to the README screenshots section (Quotes, Configure, Review Pricing, Budget Fit, Alternatives, Proposal workspace, generated PDF)
- [ ] Deployment verified against the Docker image (or documented as unverified, with the specific limitation named)
- [ ] At least one generated Proposal PDF opened and visually checked (page breaks, footer, no clipped text, no internal governance fields)
- [ ] Streamlit fully removed (`app/`, `.streamlit/`, the `streamlit` dependency, and Streamlit-only tests)
- [ ] LICENSE decision made (a LICENSE file already exists at the repo root — confirm it's still the intended choice before going public)
- [ ] `git status` clean, nothing unintentionally staged or untracked
- [ ] Release tag created **after** this checklist is complete and the branch is merged (see the README/CHANGELOG for the recommended first tag)
