# AI Signal Brief

## What This Project Does

AI Signal Brief is an English-first public project skeleton for producing source-backed briefings about AI model, tooling, infrastructure, and deployment updates.

The intended production system will collect official and high-quality public sources, deduplicate recurring stories, generate canonical `report.json` records, and publish reviewable summaries for readers who track frontier AI updates.

## Why It Exists

AI news moves quickly and is often repeated across vendors, model releases, benchmarks, developer tools, and deployment announcements. This project is designed to make the daily signal auditable: every important claim should map back to sources, report runs should be reproducible, and public outputs should separate confirmed facts from analysis.

## Current Status

Phase 4 adds offline Markdown and Telegram-preview renderers that operate only on validated canonical report JSON. The repository is still local-first; no live ingestion, delivery, or publishing automation is implemented yet.

Not implemented yet:

- live news fetching
- model calls
- image generation
- Telegram delivery
- GitHub Actions scheduling
- historical report migration
- website generation
- DOCX generation

## Public Data And Source Policy

The project will prioritize official sources, primary technical sources, papers, repositories, regulatory filings, and clearly attributed public news. Reports should avoid copying private material, screenshots, proprietary assets, credentials, local machine paths, or unreviewed migration outputs.

Every material story should include source IDs and every important claim should be traceable to one or more sources.

## Output Formats

Planned canonical outputs:

- `report.json`: source-backed public report data
- `run.json`: execution metadata, artifact list, warnings, and delivery status
- Markdown, HTML, website, Telegram text, and DOCX may be generated later from canonical data

## Canonical Data Model

Initial schema drafts live in:

- `schemas/report.schema.json`
- `schemas/run.schema.json`

Readable documentation lives in:

- `docs/report-schema.md`
- `docs/run-schema.md`
- `docs/source-registry.md`
- `docs/offline-rendering.md`

## Local Development

Phase 4 uses only the Python standard library.

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m ai_signal_brief --version
python -m ai_signal_brief doctor
python -m ai_signal_brief validate-report examples/report.example.json
python -m ai_signal_brief validate-run examples/run.example.json
python -m unittest discover -s tests
```

No package installation is required for Phase 4.

Validation currently checks required fields, duplicate IDs, source references, ISO-8601 timestamps with timezones, English-language report output, source registry priority rules, official-source-first policy, and secret-like values in report/run/source JSON. Rendering refuses invalid reports and writes offline preview files only.

## Example Files

- `examples/report.example.json`
- `examples/run.example.json`
- `config/settings.example.json`
- `config/sources.example.json`

These examples are public-safe placeholders. They do not contain secrets, private paths, historical generated reports, or live API credentials.

## Roadmap

Near-term phases:

1. Build robust schema validation and CLI commands.
2. Add source ingestion with official-source priority.
3. Add deduplication and material-update detection.
4. Migrate historical reports privately into sanitized English canonical records.
5. Add site generation and GitHub Pages deployment.
6. Add Telegram delivery using GitHub Secrets after verification.
7. Add generated visual assets using a dedicated API key stored only as a secret.

## Security And Secrets

Never commit API keys, Telegram tokens, chat IDs, local env files, private migration files, generated private reports, screenshots, or local machine paths.

See `SECURITY.md` and `docs/security-and-secrets.md`.

## License

Code is licensed under the MIT License. Original report prose and project-created assets are intended to be licensed under CC BY 4.0, subject to the exclusions in `CONTENT-LICENSE.md`.