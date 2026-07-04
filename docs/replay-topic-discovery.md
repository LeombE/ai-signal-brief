# Replay Topic Discovery

Replay topic discovery connects local replay source observations to the existing offline topic candidate pipeline. It is an artifact-only workflow for reviewable topic candidates; it does not fetch live sources or publish reports.

## Status

The command is replay-only and local-file only:

```powershell
python -m ai_signal_brief discover-topics-from-replay --date 2026-06-24 --sources config/topic_sources.live.example.json --replay-dir outputs/replay-valid-fixtures/2026-06-24 --out outputs/topic-candidates-replay/2026-06-24.json --rank
```

The replay directory must contain valid replay fixture JSON files only. The shared `tests/fixtures/fetch_replay/` directory intentionally contains invalid fixtures for failure tests, so passing that mixed directory to the command should fail.

GitHub Actions CI for commit `43d2344 Remove urllib imports from validation helpers` was manually confirmed green in the GitHub UI. The no-urllib safety fix removed `urllib.parse` imports from validation helpers while preserving local HTTPS/source validation. Replay topic discovery remains replay-only, local-fixture-only, unresolved, and manually reviewable.

## Pipeline

The replay pipeline:

1. Validates the topic source registry.
2. Requires disabled live-source registry entries to remain `enabled: false` and `fetch_mode: disabled`.
3. Loads each local replay fixture through the replay-only fetch adapter.
4. Converts the fixture into a normalized source observation.
5. Rejects unknown source IDs, duplicate observation IDs, unsafe values, raw HTML, private paths, and secret-like markers.
6. Converts source observations into topic discovery observations.
7. Generates validated topic candidates under `outputs/`.
8. Optionally runs offline ranking when `--rank` is passed.

Generated candidates use:

- `candidate_status: unresolved`
- `review_required: true`
- `provenance.generation_mode: replay_fixture_observations_only`
- `provenance.live_fetching: false`

This keeps replay-generated topics as manually reviewable candidates only.

## Preserved Observation Fields

Replay-generated topic candidates preserve source observation metadata needed for review:

- `source_id`
- `url`
- `observed_at`
- `published_at`
- `retrieved_at`
- `source_type`
- `raw_signal_type`
- `content_hash`
- `source_confidence`

These fields support source traceability without including raw article bodies, raw HTML, screenshots, private exports, or credentials.

## Safety Rules

Replay topic discovery must not:

- fetch web pages
- add `discover-topics-live`
- enable live registry entries
- modify workflows
- add schedules
- publish reports
- deploy Pages
- send Telegram messages
- call OpenAI APIs
- generate images
- create DOCX files
- commit generated outputs

Output paths must stay under `outputs/`. Generated outputs are local artifacts and should remain ignored by Git.

## Review Boundary

Replay topic candidates are not report claims. They are inputs for future manual review. A topic should not be promoted into a reviewed report until a human checks source URLs, claim scope, timing, deduplication, and unresolved review notes.