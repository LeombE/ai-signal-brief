# Reviewed Reports Staging Area

This directory is reserved for future manually reviewed, sanitized English canonical reports.

No real report data is stored here yet.

## Future Layout

```text
reports-reviewed/YYYY/MM/DD/report.json
reports-reviewed/YYYY/MM/DD/run.json
reports-reviewed/YYYY/MM/DD/review.md
```

## Rules

- Store only manually reviewed English canonical reports.
- Do not copy raw historical reports directly.
- Do not copy private source files, screenshots, DOCX files, HTML exports, Telegram exports, or old builder scripts.
- Do not store secrets, API keys, Telegram credentials, chat identifiers, local env values, or private local paths.
- Every `report.json` must pass `validate-report`.
- Every `run.json` must pass `validate-run`.
- Every report/run/source set must pass `quality-gate` before archive or site generation.
- Sources and claim/source mappings must be manually reviewed before publication.
- Production Pages publishing must wait for manual review and generated static page inspection.
- Telegram delivery must wait until the Pages URL for the reviewed report is verified.
- OpenAI Image API usage must wait until a dedicated GitHub Secret is configured and a separate workflow is approved.

## Manual Review Checklist

Use this checklist for each future report folder:

- [ ] English language confirmed.
- [ ] No private file paths.
- [ ] No secrets.
- [ ] No raw migration artifacts.
- [ ] Sources are public and attributable.
- [ ] Claim/source IDs resolve correctly.
- [ ] Story status and importance reviewed.
- [ ] Run metadata reviewed.
- [ ] Quality gate passes.
- [ ] Generated static page reviewed.
- [ ] Rollback plan known.