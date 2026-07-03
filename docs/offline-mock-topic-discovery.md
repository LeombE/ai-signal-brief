# Offline Mock Topic Discovery

Offline mock topic discovery converts local placeholder observations into validated topic candidate JSON. It is a local test and development workflow only.

It does not fetch live sources, scrape websites, call external APIs, send Telegram messages, generate images, create DOCX files, create workflows, schedule automation, publish Pages, or promote a topic candidate into a reviewed report.

## Command

```powershell
python -m ai_signal_brief discover-topics --date 2026-06-24 --sources config/topic_sources.example.json --mock-observations tests/fixtures/topic_observations.valid.json --out outputs/topic-candidates/2026-06-24.json --rank
```

Arguments:

- `--date YYYY-MM-DD`: deterministic scan date used for `scan_id`, `scan_date`, and `generated_at`.
- `--sources`: topic source registry path. The registry is validated before discovery.
- `--mock-observations`: local placeholder observation fixture.
- `--out`: generated topic candidate JSON path under `outputs/`.
- `--rank`: optionally run offline ranking after generated candidate validation.
- `--timezone`: IANA timezone used for deterministic `generated_at`; default is `Asia/Kuala_Lumpur`.
- `--quiet-ok`: allow an empty mock observation fixture to generate a quiet-day candidate.

## Mock Observation Fixtures

Current fixtures:

- `tests/fixtures/topic_observations.valid.json`
- `tests/fixtures/topic_observations.quiet_day.json`
- `tests/fixtures/topic_observations.invalid.json`
- `tests/fixtures/topic_observations.private_path.json`
- `tests/fixtures/topic_observations.secret_like.json`

The valid fixture contains placeholder observations only. It does not contain real current news claims, credentials, private local paths, screenshots, old exports, or private migration content.

## Pipeline

The offline pipeline:

1. Validate the scan date and timezone.
2. Validate `config/topic_sources.example.json`.
3. Load and safety-check the local mock observation fixture.
4. Convert observations into topic candidates with deterministic topic IDs.
5. Preserve `observed_at`, `published_at`, and `retrieved_at` separately.
6. Build source observations, topics, dedup groups, and unresolved review items.
7. Write candidate JSON only under `outputs/`.
8. Run `validate-topics` on the generated output.
9. Optionally run `rank-topics` when `--rank` is passed.

## Safety Rules

- Generated output remains under `outputs/` and is not committed.
- Mock observations must be public-safe placeholders.
- Empty observation sets require `--quiet-ok`.
- Secret-like values and private local paths are rejected before generation succeeds.
- Live discovery remains unimplemented and requires separate approval.

## Manual GitHub Actions Preview

A manual-only preview workflow is defined in `.github/workflows/topic-scan-preview.yml`.

It uses `workflow_dispatch` only and runs the same offline mock discovery path against `tests/fixtures/topic_observations.valid.json`. The generated topic candidates are written under `outputs/topic-candidates/${{ github.run_id }}/topic-candidates.json`, validated, ranked with `--explain`, and uploaded as the `topic-candidates-preview` artifact with `retention-days: 7`.

The workflow does not fetch live sources, publish reports, deploy Pages, send Telegram messages, call OpenAI APIs, generate images, create DOCX files, commit generated output, or schedule anything.

Schedule-based topic scans should be considered only in a later approved phase after manual preview artifacts have been reviewed.
