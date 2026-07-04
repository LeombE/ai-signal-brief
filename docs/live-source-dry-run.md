# Live Source Dry-Run

Live source dry-run is a no-network readiness check for future live source discovery. It validates the disabled live source registry and writes reviewable topic-candidate metadata under `outputs/`.

It does not fetch web pages, publish reports, deploy Pages, send Telegram messages, call OpenAI APIs, generate images, create DOCX files, or enable scheduled automation.

## Command

```powershell
python -m ai_signal_brief discover-topics-live-dry-run --date 2026-06-24 --sources config/topic_sources.live.example.json --out outputs/topic-candidates-live-dry-run/2026-06-24.json --artifact-only --metadata-only
```

Both safety flags are required:

- `--artifact-only`
- `--metadata-only`

The command refuses to run if either flag is omitted.

## What It Generates

The output is a topic-candidates-compatible JSON file. It is intended for manual inspection only.

Generated candidates use:

- `candidate_status: unresolved`
- `review_required: true`
- `review_recommendation: needs_source_review`
- `provenance.generation_mode: live_dry_run_metadata_only`
- `provenance.live_fetching: false`

The generated observations are derived from source registry metadata only. They are not source claims and must not be promoted into reports without human review.

## Safety Gates

The command first validates the topic source registry, then enforces live dry-run rules:

- source entries must remain `enabled: false`
- source entries must remain `fetch_mode: disabled`
- `manual_review_required` must be `true`
- `attribution_required` must be `true`
- rate-limit metadata must be present
- timeout metadata must be present
- URLs must be public HTTPS
- output must stay under `outputs/`
- private paths, secret-like values, token/chat identifier/API key markers, raw HTML content, legacy builders, and private migration markers are rejected through existing validation gates

The command does not support a network flag and does not implement `discover-topics-live`.

## Review Boundary

Live source dry-run artifacts are not production data. They only answer whether the disabled live source registry can produce safe metadata-only review artifacts.

Before any future live source fetching is approved, a human reviewer must inspect:

- source URL scope
- robots and usage notes
- rate-limit metadata
- timeout metadata
- attribution requirements
- manual review requirements
- generated topic-candidate shape

## Workflow Boundary

No GitHub Actions workflow is changed by this command. The existing Topic Scan Preview workflow remains manual-only and mock-fixture-only. A future live workflow or schedule requires separate approval.
