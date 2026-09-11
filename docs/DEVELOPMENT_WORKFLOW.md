# Development Workflow

This document describes how work should flow through Northstar Pricing Studio from this point forward. It's intentionally lightweight: trunk-based development with short-lived feature branches, not Git Flow.

```text
main
  |
  v
feature branch
  |
  v
meaningful commits
  |
  v
tests
  |
  v
push branch
  |
  v
pull request
  |
  v
review
  |
  v
merge
```

## Branching

Every non-trivial change starts on its own branch off `main`, named after the actual work:

| Pattern | Use for |
| --- | --- |
| `feat/<capability>` | new product or domain capability |
| `fix/<issue>` | a bug fix |
| `refactor/<area>` | internal restructuring with no behavior change |
| `docs/<topic>` | documentation-only changes |
| `test/<area>` | test-only additions or hardening |

Branch names should describe the capability, not the ticket number or the day of the week — e.g. `feat/budget-fit-engine`, not `feat/task-4a`.

`main` is always releasable. Nothing is committed to `main` directly once a feature branch is in flight for that work.

## Commits

A commit should represent one coherent engineering decision, not a snapshot of "whatever was in the working tree." Use [Conventional Commits](https://www.conventionalcommits.org/) style: `type(scope): summary`.

Good:

```text
feat(budget-fit): add constrained configuration search
test(budget-fit): cover feasibility and recommendation ranking
refactor(budget-fit): separate capability semantics from pricing
refactor(budget-fit): score capability preservation against baseline
```

Avoid a history dominated by `fix`, `fix again`, `oops`, `working`, `final`, `final2` — each of those is a sign the commit boundary was time-based rather than decision-based.

Equally, don't manufacture commits to look busy. Splitting one logical change into five commits with no independent meaning is worse than one honest commit. For a substantial feature, roughly 2-5 meaningful commits is a common outcome — a guideline, not a quota.

## Testing

Run the test suite before pushing:

```bash
python -m pytest tests/ -q
```

A feature branch should not be pushed with a known-failing test. If a bug is found and fixed mid-feature, the fix belongs in the commit (or a clearly-labeled follow-up commit) — not silently squashed away as if it never happened.

## Pull requests

Push the branch and open a PR against `main` using the repository's [PR template](../.github/pull_request_template.md). A PR should explain *why*, not just *what* — the diff already shows what changed.

Small, exploratory, or documentation-only branches may still go through this flow; the point is reviewability, not ceremony.

## Issues

For a substantial upcoming feature, opening a GitHub issue first (problem, scope, acceptance criteria, non-goals) is encouraged when it adds real planning value, so the PR can reference it. This is optional for small fixes and internal refactors — don't file an issue just to have one.

## What this workflow does not do

- It does not rewrite or force-push `main`.
- It does not retroactively fabricate PRs or issues for work that already happened directly on `main` before this workflow existed — that history stays as-is; see [`docs/DEVELOPMENT_HISTORY.md`](DEVELOPMENT_HISTORY.md) for how it's told honestly instead.
- It does not require a merge commit, squash policy, or release train beyond what's described here. If Northstar ever needs heavier process, that's a decision to make explicitly, not a default.
