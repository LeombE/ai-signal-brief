# Reviewed Report Dry-Run Workflow

This document defines a safe local dry-run procedure for a future manually reviewed canonical report. The helper command is available as `python -m ai_signal_brief dry-run-reviewed-report`; design notes remain in `docs/reviewed-report-dry-run-command-plan.md`.

It does not create a real report, migrate historical reports, deploy GitHub Pages, send Telegram messages, call OpenAI, generate images, create DOCX files, or schedule automation.

## Required Future Folder Layout

A future reviewed report candidate should use this layout only after manual preparation and review:

```text
reports-reviewed/YYYY/MM/DD/report.json
reports-reviewed/YYYY/MM/DD/run.json
reports-reviewed/YYYY/MM/DD/review.md
```

Do not create dated folders until there is a real reviewed report candidate. Do not use empty dated folders as placeholders.

## Preparation Steps

1. Copy the placeholder templates from `examples/reviewed-report-template/` into a future dated folder.
2. Rename the copied files to `report.json`, `run.json`, and `review.md`.
3. Replace all placeholder content with sanitized English reviewed content.
4. Confirm the report is English-only and canonical.
5. Confirm every source is public and attributable.
6. Confirm every claim references valid source IDs.
7. Confirm no private paths, secrets, chat ID values, tokens, API keys, screenshots, DOCX exports, HTML exports, Telegram exports, private source files, raw migration artifacts, or legacy builder scripts are present.

Raw Chinese historical reports must not be copied directly. Private legacy daily-report files, screenshots, Telegram exports, DOCX/HTML outputs, and legacy builders must not be copied into the public repository.

## Local Validation Sequence

Replace `YYYY/MM/DD` with the future reviewed report date.

Validate the reviewed report:

```powershell
python -m ai_signal_brief validate-report reports-reviewed/YYYY/MM/DD/report.json
```

Validate the reviewed run metadata:

```powershell
python -m ai_signal_brief validate-run reports-reviewed/YYYY/MM/DD/run.json
```

Validate the source registry:

```powershell
python -m ai_signal_brief validate-sources config/sources.example.json
```

Run the cross-file quality gate:

```powershell
python -m ai_signal_brief quality-gate --report reports-reviewed/YYYY/MM/DD/report.json --run reports-reviewed/YYYY/MM/DD/run.json --sources config/sources.example.json
```

Build a local archive preview under ignored output storage:

```powershell
python -m ai_signal_brief archive-report --report reports-reviewed/YYYY/MM/DD/report.json --run reports-reviewed/YYYY/MM/DD/run.json --sources config/sources.example.json --out outputs/reviewed-dry-run
```

Build a local static site preview under ignored output storage:

```powershell
python -m ai_signal_brief build-site --archive outputs/reviewed-dry-run --out outputs/reviewed-site-dry-run
```

Run repository safety checks:

```powershell
python -m ai_signal_brief public-readiness
python -m unittest discover -s tests
```

## Output Rules

`outputs/` is ignored and must not be committed. Dry-run archive and site output are local inspection artifacts only.

The dry-run procedure:

- does not deploy GitHub Pages
- does not send Telegram messages
- does not call OpenAI API
- does not generate images
- does not create DOCX files
- does not schedule automation
- does not publish production data
- does not change workflow triggers

## Human Review Checklist

Use this checklist before considering any production Pages workflow:

- [ ] English only.
- [ ] Sources are public and attributable.
- [ ] Claim/source IDs resolve.
- [ ] Story status reviewed.
- [ ] Importance score reviewed.
- [ ] No private paths.
- [ ] No secrets.
- [ ] No chat ID, token, or API key values.
- [ ] No old raw migration artifacts.
- [ ] No screenshots, DOCX exports, HTML exports, Telegram exports, or legacy builder scripts.
- [ ] `validate-report` passes.
- [ ] `validate-run` passes.
- [ ] `validate-sources` passes.
- [ ] `quality-gate` passes.
- [ ] Generated archive output reviewed.
- [ ] Generated static page reviewed.
- [ ] Rollback expectation is known.

## Manual Inspection Requirements

After building `outputs/reviewed-site-dry-run/`, inspect the generated report page locally before considering publication.

Confirm:

- title, date, generated timestamp, and timezone are correct
- top story summary is accurate
- story order and importance are correct
- claim/source references are visible and correct
- complete source list is present
- provenance note is public-safe
- no private or unreviewed material appears in the HTML

## Publication Boundary

A successful dry-run is not approval to publish. It only proves that the reviewed report candidate can pass local validation and render into local preview output.

Production Pages must remain manual-only until a later approved phase defines a production workflow. Telegram delivery must remain disconnected until a verified Pages URL exists for a manually reviewed report. OpenAI Image API usage must remain disabled until a dedicated GitHub Secret and a separate reviewed workflow exist.