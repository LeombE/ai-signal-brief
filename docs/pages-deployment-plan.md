# Pages Deployment Plan

GitHub Pages sample preview is live at `https://leombe.github.io/ai-signal-brief/`.

The Pages Preview workflow lives at `.github/workflows/pages-preview.yml`. It is triggered by `workflow_dispatch` only and publishes a sample static site generated from the repository's existing example JSON files.

This is a demo preview workflow, not production daily automation.

## What Pages Preview Publishes

The workflow builds the same offline sample artifacts that can be generated locally:

```powershell
python -m ai_signal_brief archive-report --report examples/report.example.json --run examples/run.example.json --sources config/sources.example.json --out outputs/archive-example
python -m ai_signal_brief build-site --archive outputs/archive-example --out outputs/site-example
```

It uploads `outputs/site-example` as a GitHub Pages artifact and deploys that artifact with official GitHub Pages actions.

The live preview site contains sample/example data only. It does not publish historical reports, private migration material, Telegram output, generated images, DOCX files, live news results, or production daily reports.

## Current Live Status

- Public repository: `https://github.com/LeombE/ai-signal-brief`
- Pages sample preview: `https://leombe.github.io/ai-signal-brief/`
- Pages Preview workflow has passed.
- Latest CI is passing.
- Pages is sample/demo only.
- Pages is not production daily automation yet.
- Historical reports are not migrated yet.
- Telegram delivery is not connected.
- OpenAI Image API is not configured.
- Image generation and DOCX generation are not active.

## Workflow Shape

The Pages Preview workflow:

1. checks out the repository
2. sets up Python
3. sets `PYTHONPATH=src`
4. runs `python -m ai_signal_brief public-readiness`
5. runs `python -m unittest discover -s tests`
6. generates the sample archive
7. generates the sample static site
8. re-runs public readiness against tracked files
9. uploads the generated sample site as a Pages artifact
10. deploys through official GitHub Pages actions

Official Pages actions used:

- `actions/configure-pages`
- `actions/upload-pages-artifact`
- `actions/deploy-pages`

## Manual Operation In GitHub UI

Use the workflow manually only:

1. Open `https://github.com/LeombE/ai-signal-brief`.
2. Go to `Actions`.
3. Select `Pages Preview`.
4. Choose `Run workflow` on `main`.
5. Wait for the workflow to complete.
6. Open `https://leombe.github.io/ai-signal-brief/` or the Pages URL shown in the completed deployment.

Do not add a push trigger or schedule until production publication rules are approved separately.


## Production Readiness

Production Pages is not active yet. Before publishing real reports, use `docs/production-pages-readiness.md` to verify production data requirements, manual review gates, historical migration rules, source/citation quality, quality gates, public readiness, no-secrets boundaries, and rollback planning.

Production Pages must start as manual `workflow_dispatch` only. Do not add a schedule until at least one manually reviewed report has been published successfully and the Pages URL has been verified.
## Current Non-Goals

Phase 15 does not:

- change workflow triggers
- run the Pages workflow from Codex
- add a push trigger
- add a scheduled trigger
- publish historical reports
- migrate historical reports
- configure scheduled daily runs
- configure Telegram delivery
- configure OpenAI Image API usage
- generate images
- generate DOCX files
- commit generated outputs

## Safety Rules For Pages Work

Pages output should contain only public-safe generated HTML, CSS, JSON, Markdown-derived report content, and reviewed assets. It must not include secrets, local paths, private migration material, private generated reports, unreviewed historical content, Telegram credentials, OpenAI keys, or chat identifiers.

The preview workflow must stay sample-only until a later approved phase defines production publication inputs, review gates, and retention policy.