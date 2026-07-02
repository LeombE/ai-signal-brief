# Offline Quality Gates

Phase 6 adds a stdlib-only quality gate command for checking a canonical report, run metadata record, and source registry together.

The command is offline. It does not fetch sources, scrape websites, call model APIs, send Telegram messages, generate images, create DOCX files, create GitHub Actions, or publish outputs.

## Command

```powershell
python -m ai_signal_brief quality-gate --report examples/report.example.json --run examples/run.example.json --sources config/sources.example.json
```

## Checks

The quality gate verifies:

- report JSON passes report validation
- run JSON passes run validation
- source registry JSON passes source validation
- run `report_id` and `report_date` match the report when present
- story and claim source references point to report sources
- report source types are allowed by the source registry
- run artifact paths are relative, safe, and stay inside the repository
- report, run, and source registry data contain no secret-like values
- report, run, and source registry data contain no private local paths
- report, run, and source registry data contain no mistaken prompt references
- report, run, and source registry data contain no legacy private builder references

## Output Contract

On success:

```text
Quality gate PASS
```

On failure:

```text
Quality gate FAIL
Failed checks:
- check_name
```

The command prints failed check names only. It must not print secret values or matched private strings.

## Exit Codes

- `0`: all checks passed
- non-zero: one or more checks failed

## Testing Policy

Invalid fixtures under `tests/fixtures/` intentionally cover mismatch, unsafe artifact paths, secret-like values, disallowed source types, and mistaken prompt references. These fixtures are for validation tests only and are not production report content.