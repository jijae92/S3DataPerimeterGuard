# Contributing Guide

## Branch Strategy
- `main`: protected, release-ready.
- `feature/*`: new features or improvements.
- `fix/*`: hotfixes or urgent patches.

## Pull Request Checklist
- Run `make test` and `make simulate`; attach summary of `/artifacts/findings.json` if relevant.
- Update docs (README/CHANGELOG) when behaviour changes.
- Changes touching `.guardrails-allow.json` require at least one security reviewer.
- Fill out PR template: summary, testing, security impact, rollback plan.

## Commit Convention
- Follow [Conventional Commits](https://www.conventionalcommits.org/).
  - `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, etc.

## Coding Standards
- Python: `ruff` + `black`.
- Infrastructure (SAM/CDK): run `cfn-lint` and `npm run lint` for dashboard.
- Enable pre-commit hooks if provided.

## Code of Conduct
- Treat collaborators with respect. Report incidents to `ops@example.com`.
