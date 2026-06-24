# run.json Schema

`run.json` records execution metadata for a report generation run.

## Purpose

Run metadata should make automation auditable without exposing secrets. It records timing, mode, environment, generated artifacts, warnings, errors, and delivery status.

## Top-Level Fields

- `schema_version`: schema version string
- `run_id`: stable run identifier
- `started_at`: timezone-aware start timestamp
- `ended_at`: optional timezone-aware end timestamp
- `timezone`: IANA timezone
- `status`: `success`, `partial`, `failed`, or `dry_run`
- `mode`: `manual`, `scheduled`, or `test`
- `environment`: `local`, `github_actions`, or `other`
- `artifacts`: generated artifact metadata
- `delivery`: delivery channel status
- `warnings`: non-fatal warnings
- `errors`: fatal or blocking errors

## Secret Rule

Run metadata must never contain API keys, Telegram tokens, chat IDs, private env content, or raw external service responses containing sensitive data.