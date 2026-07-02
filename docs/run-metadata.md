# Offline Run Metadata

Phase 5 adds an offline command that creates a `run.json`-style metadata record from a validated canonical report.

The command does not fetch sources, call model APIs, send Telegram messages, create DOCX files, or publish outputs. It writes a local JSON file only.

## Command

```powershell
python -m ai_signal_brief create-run-record --report examples/report.example.json --out outputs/run.example.generated.json
```

Optional artifacts can be attached with repeated `--artifact` arguments:

```powershell
python -m ai_signal_brief create-run-record `
  --report examples/report.example.json `
  --out outputs/run.example.generated.json `
  --artifact markdown=outputs/report.example.md `
  --artifact telegram_preview=outputs/telegram.example.txt `
  --started-at 2026-06-24T04:00:00+08:00 `
  --ended-at 2026-06-24T04:01:00+08:00 `
  --timezone Asia/Kuala_Lumpur
```

## Generated Fields

The generated record includes:

- `schema_version`
- `run_id`
- `started_at`
- `ended_at`
- `timezone`
- `status`
- `mode`
- `environment`
- `report_id`
- `report_date`
- `artifacts`
- `delivery.telegram.enabled = false`
- `delivery.telegram.status = skipped`
- `warnings`
- `errors`

## Deterministic Tests

Use fixed `--started-at`, `--ended-at`, and `--timezone` values in tests. If timestamps are omitted, the command uses the current local time for the configured timezone.

## Safety Rules

Run metadata generation rejects invalid report JSON before writing an output file.

Artifact paths must be relative paths. Absolute paths, URLs, parent-directory segments, Windows drive paths, and secret-like values are rejected.

Generated run metadata must not contain Telegram tokens, OpenAI keys, chat IDs, local env values, private machine paths, or private migration references.

## Validation

Validate generated metadata with:

```powershell
python -m ai_signal_brief validate-run outputs/run.example.generated.json
```