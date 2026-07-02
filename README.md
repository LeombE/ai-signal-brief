# AI Signal Brief

## What This Project Does

AI Signal Brief is an English-first public project skeleton for producing source-backed briefings about AI model, tooling, infrastructure, and deployment updates.

The intended production system will collect official and high-quality public sources, deduplicate recurring stories, generate canonical `report.json` records, and publish reviewable summaries for readers who track frontier AI updates.

## Why It Exists

AI news moves quickly and is often repeated across vendors, model releases, benchmarks, developer tools, and deployment announcements. This project is designed to make the daily signal auditable: every important claim should map back to sources, report runs should be reproducible, and public outputs should separate confirmed facts from analysis.

## Current Status

Phase 10 prepares the repository for future GitHub publication by adding offline CI checks and publication documentation. The repository is still local-first; no live ingestion, delivery, scheduled automation, external API usage, or publishing automation is implemented yet.

Implemented so far:

- canonical report and run schema drafts
- stdlib-only report, run, and source registry validation
- offline Markdown rendering
- offline Telegram-preview text rendering without sending
- offline run metadata generation with deterministic test timestamps
- offline quality gates across report, run, and source registry files
- offline public archive builder with canonical date-based layout
- offline static site builder from generated archive data
- public readiness audit for tracked files
- GitHub Actions CI definition for offline checks
- publication, Pages planning, and release checklist documentation

Not implemented yet:

- live news fetching
- model calls
- image generation
- Telegram delivery
- GitHub Actions scheduling
- GitHub Pages deployment
- historical report migration
- DOCX generation

## GitHub Publication Status

The intended future public repository is `LeombE/ai-signal-brief`.

Current publication boundary:

- not yet pushed to GitHub
- no GitHub remote required yet
- not yet live on GitHub Pages
- not connected to Telegram
- no API keys required
- no historical reports migrated
- no generated ignored outputs should be tracked

Publication planning docs:

- `docs/github-publication.md`
- `docs/pages-deployment-plan.md`
- `docs/release-checklist.md`

## CI Overview

The Phase 10 CI workflow lives at `.github/workflows/ci.yml`.

It runs offline validation only:

- Python compile check
- package version and doctor checks
- report, run, and source registry validation
- cross-file quality gate
- archive build
- static site build
- public readiness audit
- unittest suite

The workflow does not install runtime dependencies, fetch live sources, call APIs, send Telegram messages, generate images, create DOCX files, or deploy GitHub Pages.

## Public Data And Source Policy

The project prioritizes official sources, primary technical sources, papers, repositories, regulatory filings, and clearly attributed public news. Reports should avoid copying private material, screenshots, proprietary assets, credentials, local machine paths, or unreviewed migration outputs.

Every material story should include source IDs and every important claim should be traceable to one or more sources.

## Output Formats

Canonical and offline-preview outputs:

- `report.json`: source-backed public report data
- `run.json`: execution metadata, artifact list, warnings, and delivery status
- Markdown: offline rendering from validated report JSON
- Telegram preview text: offline preview only; it does not send messages
- Archive layout: date-based public archive generated from validated report and run data
- Static site: offline HTML/CSS generated from an archive

Telegram delivery, DOCX, generated image assets, and Pages deployment may be added in later phases.

## Canonical Data Model

Initial schema drafts live in:

- `schemas/report.schema.json`
- `schemas/run.schema.json`

Readable documentation lives in:

- `docs/report-schema.md`
- `docs/run-schema.md`
- `docs/source-registry.md`
- `docs/offline-rendering.md`
- `docs/run-metadata.md`
- `docs/quality-gates.md`
- `docs/archive-builder.md`
- `docs/static-site-builder.md`
- `docs/public-readiness.md`
- `docs/github-publication.md`
- `docs/pages-deployment-plan.md`
- `docs/release-checklist.md`

## Local Verification

Phase 10 uses only the Python standard library.

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m compileall src
python -m ai_signal_brief --version
python -m ai_signal_brief doctor
python -m ai_signal_brief validate-report examples/report.example.json
python -m ai_signal_brief validate-run examples/run.example.json
python -m ai_signal_brief validate-sources config/sources.example.json
python -m ai_signal_brief quality-gate --report examples/report.example.json --run examples/run.example.json --sources config/sources.example.json
python -m ai_signal_brief archive-report --report examples/report.example.json --run examples/run.example.json --sources config/sources.example.json --out outputs/archive-example
python -m ai_signal_brief build-site --archive outputs/archive-example --out outputs/site-example
python -m ai_signal_brief public-readiness
python -m unittest discover -s tests
```

Additional offline commands:

```powershell
python -m ai_signal_brief render-markdown examples/report.example.json --out outputs/report.example.md
python -m ai_signal_brief render-telegram examples/report.example.json --out outputs/telegram.example.txt
python -m ai_signal_brief create-run-record --report examples/report.example.json --out outputs/run.example.generated.json --artifact markdown=outputs/report.example.md --artifact telegram_preview=outputs/telegram.example.txt --started-at 2026-06-24T04:00:00+08:00 --ended-at 2026-06-24T04:01:00+08:00 --timezone Asia/Kuala_Lumpur
python -m ai_signal_brief validate-run outputs/run.example.generated.json
```

No package installation is required for Phase 10.

Validation checks required fields, duplicate IDs, source references, ISO-8601 timestamps with timezones, English-language report output, source registry priority rules, official-source-first policy, artifact shape, cross-file report/run/source consistency, and secret-like values in report/run/source JSON. Rendering, run metadata generation, quality gates, archive building, static site building, and public readiness auditing refuse invalid inputs.

## Example Files

- `examples/report.example.json`
- `examples/run.example.json`
- `config/settings.example.json`
- `config/sources.example.json`

These examples are public-safe placeholders. They do not contain secrets, private paths, historical generated reports, or live API credentials.

## Roadmap

Near-term phases:

1. Prepare GitHub publication checks and release documentation.
2. Add reviewed publication workflow only after explicit approval.
3. Add source ingestion with official-source priority.
4. Add deduplication and material-update detection.
5. Migrate historical reports privately into sanitized English canonical records.
6. Add GitHub Pages deployment after static site outputs are reviewed.
7. Add Telegram delivery using GitHub Secrets after verification.
8. Add generated visual assets using a dedicated API key stored only as a secret.

## Security And Secrets

Never commit API keys, Telegram tokens, chat IDs, local env files, private migration files, generated private reports, screenshots, or local machine paths.

See `SECURITY.md` and `docs/security-and-secrets.md`.

## License

Code is licensed under the MIT License. Original report prose and project-created assets are intended to be licensed under CC BY 4.0, subject to the exclusions in `CONTENT-LICENSE.md`.
