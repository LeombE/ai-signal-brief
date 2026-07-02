# Offline Archive Builder

Phase 7 adds a stdlib-only archive builder for creating a public-safe, date-based report archive from validated canonical files.

The archive builder is offline. It does not fetch sources, scrape websites, call model APIs, generate images, send Telegram messages, create DOCX files, create GitHub Actions, or publish outputs.

## Command

```powershell
python -m ai_signal_brief archive-report --report examples/report.example.json --run examples/run.example.json --sources config/sources.example.json --out outputs/archive-example
```

## Quality Gate Requirement

The archive builder runs the offline quality gate before writing archive output. If the report, run metadata, or source registry fails validation or cross-file checks, archive creation stops before writing files.

## Canonical Layout

For a report dated `YYYY-MM-DD`, the archive builder writes:

```text
outputs/archive-example/YYYY/MM/DD/report.json
outputs/archive-example/YYYY/MM/DD/run.json
outputs/archive-example/YYYY/MM/DD/index.md
outputs/archive-example/index.json
```

`outputs/` is generated output and should remain ignored by Git.

## Archive Index

`index.json` contains:

- `schema_version`
- `reports`

Each report entry contains:

- `schema_version`
- `report_id`
- `report_date`
- `generated_at`
- `title`
- path references for `report.json`, `run.json`, and `index.md`

Reports are sorted by `report_date` descending, then `generated_at` descending.

## Duplicate Rule

The builder rejects duplicate `report_id` values. Phase 7 does not implement an overwrite flag.

## Safety Rules

The builder rejects unsafe output paths, paths outside the repository, private source references, secret-like values, local env references, legacy private builder references, and mistaken prompt references.

Generated archive files should contain only relative archive paths, never local absolute machine paths.