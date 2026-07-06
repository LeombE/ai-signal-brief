# AI Signal Brief

AI Signal Brief produces source-backed English AI news briefs focused on AI models, developer tooling, research, infrastructure, safety, policy, and product updates. It fetches allowlisted public sources, ranks editorially relevant updates, writes reviewable report artifacts, and can send a concise Telegram brief when the generated report passes its `telegram_ready` gate.

## Current Status

- Public repository: `https://github.com/LeombE/ai-signal-brief`
- Daily AI Report automation exists at `.github/workflows/daily-ai-report.yml`.
- Telegram delivery has been tested through manual local sending and GitHub Actions `workflow_dispatch` runs.
- The scheduled workflow is configured for `21:00 UTC` daily, which is `05:00 Asia/Kuala_Lumpur` daily.
- Reports are uploaded as GitHub Actions artifacts and local `outputs/` files; generated outputs are not committed.
- OpenAI API is not used by default. The current report pipeline runs without model API calls.
- The first scheduled 05:00 Malaysia run still needs to be observed after it happens.

## What It Does

- Fetches allowlisted public AI sources over HTTPS.
- Extracts article-level items and publication/update dates where available.
- Separates stale or date-missing items from the main Telegram-ready update set.
- Ranks source-backed, editorially relevant AI updates.
- Generates `report.json`, `report.md`, and `report.docx` artifacts.
- Sends a Telegram message only when `telegram_ready` is true.
- Includes reader-facing Telegram content: title, date, readiness status, ranked updates, source names, source URLs, confidence, freshness, and an artifact note.
- Uploads generated report files as GitHub Actions artifacts.

## What It Does Not Do Yet

- Does not use OpenAI by default.
- Does not generate images.
- Does not deploy production GitHub Pages from real reports.
- Does not commit generated outputs.
- Does not expose secrets in code, logs, docs, or report artifacts.
- Does not use private sources.

## Quick Start For Local Use

This project currently has no runtime dependencies beyond the Python standard library. The package metadata targets Python 3.12+, and the source-tree commands below work without installing third-party packages.

```powershell
git clone https://github.com/LeombE/ai-signal-brief.git
cd ai-signal-brief
$env:PYTHONPATH = (Resolve-Path .\src).Path
```

Run local checks:

```powershell
python -m compileall src
python -m unittest discover -s tests
python -m ai_signal_brief public-readiness
```

Maintainer CLI map:

- Validation: `validate-report`, `validate-run`, `validate-sources`, `validate-topic-sources`, `validate-topics`
- Topic workflow helpers: `discover-topics`, `rank-topics`, `fetch-source-replay`
- Rendering and metadata: `render-markdown`, `render-telegram`, `create-run-record`
- Artifact checks and publication previews: `quality-gate`, `archive-report`, `build-site`, `public-readiness`

Generate a daily report locally without Telegram delivery:

```powershell
python -m ai_signal_brief build-daily-ai-report `
  --date YYYY-MM-DD `
  --timezone Asia/Kuala_Lumpur `
  --out outputs/daily-reports/YYYY-MM-DD-live `
  --format markdown,json,docx `
  --english-only `
  --no-openai `
  --sources config/live_ai_sources.example.json `
  --max-items 10 `
  --lookback-hours 48 `
  --min-fresh-items 3
```

The generated files are written under `outputs/daily-reports/YYYY-MM-DD-live/`. The `outputs/` directory is ignored by Git; outputs are not committed.

## Telegram Automation

The scheduled Telegram workflow lives at `.github/workflows/daily-ai-report.yml`.

Schedule and trigger:

- Schedule: `21:00 UTC` daily / `05:00 Asia/Kuala_Lumpur` daily
- Cron: `0 21 * * *`
- Manual test trigger: GitHub Actions → Daily AI Report → Run workflow
- Workflow page: https://github.com/LeombE/ai-signal-brief/actions/workflows/daily-ai-report.yml

Required GitHub repository secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Safety behavior:

- Never commit or print Telegram secrets.
- Never commit tokens, chat IDs, `.env` files, private files, generated reports, screenshots, or local machine paths.
- The workflow fails safely if either required secret is missing.
- Telegram sends only when `telegram_ready` is true.
- A per-run guard prevents duplicate send attempts in the same workflow run.
- The workflow uploads generated reports as artifacts instead of committing them.
- OpenAI API is not used by default in the workflow.

## Output Files

A report run writes these files under `outputs/daily-reports/<date>-live/` locally or uploads the same files as GitHub Actions artifacts:

- `report.json`: structured report data, ranked updates, source notes, metadata, and readiness fields.
- `report.md`: English Markdown report for human review.
- `report.docx`: Word document version of the report.

Generated files under `outputs/` are ignored and must stay untracked.

## Safety Model

AI Signal Brief is built around public-safe, source-backed reporting:

- Source inputs come from an allowlist of public HTTPS sources.
- Claims should remain traceable to source names and URLs.
- Freshness and editorial relevance gates decide whether an item can appear in the Telegram-ready brief.
- Telegram delivery is secret-gated and `telegram_ready`-gated.
- OpenAI API is not used by default; any future model-assisted summarization should require explicit approval and secrets.
- Generated outputs are local artifacts or GitHub Actions artifacts, not committed repo files.
- `python -m ai_signal_brief public-readiness` checks tracked files for public-release risks such as secrets, private paths, and generated outputs.

## Useful Links

- [Daily AI Report workflow](.github/workflows/daily-ai-report.yml)
- [GitHub Actions Daily AI Report runs](https://github.com/LeombE/ai-signal-brief/actions/workflows/daily-ai-report.yml)
- [Live AI report documentation](docs/live-ai-report.md)
- [Security policy](SECURITY.md)
- [Security and secrets guide](docs/security-and-secrets.md)
- [Content license](CONTENT-LICENSE.md)
- [Public readiness checks](docs/public-readiness.md)

## Roadmap

- Verify the first scheduled 05:00 Asia/Kuala_Lumpur Daily AI Report run after it happens.
- Improve source coverage while keeping the public HTTPS allowlist and attribution rules clear.
- Improve editorial ranking quality for model, tooling, research, safety, and product updates.
- Consider production Pages publication only after a reviewed publication workflow is approved.
- Consider OpenAI-assisted summarization only with explicit approval, clear review gates, and GitHub Secrets.

## License

Code is licensed under the MIT License. Original report prose and project-created assets are intended to be licensed under CC BY 4.0, with exclusions documented in [CONTENT-LICENSE.md](CONTENT-LICENSE.md). See [LICENSE](LICENSE) for the code license.
