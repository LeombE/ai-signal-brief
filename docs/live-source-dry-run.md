# Live Source Dry-Run

Live source dry-run is a no-network readiness check for future live source discovery. It validates the disabled live source registry and writes reviewable topic-candidate metadata under `outputs/`.

It does not fetch web pages, publish reports, deploy Pages, send Telegram messages, call OpenAI APIs, generate images, create DOCX files, or enable scheduled automation.

GitHub Actions CI for commit `aa173c9 Add no-network live source dry-run` was manually confirmed green in the GitHub UI. That confirmation did not trigger deployment, production Pages publication, Telegram delivery, OpenAI API usage, image generation, DOCX generation, or scheduling.

GitHub Actions CI for commit `637b424 Document no-network live dry-run CI result` was manually confirmed green in the GitHub UI. That documentation-only confirmation did not change workflows, enable scheduling, trigger deployment, publish production Pages, send Telegram, call OpenAI APIs, generate images, create DOCX files, or enable live HTTP fetching.

GitHub Actions CI for commit `01d0113 Document no-network live dry-run documentation CI result` was manually confirmed green in the GitHub UI. That verified documentation confirmation did not change workflows, enable scheduling, trigger deployment, publish production Pages, send Telegram, call OpenAI APIs, generate images, create DOCX files, or enable live HTTP fetching.

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

The command does not support a network flag and does not implement `discover-topics-live`. The only live-source dry-run command is `discover-topics-live-dry-run`, and it reads disabled registry metadata only.

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
