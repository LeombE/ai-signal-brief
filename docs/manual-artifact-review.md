# Manual Artifact Review

Manual artifact review is the required human checkpoint before any live-source workflow, schedule, report publication, Telegram delivery, OpenAI usage, image generation, DOCX generation, or production Pages deployment is considered.

The current live-source dry-run is no-network. It reads disabled source-registry metadata only and writes reviewable topic-candidate JSON under `outputs/`.

## Current Capability

The stable local capability is intentionally narrow:

- replay discovery remains local-fixture-only
- `discover-topics-live-dry-run` remains no-network
- source entries in `config/topic_sources.live.example.json` remain `enabled: false`
- source entries remain `fetch_mode: disabled`
- generated output is metadata-only and artifact-only
- generated topics remain `candidate_status: unresolved`
- generated topics remain `review_required: true`
- `discover-topics-live` does not exist
- generated files under `outputs/` must not be committed

## Run A Manual Dry-Run

Start from a clean local state:

```powershell
git branch --show-current
git status --short
git log --oneline -5
```

Run the no-network live dry-run:

```powershell
python -m ai_signal_brief discover-topics-live-dry-run --date YYYY-MM-DD --sources config/topic_sources.live.example.json --out outputs/topic-candidates-live-dry-run/YYYY-MM-DD.json --artifact-only --metadata-only
```

Validate the generated artifact:

```powershell
python -m ai_signal_brief validate-topics outputs/topic-candidates-live-dry-run/YYYY-MM-DD.json
python -m ai_signal_brief public-readiness
git status --short
git ls-files outputs
```

`git ls-files outputs` must print no tracked generated files.

## Review The Artifact

Open the generated JSON under `outputs/topic-candidates-live-dry-run/` and inspect every topic candidate.

Classify candidates conservatively:

- strong candidate: public HTTPS source, clear attribution, useful topic label, explainable source metadata, and clear confidence or uncertainty notes
- weak candidate: vague source purpose, missing timing confidence, low confidence, insufficient source description, or unclear topic usefulness
- duplicate candidate: same vendor, source category, source URL, model family, or overlapping topic intent with another candidate
- unsafe candidate: private path, secret-like value, login-required source, paywall/private marker, raw HTML/full-body content, non-HTTPS URL, token/chat/API key marker, or private migration reference

Do not promote any candidate to a report until a human reviewer confirms source scope, timing, attribution, and claim limits.

## No-Live-Fetch Confirmation

For each review run, confirm:

- `discover-topics-live-dry-run` was the command used
- no `discover-topics-live` command exists or was run
- source registry entries remained `enabled: false`
- `fetch_mode` remained `disabled`
- output stayed under `outputs/`
- generated candidates stayed unresolved and review-required
- no Telegram, OpenAI API, image generation, DOCX generation, Pages production deployment, or report publication occurred
- generated outputs were not staged or committed

## Reviewer Checklist

Use this checklist before treating a dry-run artifact as schedule-readiness evidence:

- CI is green for latest `main`
- Topic Scan Preview remains manual-only
- no schedule exists
- live dry-run remains no-network
- output path is under `outputs/`
- generated outputs are untracked
- each topic is `unresolved`
- each topic has `review_required: true`
- source attribution is present
- confidence and uncertainty fields are present
- duplicate or related topics are identifiable
- unsafe or private sources are rejected
- no Telegram, OpenAI API, image generation, DOCX generation, Pages production deployment, or report publication behavior exists