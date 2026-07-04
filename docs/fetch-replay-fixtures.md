# Fetch Replay Fixtures

## Status

Fetch replay fixtures are local, public-safe test inputs for the replay-only fetch adapter. They do not enable live source fetching, external API calls, workflow changes, schedules, Telegram delivery, OpenAI API usage, image generation, DOCX generation, Pages deployment, or report publication.

GitHub Actions CI for commit `85ec975 Add replay-only fetch adapter skeleton` was manually confirmed green in the GitHub UI. The confirmation covers replay-only fixture parsing and validation; it does not make the adapter a live web fetcher and does not activate scheduling, Telegram, OpenAI API usage, image generation, DOCX generation, Pages deployment, or report publication.

GitHub Actions CI for commit `43d2344 Remove urllib imports from validation helpers` was manually confirmed green in the GitHub UI. The no-urllib safety fix removed `urllib.parse` imports from validation helpers while preserving local HTTPS/source validation. `fetch-source-replay` still reads local JSON replay fixtures only and does not enable live HTTP fetching, scheduling, Telegram, OpenAI API usage, image generation, DOCX generation, Pages deployment, or report publication.

The current replay command reads local JSON only:

```powershell
python -m ai_signal_brief fetch-source-replay --source-id openai-news --fixture tests/fixtures/fetch_replay/example_official_release.json
```

## Purpose

Replay fixtures exercise adapter parsing, validation, deterministic observation output, and failure handling without network access.

They are different from mock observations:

- mock observations are already-shaped topic discovery inputs
- replay fixtures are reduced source metadata snapshots that the adapter converts into source observations
- manual snapshots are future reviewed metadata files prepared by a human
- live fetch is not implemented and must remain separate

## Directory And Naming

Fixture files live under:

```text
tests/fixtures/fetch_replay/
```

Current fixtures:

- `example_official_release.json`: valid synthetic official release metadata
- `example_model_card.json`: valid synthetic model card metadata
- `invalid_private_path.json`: intentionally invalid private-path fixture
- `invalid_secret_like.json`: intentionally invalid secret-like marker fixture
- `invalid_raw_html.json`: intentionally invalid raw markup fixture

Negative fixtures exist only for tests and have narrow public-readiness allowlist entries. Do not allowlist the whole directory.

## Required Fixture Fields

Each replay fixture must include:

| Field | Requirement |
| --- | --- |
| `fixture_schema_version` | Must be `1.0.0`. |
| `source_id` | Stable source ID expected by the CLI. |
| `source_type` | One of report-compatible source types. |
| `title` | Public-safe fixture title. |
| `url` | Public HTTPS URL without credentials, query strings, or fragments. |
| `observed_at` | ISO-8601 timestamp with timezone. |
| `published_at` | ISO-8601 timestamp with timezone or null. |
| `retrieved_at` | ISO-8601 timestamp with timezone. |
| `fetch_mode` | Must be `replay_fixture`. |
| `content_type` | Reduced metadata content type; raw HTML is not allowed. |
| `reduced_metadata` | Small public-safe metadata object. |
| `entities` | Companies, models, and regions arrays. |
| `content_hash` | Lowercase SHA-256 hex string. |
| `source_confidence` | `high`, `medium`, or `low`. |
| `safety_flags` | Array of strings. |

## Forbidden Fixture Content

Replay fixtures must not include:

- raw HTML or full response bodies
- full article bodies
- screenshots
- DOCX exports
- private HTML exports
- Telegram exports
- private migration material
- local machine paths
- secrets or credentials
- API keys
- bot tokens
- chat identifiers
- signed URLs
- login-required URLs
- cookies or authorization headers
- generated outputs

## Test Matrix

Current and future tests should cover:

- valid fixture loading
- valid fixture to source observation conversion
- deterministic JSON output
- private path rejection
- secret-like marker rejection
- raw markup rejection
- missing required fields
- non-HTTPS URL rejection
- non-replay fetch mode rejection
- source ID mismatch rejection
- no network module import or call
- CLI zero exit for valid fixture
- CLI non-zero exit for invalid fixture
- no workflow or schedule changes

## Safety Checklist

Before adding a new replay fixture, verify:

- fixture is synthetic or reduced public metadata only
- URL is public HTTPS
- no query string or fragment is present
- no credential or signed URL is present
- no local path appears
- no private migration artifact appears
- no raw markup or full body appears
- `fetch_mode` is `replay_fixture`
- output remains metadata-only
- fixture does not publish or deliver anything

## Non-Goals

Replay fixtures do not:

- fetch live sources
- enable live source registry entries
- create topic candidates directly
- publish reports
- deploy Pages
- send Telegram messages
- call OpenAI APIs
- generate images
- create DOCX files
- add a schedule
