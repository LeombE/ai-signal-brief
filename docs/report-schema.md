# report.json Schema

`report.json` is the canonical public report data model.

## Purpose

The report file stores reader-facing AI signal analysis with explicit source and claim mapping. It should be suitable for generating Markdown, HTML, website pages, Telegram summaries, and other output formats.

## Top-Level Fields

- `schema_version`: schema version string
- `report_id`: stable report identifier
- `report_date`: report date in `YYYY-MM-DD`
- `generated_at`: timezone-aware timestamp
- `timezone`: IANA timezone
- `language`: report language, default `en`
- `title`: reader-facing report title
- `summary`: high-level story ranking and brief summary
- `stories`: ranked story records
- `sources`: source records referenced by stories and claims
- `assets`: generated or attached public assets
- `provenance`: generation and review metadata

## Story Records

Stories are ranked by importance and must include:

- stable ID
- rank
- title
- status
- importance score and rationale
- companies, models, and regions
- claims
- source IDs
- analysis

## Claim Records

Claims must be mapped to one or more source IDs and marked with verification status and confidence.

## Source Records

Sources should prefer official and primary material. News and social sources are allowed when clearly attributed and used appropriately.