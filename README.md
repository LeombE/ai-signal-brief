# AI Signal Brief

## What This Project Does

AI Signal Brief is an English-first public project skeleton for producing source-backed briefings about AI model, tooling, infrastructure, and deployment updates.

The intended production system will collect official and high-quality public sources, deduplicate recurring stories, generate canonical `report.json` records, and publish reviewable summaries for readers who track frontier AI updates.

## Why It Exists

AI news moves quickly and is often repeated across vendors, model releases, benchmarks, developer tools, and deployment announcements. This project is designed to make the daily signal auditable: every important claim should map back to sources, report runs should be reproducible, and public outputs should separate confirmed facts from analysis.

## Current Status

The repository is now public at `https://github.com/LeombE/ai-signal-brief`, and the latest GitHub Actions CI run is passing.

The project is still offline-first: no live ingestion, delivery, scheduled automation, external API usage, image generation, DOCX generation, historical migration, production daily Pages automation, or Telegram delivery is active. GitHub Pages sample preview is live at `https://leombe.github.io/ai-signal-brief/` and currently uses sample/example data only.

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
- manual GitHub Pages Preview workflow for sample data only
- publication, Pages planning, and release checklist documentation

Not implemented yet:

- live news fetching
- model calls
- image generation
- Telegram delivery
- GitHub Actions scheduling
- production GitHub Pages deployment from real reports
- historical report migration
- DOCX generation

## GitHub Publication Status

Repository URL: `https://github.com/LeombE/ai-signal-brief`

Current publication boundary:

- repository is public
- latest GitHub Actions CI is passing
- GitHub Pages sample preview is live: `https://leombe.github.io/ai-signal-brief/`
- manual Pages Preview workflow exists and publishes sample data only when run manually
- Telegram delivery is not connected
- OpenAI Image API is not configured
- no API keys are required for the current offline workflow
- no historical reports have been migrated
- no generated ignored outputs should be tracked

Publication planning docs:

- `docs/github-publication.md`
- `docs/pages-deployment-plan.md`
- `docs/release-checklist.md`

## CI Overview

The CI workflow lives at `.github/workflows/ci.yml`.

It runs offline validation only:

- Python compile check
- package version and doctor checks
- positive report, run, and source registry example validation
- cross-file quality gate
- archive build
- static site build
- public readiness audit
- unittest suite, including intentionally invalid fixtures through assertions

The CI workflow does not install runtime dependencies, fetch live sources, call APIs, send Telegram messages, generate images, create DOCX files, or deploy GitHub Pages.

## GitHub Pages Preview

The manual preview workflow lives at `.github/workflows/pages-preview.yml`.

It is triggered by `workflow_dispatch` only. It builds a sample archive and sample static site from the existing example JSON files, uploads `outputs/site-example` as a GitHub Pages artifact, and deploys it through the official GitHub Pages actions.

The Pages Preview workflow:

- publishes sample data only
- does not publish historical AI reports
- does not fetch live news
- does not send Telegram messages
- does not use OpenAI, Images, or API credentials
- does not generate images or DOCX files
- does not commit generated outputs to Git

GitHub Pages sample preview is live at `https://leombe.github.io/ai-signal-brief/`. It uses sample/example data only and does not currently run automatically on push or schedule.

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
- GitHub Pages Preview: manual sample static-site deployment from example JSON files only

Telegram delivery, DOCX, generated image assets, production Pages deployment, and historical report migration may be added in later approved phases.

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

This project currently uses only the Python standard library.

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

No package installation is required for the current offline workflow.

Validation checks required fields, duplicate IDs, source references, ISO-8601 timestamps with timezones, English-language report output, source registry priority rules, official-source-first policy, artifact shape, cross-file report/run/source consistency, and secret-like values in report/run/source JSON. Rendering, run metadata generation, quality gates, archive building, static site building, and public readiness auditing refuse invalid inputs.

## Example Files

- `examples/report.example.json`
- `examples/run.example.json`
- `config/settings.example.json`
- `config/sources.example.json`

These examples are public-safe placeholders. They do not contain secrets, private paths, historical generated reports, or live API credentials.

## Roadmap

Near-term phases:

1. Keep CI passing and documentation aligned with the public repository state.
2. Keep Pages sample preview limited to sample/example data until production publication is approved.
3. Add source ingestion with official-source priority.
4. Add deduplication and material-update detection.
5. Migrate historical reports privately into sanitized English canonical records.
6. Add production GitHub Pages deployment after static site outputs are reviewed.
7. Add Telegram delivery using GitHub Secrets after verification.
8. Add generated visual assets using a dedicated API key stored only as a secret.

## Security And Secrets

Never commit API keys, Telegram tokens, chat IDs, local env files, private migration files, generated private reports, screenshots, or local machine paths.

See `SECURITY.md` and `docs/security-and-secrets.md`.

## License

Code is licensed under the MIT License. Original report prose and project-created assets are intended to be licensed under CC BY 4.0, subject to the exclusions in `CONTENT-LICENSE.md`.