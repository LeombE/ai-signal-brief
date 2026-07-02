# Reviewed Report Manual Review Template

This file is a placeholder review checklist for a future manually reviewed English canonical report. It is not a real report review.

Target future layout:

```text
reports-reviewed/YYYY/MM/DD/report.json
reports-reviewed/YYYY/MM/DD/run.json
reports-reviewed/YYYY/MM/DD/review.md
```

## Report Identity

- Report date: `YYYY-MM-DD`
- Report ID: `replace-with-reviewed-report-id`
- Reviewer: `replace-with-reviewer-name-or-handle`
- Review date: `YYYY-MM-DD`
- Pages preview URL after generation: `replace-after-local-or-manual-preview`

## Manual Review Checklist

- [ ] English language confirmed.
- [ ] No private file paths.
- [ ] No secrets.
- [ ] No raw migration artifacts.
- [ ] No screenshots, DOCX files, HTML exports, Telegram exports, or old builder content.
- [ ] Sources are public and attributable.
- [ ] Source URLs are inspectable public URLs.
- [ ] Claim/source IDs resolve correctly.
- [ ] Story status values are reviewed.
- [ ] Story importance scores and rationales are reviewed.
- [ ] Run metadata is reviewed.
- [ ] Artifact paths are relative and safe.
- [ ] `validate-report` passes.
- [ ] `validate-run` passes.
- [ ] `quality-gate` passes.
- [ ] Generated archive output is reviewed.
- [ ] Generated static page is reviewed.
- [ ] GitHub Pages URL is verified before delivery.
- [ ] Rollback plan is known.

## Source Review Notes

Record source-level review notes here. Confirm source title, publisher, URL, source type, publication timestamp, retrieval timestamp, and why the source is acceptable.

## Claim Review Notes

Record claim-level review notes here. Confirm each claim is supported, partially supported, or removed before publication.

## Publication Decision

- [ ] Not ready for publication.
- [ ] Ready for local archive/site generation only.
- [ ] Ready for manual production Pages consideration.

Decision notes:

```text
Replace this block with review notes before using this file for a real report.
```