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
- manual Topic Scan Preview workflow for mock topic-candidate artifacts only
- publication, Pages planning, production Pages readiness, reviewed report staging, reviewed report dry-run helper command, daily topic discovery architecture, topic source registry and candidate schema examples, live-source discovery readiness, disabled live-source registry example, live-source registry extension planning, and release checklist documentation

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
- manual Topic Scan Preview workflow exists and uploads mock topic candidates as a short-lived artifact only
- Telegram delivery is not connected
- OpenAI Image API is not configured
- no API keys are required for the current offline workflow
- no historical reports have been migrated
- no generated ignored outputs should be tracked

Publication planning docs:

- `docs/github-publication.md`
- `docs/pages-deployment-plan.md`
- `docs/production-pages-readiness.md`
- `docs/reviewed-report-staging.md`
- `docs/reviewed-report-dry-run.md`
- `docs/reviewed-report-dry-run-command-plan.md`
- `docs/first-reviewed-report-candidate-plan.md`
- `docs/daily-topic-discovery-architecture.md`
- `docs/topic-sources-and-candidates.md`
- `docs/offline-mock-topic-discovery.md`
- `docs/topic-scan-preview-workflow.md`
- `docs/live-source-discovery-readiness.md`
- `docs/live-source-registry-extension-plan.md`
- `config/topic_sources.live.example.json`
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

## Topic Scan Preview

The manual topic scan preview workflow lives at `.github/workflows/topic-scan-preview.yml`.

It is triggered by `workflow_dispatch` only. It runs offline mock topic discovery from `tests/fixtures/topic_observations.valid.json`, writes generated topic candidates under `outputs/topic-candidates/${{ github.run_id }}/`, validates and ranks the generated JSON, and uploads it as the `topic-candidates-preview` artifact for 7 days.

The Topic Scan Preview workflow:

- uses mock fixture observations only
- does not fetch live sources
- does not publish reports
- does not deploy GitHub Pages
- does not send Telegram messages
- does not call OpenAI APIs
- does not generate images or DOCX files
- does not commit generated outputs to Git


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

Telegram delivery, DOCX, generated image assets, production Pages deployment, and historical report migration may be added in later approved phases. Production Pages requirements are documented in `docs/production-pages-readiness.md`; future reviewed report staging rules are documented in `docs/reviewed-report-staging.md`, and local dry-run rules are documented in `docs/reviewed-report-dry-run.md`; a dry-run helper command plan is documented in `docs/reviewed-report-dry-run-command-plan.md`, first-candidate selection rules are documented in `docs/first-reviewed-report-candidate-plan.md`, future daily topic discovery architecture is documented in `docs/daily-topic-discovery-architecture.md`, offline mock topic discovery is documented in `docs/offline-mock-topic-discovery.md`, and live-source readiness is documented in `docs/live-source-discovery-readiness.md`.

The first manual `Topic Scan Preview` run on `main` completed successfully. It uploaded one short-lived `topic-candidates-preview` artifact containing `topic-candidates.json`, and the artifact was manually inspected as mock placeholder output only. Live-source discovery remains unimplemented; future requirements and safety gates are documented in `docs/live-source-discovery-readiness.md`, future registry extension fields are documented in `docs/live-source-registry-extension-plan.md`, and the disabled-by-default example registry lives at `config/topic_sources.live.example.json`.

## Canonical Data Model

Initial schema drafts live in:

- `schemas/report.schema.json`
- `schemas/run.schema.json`
- `schemas/topic-candidates.schema.json`

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
- `docs/production-pages-readiness.md`
- `docs/reviewed-report-staging.md`
- `docs/reviewed-report-dry-run.md`
- `docs/reviewed-report-dry-run-command-plan.md`
- `docs/first-reviewed-report-candidate-plan.md`
- `docs/daily-topic-discovery-architecture.md`
- `docs/topic-sources-and-candidates.md`
- `docs/offline-mock-topic-discovery.md`
- `docs/topic-scan-preview-workflow.md`
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
python -m ai_signal_brief validate-topic-sources config/topic_sources.example.json
python -m ai_signal_brief validate-topic-sources config/topic_sources.live.example.json
python -m ai_signal_brief validate-topics examples/topic-candidates.example.json
python -m ai_signal_brief rank-topics examples/topic-candidates.example.json --explain
python -m ai_signal_brief discover-topics --date 2026-06-24 --sources config/topic_sources.example.json --mock-observations tests/fixtures/topic_observations.valid.json --out outputs/topic-candidates/2026-06-24.json --rank
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
python -m ai_signal_brief dry-run-reviewed-report --date YYYY-MM-DD --report reports-reviewed/YYYY/MM/DD/report.json --run reports-reviewed/YYYY/MM/DD/run.json --sources config/sources.example.json --archive-out outputs/reviewed-dry-run/YYYY/MM/DD --site-out outputs/reviewed-site-dry-run/YYYY/MM/DD --strict
```

No package installation is required for the current offline workflow.

Validation checks required fields, duplicate IDs, source references, ISO-8601 timestamps with timezones, English-language report output, source registry priority rules, official-source-first policy, topic source registry rules, topic candidate references, artifact shape, cross-file report/run/source consistency, and secret-like values in report/run/source/topic JSON. Offline mock topic discovery reads local observation fixtures, validates the topic source registry, writes candidate JSON under `outputs/`, validates generated candidates, and can run ranking without network access. Offline topic ranking validates candidates first, applies deterministic score normalization, preserves dedup evidence, and refuses unsafe output paths. Rendering, run metadata generation, quality gates, archive building, static site building, and public readiness auditing refuse invalid inputs.

## Example Files

- `examples/report.example.json`
- `examples/run.example.json`
- `config/settings.example.json`
- `config/sources.example.json`
- `config/topic_sources.example.json`
- `examples/reviewed-report-template/`
- `examples/topic-candidates.example.json`

These examples are public-safe placeholders. They do not contain secrets, private paths, historical generated reports, or live API credentials.

## Roadmap

Near-term phases:

1. Keep CI passing and documentation aligned with the public repository state.
2. Keep Pages sample preview limited to sample/example data until production publication is approved.
3. Keep topic source validation, topic candidate validation, mock topic discovery, and topic ranking offline; add live daily topic discovery only after separate approval.
4. Extend reviewed-report promotion from ranked topic candidates only after manual review.
5. Stage future manually reviewed English canonical reports under `reports-reviewed/` only after review.
6. Use `docs/production-pages-readiness.md` before approving production GitHub Pages deployment.
7. Add Telegram delivery using GitHub Secrets after verification.
8. Add generated visual assets using a dedicated API key stored only as a secret.

## Security And Secrets

Never commit API keys, Telegram tokens, chat IDs, local env files, private migration files, generated private reports, screenshots, or local machine paths.

See `SECURITY.md` and `docs/security-and-secrets.md`.

## License

Code is licensed under the MIT License. Original report prose and project-created assets are intended to be licensed under CC BY 4.0, subject to the exclusions in `CONTENT-LICENSE.md`.
