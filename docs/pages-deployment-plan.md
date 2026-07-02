# Pages Deployment Plan

GitHub Pages is not enabled in Phase 10.

The project can already build a static site locally from an offline archive:

```powershell
python -m ai_signal_brief archive-report --report examples/report.example.json --run examples/run.example.json --sources config/sources.example.json --out outputs/archive-example
python -m ai_signal_brief build-site --archive outputs/archive-example --out outputs/site-example
```

## Future Deployment Shape

A later phase may add a Pages workflow that:

1. validates report, run, and source registry inputs
2. runs the quality gate
3. builds an archive
4. builds a static site
5. uploads the generated site as a Pages artifact
6. deploys only after public readiness passes

## Current Non-Goals

Phase 10 does not:

- enable GitHub Pages
- add a deployment workflow
- publish generated site files
- migrate historical reports
- configure scheduled runs
- configure Telegram delivery
- configure OpenAI Image API usage

## Safety Rules For Future Pages Work

Future Pages output should contain only public-safe generated HTML, CSS, JSON, Markdown-derived report content, and reviewed assets. It must not include secrets, local paths, private migration material, private generated reports, or unreviewed historical content.
