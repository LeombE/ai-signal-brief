# Production Pages Readiness Plan

This plan defines the gate for moving from the live sample Pages preview to a production GitHub Pages publication workflow.

Current sample preview:

- Repository: `https://github.com/LeombE/ai-signal-brief`
- Sample Pages URL: `https://leombe.github.io/ai-signal-brief/`
- Trigger: manual `workflow_dispatch` only
- Data: repository example JSON files only
- Status: demo preview, not production daily automation

## Sample Preview Versus Production Pages

Sample Pages preview proves that the offline archive builder, static site builder, Pages artifact upload, and Pages deployment path work with public-safe example data.

Production Pages would publish reviewed AI Signal Brief reports for real readers. It must use sanitized English canonical `report.json` and `run.json` records, reviewed source metadata, reviewed archive output, and reviewed static pages. Production Pages must not publish raw migration material, private local outputs, unreviewed historical files, secrets, local paths, or generated artifacts that bypass validation.

## Production Data Requirements

Production Pages requires all report inputs to be canonical and reviewable:

- `report.json` must pass `validate-report`.
- `run.json` must pass `validate-run`.
- source registry data must pass `validate-sources`.
- report, run, and source registry files must pass `quality-gate` together.
- each report must be English-first and sanitized for public release.
- every material claim must map to source IDs.
- every source must include enough attribution for a reader to inspect it.
- generated archive output must be reviewed before publication.
- generated static pages must be reviewed before publication.

## Manual Review Gates

Do not publish real reports to Pages until these checks are completed manually:

1. Confirm CI is green on `main`.
2. Run `python -m ai_signal_brief public-readiness` and confirm PASS.
3. Run `python -m unittest discover -s tests` and confirm OK.
4. Review at least one sanitized English `report.json`.
5. Review source titles, publishers, URLs, source types, and published timestamps.
6. Review claim-to-source mappings.
7. Review `run.json` metadata, artifact paths, warnings, and errors.
8. Build and review archive output.
9. Build and review generated static pages.
10. Verify the GitHub Pages URL after manual deployment.
11. Confirm rollback steps are documented before the first production run.

## Historical Migration Requirements

Historical reports must be migrated privately before any public publication.

Migration requirements:

- do not publish raw historical reports directly
- do not publish raw non-English legacy drafts directly
- do not copy private source files into the public repo
- convert reviewed historical material into sanitized English canonical records
- preserve source/citation traceability in canonical JSON
- remove private paths, local filenames, screenshots, credentials, and unreviewed assets
- review each migrated report before it is added to a production archive

## Source And Citation Quality Requirements

Production Pages should preserve the official-source-first policy:

- prefer official vendor announcements, docs, changelogs, research papers, repositories, and regulatory sources
- use news sources for context when primary sources are unavailable or insufficient
- avoid unsupported claims
- mark unverified or partially supported claims explicitly
- keep source URLs public and inspectable
- avoid private URLs, local paths, screenshots, and copied third-party assets

## Quality Gate Requirements

Before production Pages publication, the pipeline must pass:

```powershell
python -m ai_signal_brief validate-report <reviewed-report.json>
python -m ai_signal_brief validate-run <reviewed-run.json>
python -m ai_signal_brief validate-sources config/sources.example.json
python -m ai_signal_brief quality-gate --report <reviewed-report.json> --run <reviewed-run.json> --sources config/sources.example.json
python -m ai_signal_brief public-readiness
python -m unittest discover -s tests
```

For production inputs, replace example paths with reviewed canonical files. Do not point the workflow at private source folders or unreviewed migration folders.

## Public Readiness And No-Secrets Requirements

Production Pages must pass the public readiness audit and must not contain:

- API keys
- Telegram credentials
- OpenAI credentials
- local env values
- private legacy daily-report source paths
- private migration material
- local machine paths
- private screenshots or attachments
- raw generated outputs that were not reviewed
- unreviewed historical files

## Telegram And OpenAI Boundaries

Telegram delivery must remain disconnected until a Pages URL from a manually reviewed production report is verified.

OpenAI Image API usage must remain disabled until a dedicated GitHub Secret is configured and a separate image-generation workflow is reviewed. Image generation must not be added as part of production Pages readiness.

Daily scheduling must remain disabled until at least one manually reviewed report has been published successfully and the Pages URL has been verified.

## Future Production Workflow Design

Suggested future workflow design, not implemented in this phase:

1. Start with `workflow_dispatch` only.
2. Do not add a schedule initially.
3. Read reviewed canonical report and run records from a public-safe location.
4. Validate report, run, and sources.
5. Run the quality gate.
6. Build the archive from reviewed canonical reports.
7. Build the static site.
8. Upload the Pages artifact.
9. Deploy GitHub Pages.
10. Verify the Pages URL.
11. Only after a verified Pages URL exists, consider future Telegram delivery.
12. Add scheduling only after repeated successful manual production runs.

## Production Readiness Checklist

- [ ] CI is green.
- [ ] `public-readiness` passes.
- [ ] Pages sample preview works.
- [ ] At least one sanitized English `report.json` is reviewed.
- [ ] Report sources are reviewed.
- [ ] Run metadata is reviewed.
- [ ] Archive output is reviewed.
- [ ] Generated static page is reviewed.
- [ ] GitHub Pages URL is verified.
- [ ] No private files are copied.
- [ ] No secrets are committed.
- [ ] No raw historical non-English reports are published directly.
- [ ] Rollback plan is documented.

## Rollback Plan Requirement

Before production Pages is enabled, document how to roll back to the last known good Pages artifact or disable the production workflow. A minimum rollback plan should include the last good commit, the Pages workflow run URL, the affected report IDs, and the command or GitHub UI action needed to redeploy or disable publication.