# run.json Schema

`run.json` records execution metadata for a report generation run.

## Purpose

Run metadata should make automation auditable without exposing secrets. It records timing, mode, environment, generated artifacts, warnings, errors, linked report identity, and delivery status.

## Top-Level Fields

- `schema_version`: schema version string
- `run_id`: stable run identifier
- `started_at`: timezone-aware start timestamp
- `ended_at`: optional timezone-aware end timestamp
- `timezone`: IANA timezone
- `status`: `success`, `partial`, `failed`, or `dry_run`
- `mode`: `manual`, `scheduled`, or `test`
- `environment`: `local`, `github_actions`, or `other`
- `report_id`: source report identifier
- `report_date`: source report date in `YYYY-MM-DD` format
- `artifacts`: generated artifact metadata
- `delivery`: delivery channel status
- `warnings`: non-fatal warnings
- `errors`: fatal or blocking errors

## Artifact Fields

Each artifact contains:

- `kind`: artifact type, such as `markdown` or `telegram_preview`
- `path`: relative artifact path
- `sha256`: optional checksum

## Secret Rule

Run metadata must never contain API keys, Telegram tokens, chat IDs, private env content, local machine paths, or raw external service responses containing sensitive data.

## Validation Command

```powershell
python -m ai_signal_brief validate-run examples/run.example.json
```

The validator checks required run fields, ISO-8601 timestamps with timezones, allowed status/mode/environment values, linked report fields, artifact shape, delivery shape, list fields, and secret-like values.