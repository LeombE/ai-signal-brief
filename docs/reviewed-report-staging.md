# Reviewed Report Staging

This document defines the future staging area for manually reviewed, sanitized English canonical reports. It does not add real report data, migrate historical reports, enable production Pages publishing, connect Telegram delivery, configure OpenAI, generate images, or create DOCX outputs.

## Purpose

The staging area gives the project a clear public-safe place for future reviewed canonical reports before they are considered for production archive or Pages publication.

The folder is for manually reviewed English canonical reports only. Raw historical reports must not be copied directly. Raw non-English historical drafts must first be converted into sanitized English canonical `report.json` and `run.json` records, then reviewed before any public use.

## Future Layout

```text
reports-reviewed/YYYY/MM/DD/report.json
reports-reviewed/YYYY/MM/DD/run.json
reports-reviewed/YYYY/MM/DD/review.md
```

Required files for each future report date:

- `report.json`: sanitized English canonical report data
- `run.json`: reviewed run metadata for the report
- `review.md`: manual review notes and checklist evidence

Do not create date folders until there is a reviewed report candidate. Empty date folders should not be used as placeholders. Use `examples/reviewed-report-template/` for placeholder files.

## Material That Must Not Be Copied

Do not copy any of the following into `reports-reviewed/`:

- raw historical reports
- raw non-English historical drafts
- private source files
- screenshots or private attachments
- DOCX files
- HTML exports
- Telegram exports
- old builder scripts
- local env files
- cache files
- generated unreviewed outputs
- private legacy daily-report source paths
- API keys, Telegram credentials, chat identifiers, or any secret values

## Validation Requirements

Every future reviewed report must satisfy these checks before archive or site generation:

```powershell
python -m ai_signal_brief validate-report reports-reviewed/YYYY/MM/DD/report.json
python -m ai_signal_brief validate-run reports-reviewed/YYYY/MM/DD/run.json
python -m ai_signal_brief validate-sources config/sources.example.json
python -m ai_signal_brief quality-gate --report reports-reviewed/YYYY/MM/DD/report.json --run reports-reviewed/YYYY/MM/DD/run.json --sources config/sources.example.json
python -m ai_signal_brief public-readiness
python -m unittest discover -s tests
```

The report must pass `validate-report`. The run metadata must pass `validate-run`. The report, run, and source registry must pass `quality-gate` before archive or static-site generation.

## Manual Review Requirements

Each future report needs manual review before publication:

- English language confirmed
- no private file paths
- no secrets
- no raw migration artifacts
- sources are public and attributable
- source URLs are inspectable public URLs
- claim/source IDs resolve correctly
- claim support levels are reviewed
- story status and importance are reviewed
- run metadata is reviewed
- artifact paths are relative and safe
- quality gate passes
- generated static page is reviewed
- rollback plan is known

## Source And Claim Review

Source review must confirm that every material claim maps to one or more source IDs. Source metadata should include title, publisher, URL, source type, and timestamps when available.

Claim review should confirm that:

- source IDs exist in the report source list
- unsupported claims are removed or marked appropriately
- partially supported claims are not overstated
- story importance is justified by reader impact
- follow-up stories are not duplicates of earlier reports

## Pages And Delivery Boundaries

Production Pages publishing must not happen before manual review. A reviewed report should first be validated locally, archived locally, rendered into a static site locally, and inspected before any production Pages workflow is considered.

Telegram delivery must remain disconnected until the Pages URL for the reviewed report is verified.

OpenAI Image API usage must remain disabled until a dedicated GitHub Secret is configured and a separate image workflow is approved.

## Future Workflow Design

Suggested future process, not implemented in this phase:

1. Manually prepare one reviewed `report.json`.
2. Manually prepare matching `run.json`.
3. Write `review.md` with checklist evidence.
4. Validate locally.
5. Run the quality gate locally.
6. Run `archive-report` locally.
7. Run `build-site` locally.
8. Inspect the generated Pages output locally.
9. Review rollback expectations.
10. Only then consider a production Pages workflow.

## Publication Boundary

`reports-reviewed/` is a staging area, not an automatic publication trigger. Adding files here in a future phase must not by itself publish Pages, send Telegram messages, call OpenAI, generate images, create DOCX files, or start scheduled automation.