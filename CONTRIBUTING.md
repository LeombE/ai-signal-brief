# Contributing

## Development Principles

AI Signal Brief should be source-backed, reproducible, and safe to publish. Prefer clear data models, explicit provenance, small changes, and tests that can run locally without network access.

## Local Setup

Phase 1 uses only the Python standard library. No package installation is required.

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m ai_signal_brief doctor
python -m unittest discover -s tests
```

## Source And Citation Rules

- Prefer official and primary sources.
- Map important claims to source IDs.
- Separate factual claims from analysis.
- Do not copy long passages from third-party sources.
- Do not publish private migration material without review.

## Security Rules

- Do not commit secrets.
- Do not add private env files.
- Do not include local machine paths in public examples.
- Do not paste raw token scans into issues, docs, commits, or pull requests.

## Code Style

Keep the first implementation small and dependency-light. Add dependencies only when a later phase justifies them and records the reason.