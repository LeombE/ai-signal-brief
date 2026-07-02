# Pages Deployment Plan

GitHub Pages is not enabled yet.

Phase 13 adds a manual Pages Preview workflow at `.github/workflows/pages-preview.yml`. The workflow is triggered by `workflow_dispatch` only and publishes a sample static site generated from the repository's existing example JSON files.

This is a demo preview workflow, not production daily automation.

## What Pages Preview Publishes

The workflow builds the same offline sample artifacts that can be generated locally:

```powershell
python -m ai_signal_brief archive-report --report examples/report.example.json --run examples/run.example.json --sources config/sources.example.json --out outputs/archive-example
python -m ai_signal_brief build-site --archive outputs/archive-example --out outputs/site-example
```

It uploads `outputs/site-example` as a GitHub Pages artifact and deploys that artifact with official GitHub Pages actions.

The preview site contains sample data only. It does not publish historical reports, private migration material, Telegram output, generated images, DOCX files, or live news results.

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

## Manual Setup In GitHub UI

Before or during first use, configure GitHub Pages in the repository UI:

1. Open `https://github.com/LeombE/ai-signal-brief`.
2. Go to `Settings`.
3. Open `Pages`.
4. Set `Build and deployment` source to `GitHub Actions`.
5. Save the setting if GitHub asks for confirmation.
6. Go to `Actions`.
7. Select `Pages Preview`.
8. Choose `Run workflow` on `main`.
9. Wait for the workflow to complete.
10. Open the Pages URL shown in the completed deployment.

Do not add a push trigger or schedule until production publication rules are approved separately.

## Current Non-Goals

Phase 13 does not:

- enable GitHub Pages from Codex
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