# Reviewed Report Dry-Run Helper Command Plan

This document plans a future helper command for local dry-runs of manually reviewed canonical reports. It is a design document only. The command is not implemented in this phase.

The current repository remains offline-first. The sample GitHub Pages preview is live at `https://leombe.github.io/ai-signal-brief/`, but it uses sample/example data only. No production daily automation is active.

## Proposed Command Shape

Primary future command:

```powershell
python -m ai_signal_brief dry-run-reviewed-report --date YYYY-MM-DD
```

Explicit-path form:

```powershell
python -m ai_signal_brief dry-run-reviewed-report --date YYYY-MM-DD --report reports-reviewed/YYYY/MM/DD/report.json --run reports-reviewed/YYYY/MM/DD/run.json --sources config/sources.example.json --archive-out outputs/reviewed-dry-run/YYYY/MM/DD --site-out outputs/reviewed-site-dry-run/YYYY/MM/DD --strict
```

Site-skipping form:

```powershell
python -m ai_signal_brief dry-run-reviewed-report --date YYYY-MM-DD --no-site
```

## Proposed Arguments

- `--date YYYY-MM-DD`: required date for the reviewed report candidate.
- `--report reports-reviewed/YYYY/MM/DD/report.json`: optional explicit report path. Defaults from `--date`.
- `--run reports-reviewed/YYYY/MM/DD/run.json`: optional explicit run metadata path. Defaults from `--date`.
- `--sources config/sources.example.json`: optional source registry path. Defaults to the public-safe example registry until a production registry is approved.
- `--archive-out outputs/reviewed-dry-run/YYYY/MM/DD`: optional archive preview output path under ignored output storage.
- `--site-out outputs/reviewed-site-dry-run/YYYY/MM/DD`: optional static site preview output path under ignored output storage.
- `--strict`: planned mode that fails on warnings, incomplete review evidence, or missing optional review fields.
- `--no-site`: planned mode that validates and builds archive output but skips static site generation.

## Planned Local Steps

The helper command should perform only local offline validation and local output generation:

1. Confirm `reports-reviewed/YYYY/MM/DD/report.json` exists.
2. Confirm `reports-reviewed/YYYY/MM/DD/run.json` exists.
3. Confirm `reports-reviewed/YYYY/MM/DD/review.md` exists.
4. Confirm `review.md` appears completed enough for dry-run use.
5. Run `validate-report` on the reviewed report.
6. Run `validate-run` on the reviewed run metadata.
7. Run `validate-sources` on the configured source registry.
8. Run `quality-gate` across report, run, and sources.
9. Build archive preview output under `outputs/`.
10. Build static site preview output under `outputs/`, unless `--no-site` is set.
11. Run `public-readiness`.
12. Print a local dry-run PASS/FAIL summary.

The helper must not deploy anything and must not modify GitHub workflow triggers.

## Equivalent Manual Commands

The future helper should wrap the existing manual dry-run sequence documented in `docs/reviewed-report-dry-run.md`:

```powershell
python -m ai_signal_brief validate-report reports-reviewed/YYYY/MM/DD/report.json
python -m ai_signal_brief validate-run reports-reviewed/YYYY/MM/DD/run.json
python -m ai_signal_brief validate-sources config/sources.example.json
python -m ai_signal_brief quality-gate --report reports-reviewed/YYYY/MM/DD/report.json --run reports-reviewed/YYYY/MM/DD/run.json --sources config/sources.example.json
python -m ai_signal_brief archive-report --report reports-reviewed/YYYY/MM/DD/report.json --run reports-reviewed/YYYY/MM/DD/run.json --sources config/sources.example.json --out outputs/reviewed-dry-run/YYYY/MM/DD
python -m ai_signal_brief build-site --archive outputs/reviewed-dry-run/YYYY/MM/DD --out outputs/reviewed-site-dry-run/YYYY/MM/DD
python -m ai_signal_brief public-readiness
```

## Non-Goals

The planned helper command must not:

- deploy GitHub Pages
- send Telegram messages
- call OpenAI API
- generate images
- create DOCX files
- schedule automation
- migrate historical reports
- copy private source material
- create production deployment workflows
- change Pages workflow triggers
- commit generated `outputs/` files

## Safety Rules

The planned helper must reject or fail when it detects:

- private legacy daily-report paths
- secret-like values
- chat identifier, token, or API key values
- raw Chinese historical report exports copied directly
- DOCX exports used as source material
- HTML exports used as source material
- Telegram exports used as source material
- legacy builder references
- non-English canonical report content
- non-public or unattributable sources
- unresolved claim/source IDs
- missing or incomplete `review.md`
- unsafe output paths outside the repository or outside approved ignored output storage

The planned helper should require English canonical report content, public attributable sources, resolved claim/source IDs, reviewed story status and importance, reviewed run metadata, and completed manual review notes before reporting dry-run success.

## Future Review.md Completion Rules

The command should initially use conservative review checks:

- `review.md` exists beside `report.json` and `run.json`.
- required checklist section exists.
- no obvious unchecked required publication-safety item remains in strict mode.
- review notes include source review and claim review sections.
- review notes include a rollback expectation.

Exact checklist parsing can start simple and become stricter only after a real reviewed report is prepared.

## Future Test Cases

Future implementation should include stdlib tests for:

- successful reviewed report dry-run
- missing `report.json`
- missing `run.json`
- missing `review.md`
- invalid `run.json`
- `quality-gate` failure
- unsafe output path
- private path detected
- secret-like value detected
- raw historical export detected
- unresolved claim/source ID detected
- `--no-site` skips site output
- no production side effects

No production side effects means tests must verify that the command does not deploy Pages, does not send Telegram, does not call OpenAI, does not generate images, does not create DOCX files, does not create scheduled automation, and does not modify workflow triggers.

## Suggested Exit Codes

- `0`: dry-run passed.
- `1`: validation or quality gate failed.
- `2`: input path, output path, or review metadata problem.
- `3`: safety rule violation.

Exit codes can be revised during implementation, but failures must be explicit and must not expose secret values.

## Implementation Boundary

Do not implement this command until a later approved phase. Phase 20 only documents the planned interface, safety rules, local behavior, and future tests.