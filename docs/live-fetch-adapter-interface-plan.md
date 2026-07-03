# Live Fetch Adapter Interface Plan

## Status

This document is a planning artifact only. It does not implement a fetch adapter, live fetching, workflow changes, scheduling, external API calls, Telegram delivery, OpenAI API usage, image generation, DOCX generation, production Pages deployment, or report publication.

The current project remains offline-first. The disabled live source registry example at `config/topic_sources.live.example.json` validates offline, and every live source entry remains disabled by default.

## Future Adapter Objective

A future live fetch adapter should provide a narrow, auditable boundary between approved public source registry entries and reviewable source observation artifacts. The adapter should collect bounded metadata only, preserve attribution, classify errors safely, and produce artifacts that can be inspected before any topic candidate is promoted.

The adapter must not create canonical reports, publish Pages, send Telegram messages, call model APIs, generate images, create DOCX files, or modify GitHub workflows by itself.

## Boundary Definitions

Live fetch:

- would request or read approved public HTTPS source metadata in a future implementation phase
- would require explicit source registry approval and conservative limits
- would produce source observations and safe error records only
- would remain manual and artifact-only for initial dry runs

Replay fetch:

- uses committed safe fixture files only
- performs no network access
- exercises parser, validation, error classification, and candidate conversion paths
- is the required unit-test and CI mode before any network-capable implementation

Mock observation:

- uses hand-authored placeholder observation JSON fixtures
- is already used by offline mock topic discovery
- does not emulate HTTP behavior, cache behavior, response headers, redirects, or rate limits

Reviewed report publication:

- starts only after a human reviews sources, claims, ranking, deduplication, wording, and generated pages
- uses manually prepared English canonical `report.json` and `run.json`
- is separate from source observation and topic discovery

## Adapter Input Contract

A future adapter invocation should accept a validated source entry plus run-level policy:

- `source_id`: stable source ID from `config/topic_sources.live.example.json`
- `url`: public HTTPS URL from the registry only
- `source_type`: report-compatible source type
- `category_id`: topic source category
- `fetch_mode`: one of the approved adapter modes
- `enabled`: must remain `false` until a later explicit approval enables a narrow live dry run
- `manual_review_required`: must be `true`
- `attribution_required`: must be `true`
- `max_requests_per_run`: conservative source-level limit
- `min_seconds_between_requests`: throttling floor
- `timeout_seconds`: bounded per-request timeout
- `cache_ttl_minutes`: cache freshness policy under ignored `outputs/cache/`
- `max_response_bytes`: future response-size ceiling, if implemented
- `user_agent`: documented project user-agent, never a secret
- `run_id`: local or GitHub Actions run identifier
- `scan_date`: `YYYY-MM-DD`
- `mode`: adapter mode
- `out`: safe repo-contained ignored `outputs/` path

The adapter must reject inputs that are missing required policy fields, contain private paths, contain secret-like values, require login, require paywall access, use non-HTTPS URLs, use credential-bearing URLs, or point outside approved source registry entries.

## Adapter Output Contract

A future adapter should emit structured JSON artifacts only under ignored `outputs/` paths.

Expected top-level fields for a source observation artifact:

- `schema_version`
- `scan_id`
- `scan_date`
- `generated_at`
- `timezone`
- `adapter_mode`
- `source_observations`
- `errors`
- `provenance`

The artifact must be validatable, deterministic in replay mode, and safe to upload as a short-lived GitHub Actions artifact. It must not be committed unless a later phase explicitly defines a sanitized fixture format.

## Source Observation Output Fields

Each future source observation should include:

- `observation_id`
- `source_id`
- `source_title`
- `publisher`
- `source_type`
- `category_id`
- `url`
- `retrieved_at`
- `published_at`, if available from metadata
- `observed_at`
- `fetch_mode`
- `adapter_mode`
- `http_status`, if applicable
- `content_type`, if applicable
- `content_length_bytes`, if safely known
- `etag`, `last_modified`, or equivalent safe metadata, if available
- `title`, if safely extracted
- `summary`, if safely extracted from public metadata
- `canonical_url`, if safely extracted and HTTPS
- `language`, if safely known
- `raw_content_stored`: must be `false` by default
- `review_required`: must be `true`
- `confidence`: `high`, `medium`, or `low`
- `safety_flags`
- `uncertainty_notes`

Observations must not include raw HTML, full response bodies, cookies, authorization headers, signed URLs, session IDs, private paths, credentials, screenshots, DOCX exports, HTML exports from private workflows, or copied private migration artifacts.

## Error Output Fields

Each future error record should include:

- `error_id`
- `source_id`
- `url`
- `adapter_mode`
- `error_type`
- `safe_message`
- `http_status`, if applicable
- `occurred_at`
- `retryable`
- `source_disabled_recommended`
- `manual_review_required`

Allowed `error_type` examples:

- `disabled_source`
- `unsafe_url`
- `private_path_detected`
- `secret_like_value_detected`
- `login_required`
- `paywall_detected`
- `timeout`
- `rate_limited`
- `not_found`
- `forbidden`
- `server_error`
- `invalid_metadata`
- `response_too_large`
- `cache_error`

Error records must not expose response bodies, token-like strings, secret values, cookies, signed query strings, private local paths, or raw HTML snippets.

## Future Adapter Modes

These modes are planned only and are not implemented yet:

- `disabled`: no observation is performed; source is skipped with a safe disabled-source note.
- `replay_fixture`: load a committed safe fixture and produce deterministic observations without network access.
- `manual_snapshot`: load a manually prepared metadata snapshot that has already been reviewed for public safety.
- `live_http_metadata_only`: future network mode that reads bounded HTTP metadata only, such as status, content type, last-modified, and canonical URL metadata when safe.
- `live_http_page_metadata`: future network mode that extracts bounded page metadata from approved public HTTPS pages without storing raw HTML.

Initial implementation should support `disabled` and `replay_fixture` first. Network-capable modes require separate approval.

## Timeout Policy

Future live-capable modes must use short, bounded timeouts:

- source-level `timeout_seconds` from the registry
- no unbounded waits
- no aggressive retries
- timeout classified as a safe unresolved error
- no report candidate promotion from timed-out sources

A timeout should not block the whole run unless the run has no safe observations left and cannot produce a valid quiet-day or partial artifact.

## Rate-Limit Policy

Future live-capable modes must honor registry limits:

- `max_requests_per_run`
- `min_seconds_between_requests`
- per-run maximum observation count
- zero or small bounded retry count
- fail-closed behavior for HTTP 429

If rate limits are hit, the adapter should record a safe `rate_limited` error and stop accessing that source for the run.

## Cache Policy

A future cache must remain under ignored paths such as `outputs/cache/`.

Requirements:

- cache files are generated outputs and must not be committed
- cache keys must not contain secrets or private paths
- raw HTML and full response bodies are not stored by default
- cached metadata must pass the same safety checks as fresh metadata
- cache TTL must respect registry `cache_ttl_minutes`
- stale cache should be marked clearly in provenance

## User-Agent Policy

A future live-capable adapter must use a documented, non-secret user-agent that identifies the project and purpose. The user-agent must not contain personal tokens, email credentials, API keys, chat IDs, local paths, or private workspace names.

## HTTPS-Only Policy

Future adapters must reject:

- `http://` URLs
- local file URLs
- localhost URLs
- private network URLs
- local machine paths
- signed URLs or credential-bearing query strings
- URLs with embedded username or password

Only public HTTPS URLs from the validated source registry are eligible for future live modes.

## No-Login And No-Paywall Policy

Future adapters must reject sources that require:

- login
- cookies or session state
- paid access
- private workspace membership
- private repository access
- browser-only authenticated flows

If access appears restricted, the adapter should record a safe error and require manual review.

## No Secret-Bearing URL Policy

Future adapters must reject URLs, headers, fixture files, cache files, logs, and artifacts containing token-like or secret-like values.

Rejected examples include:

- API keys
- bearer tokens
- Telegram bot tokens
- chat IDs
- signed URL query strings
- session IDs
- private path fragments
- `.env`-style assignments

Logs and errors must print failed check names and file paths only, not secret values.

## No Raw HTML Commit Policy

Raw HTML, full response bodies, screenshots, DOCX files, private HTML exports, and browser captures must not be committed as fixtures or outputs.

Replay fixtures should contain only public-safe reduced metadata needed to test parsing and error behavior.

## No Generated Outputs Commit Policy

Generated files under `outputs/`, cache directories, live dry-run artifacts, topic candidate previews, and source observation outputs must remain ignored and untracked unless a later phase explicitly creates a sanitized committed fixture format.

## Manual Review Gate Before Report Candidate

A source observation or topic candidate can only become a reviewed report candidate after manual review confirms:

- public source URL
- publisher attribution
- source type and category
- claim relevance
- topic ranking and dedup behavior
- uncertainty notes
- English wording
- no private paths
- no secrets
- no raw migration artifacts
- quality-gate readiness
- static page review readiness

The adapter output is a discovery aid, not a publication source of truth.

## Artifact-Only First Live Dry-Run Policy

The first future live-capable dry run must be manual-only and artifact-only:

1. Triggered manually, not scheduled.
2. Uses a narrowly approved source subset.
3. Writes observations and candidates under ignored `outputs/` paths.
4. Uploads short-lived artifacts only.
5. Does not commit generated output.
6. Does not deploy Pages.
7. Does not send Telegram.
8. Does not call OpenAI APIs.
9. Does not generate images.
10. Does not create DOCX files.
11. Requires manual artifact inspection before any next phase.

## Replay Fixture Requirements

Future replay fixtures should be committed only after review and should contain:

- fixture schema version
- source ID
- source URL
- adapter mode
- simulated retrieval timestamp
- safe metadata fields
- simulated HTTP status or error type
- expected observation IDs
- expected safety flags
- provenance explaining that the fixture is synthetic or reduced public metadata

Replay fixtures must not contain:

- raw HTML
- full response bodies
- screenshots
- private paths
- credentials
- tokens
- chat IDs
- API keys
- signed URLs
- copied private migration artifacts
- generated private report exports

## No-Network Test Strategy

Future tests must run without network access.

Required tests:

- successful replay fixture parse
- timeout simulated from fixture
- rate-limit simulated from fixture
- unsafe URL rejected
- disabled source skipped or rejected as required
- `enabled: true` rejected until explicitly approved
- raw HTML fixture rejected
- generated output path must be under ignored `outputs/`
- private paths rejected
- secret-like values rejected
- no production side effects

CI must continue to validate replay and fixture behavior without external connectivity.

## Future Files Not Yet Created

These files are planned only and must not be created in this phase:

```text
src/ai_signal_brief/fetch_adapter.py
tests/test_fetch_adapter.py
tests/fixtures/fetch_replay/
docs/fetch-replay-fixtures.md
```

## Future CLI Shape Not Yet Implemented

Planned replay command:

```powershell
python -m ai_signal_brief fetch-source-replay --source-id SOURCE_ID --fixture tests/fixtures/fetch_replay/example.json
```

Planned live-discovery dry-run command:

```powershell
python -m ai_signal_brief discover-topics-live --date YYYY-MM-DD --sources config/topic_sources.live.example.json --mode replay_fixture --out outputs/topic-candidates-live/YYYY-MM-DD.json
```

Both commands are future proposals only. They must not perform live network access until separately approved.

## Future Enablement Criteria

Before any network-capable adapter mode is enabled, all of these must be true:

- disabled live source registry validates
- adapter interface and replay fixture tests pass
- no-network CI remains green
- replay fixtures have been reviewed
- output artifacts remain ignored
- cache policy is tested
- timeout and rate-limit behavior are tested
- unsafe URL and secret detection are tested
- manual artifact review process is documented
- rollback path is documented
- workflow remains manual-only for first live dry run
- schedule receives separate approval later

## Rollback Plan

If future adapter work creates unsafe behavior:

1. Keep live modes disabled.
2. Remove or disable affected source registry entries.
3. Delete unsafe artifacts from GitHub Actions if necessary.
4. Revert the adapter implementation commit.
5. Keep production Pages, Telegram, OpenAI API, image generation, and DOCX disconnected.
6. Do not promote any topic candidate from the failed run.
7. Add a documented failure note before retrying.

## Non-Goals

This plan does not:

- implement `fetch_adapter.py`
- create replay fixtures
- create a live CLI command
- modify GitHub Actions
- add workflow triggers
- add a schedule
- fetch live web pages
- call external APIs
- send Telegram messages
- call OpenAI APIs
- generate images
- create DOCX files
- deploy Pages
- publish reports
- migrate historical reports
