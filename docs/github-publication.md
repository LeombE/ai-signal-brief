# GitHub Publication Plan

This repository is now public at `https://github.com/LeombE/ai-signal-brief`.

This document records the current public status and the live sample Pages Preview boundary. It does not configure production daily automation, API keys, Telegram delivery, image generation, DOCX generation, scheduled automation, or historical report migration.

## Current Repository Status

Repository URL:

```text
https://github.com/LeombE/ai-signal-brief
```

Current status:

- repository is public
- latest GitHub Actions CI run is passing
- offline validation commands exist
- offline render, archive, site, and readiness checks exist
- GitHub Actions CI runs offline checks only
- manual Pages Preview workflow exists and is `workflow_dispatch` only
- GitHub Pages sample preview is live: `https://leombe.github.io/ai-signal-brief/`
- no Telegram delivery is configured
- OpenAI Image API is not configured
- no secrets are required for the current offline workflow
- historical reports have not been migrated

## Current Publication Boundary

The repository is public, but it is not a production service. The current project is an offline, public-safe skeleton and validation pipeline.

The Pages Preview workflow publishes sample data only from `examples/report.example.json`, `examples/run.example.json`, and `config/sources.example.json` to `https://leombe.github.io/ai-signal-brief/`. It does not publish historical reports, production daily reports, or private migration content.

Future live ingestion, production Pages deployment, Telegram delivery, image generation, DOCX generation, and historical migration must be added only in later approved phases.

## Ongoing Public Repo Checks

Before adding any new public-facing capability:

1. Confirm `git branch --show-current` returns `main`.
2. Confirm `git status --short` is empty.
3. Confirm `git remote -v` points to `https://github.com/LeombE/ai-signal-brief.git`.
4. Confirm the latest GitHub Actions CI run is passing.
5. Run `python -m ai_signal_brief public-readiness` locally and confirm PASS.
6. Run `python -m unittest discover -s tests` locally and confirm OK.
7. Confirm no secrets, local env values, tokens, or API keys are present.
8. Confirm no private migration source content is present.
9. Confirm generated ignored outputs are not tracked.
10. Confirm no Telegram token is present.
11. Confirm no OpenAI API key is present.
12. Confirm no chat identifier is present.
13. Confirm no historical reports have been migrated without review.
14. Confirm GitHub Pages publishes sample/example data only.
15. Confirm no production deployment workflow, Telegram workflow, or OpenAI Image API workflow is active.
16. Confirm the only Pages workflow is manual sample preview unless a later phase approves production publication.
17. Confirm the intended public owner and repository name remain `LeombE/ai-signal-brief`.