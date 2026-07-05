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


## First Rehearsal Result: 2026-07-05

The first manual no-network artifact review rehearsal was run for `2026-07-05`.

Generated artifact:

```text
outputs/topic-candidates-live-dry-run/2026-07-05.json
```

Artifact summary:

- topics: 9
- source observations: 9
- unresolved items: 9
- all topics had `candidate_status: unresolved`
- all topics had `review_required: true`
- all topics had `source_ids` and `primary_source_ids`
- confidence fields existed; all candidates were low confidence
- uncertainty fields existed on all candidates
- each candidate had a deterministic `dedup_key`
- no duplicate group required merging
- `provenance.live_fetching` was `false`
- `provenance.publication_status` was `not_published`
- Telegram delivery, OpenAI API usage, image generation, DOCX generation, and production Pages deployment remained not configured
- output stayed under `outputs/`
- `git ls-files outputs` returned no tracked files
- `git status --short` was clean after the rehearsal

Manual classification:

- strong candidates: none
- weak candidates: all 9 candidates, because live fetching was disabled and source timing/review was incomplete
- duplicate or related candidates: none requiring merge; each candidate had a unique deterministic `dedup_key`
- unsafe candidates: none detected by validation
- ready for promotion: no

Local validation passed for the rehearsal:

- `compileall`
- `validate-topic-sources` for the example registry
- `validate-topic-sources` for the disabled live registry
- `discover-topics-live-dry-run 2026-07-05`
- `validate generated topics`
- `public-readiness`
- `unittest`: 174 tests OK
- `git diff --check`
- `git ls-files outputs`

This rehearsal is schedule-readiness evidence only. It is not evidence of live fetching, source publication timing, report readiness, Telegram delivery, OpenAI usage, image generation, DOCX generation, or Pages production deployment.

## Second Rehearsal Result: 2026-07-06

The second manual no-network artifact review rehearsal was run for `2026-07-06`.

Generated artifact:

```text
outputs/topic-candidates-live-dry-run/2026-07-06.json
```

Artifact summary:

- topics: 9
- source observations: 9
- unresolved items: 9
- all topics had `candidate_status: unresolved`
- all topics had `review_required: true`
- all topics had `source_ids` and `primary_source_ids`
- confidence fields existed; all candidates were low confidence
- uncertainty fields existed on all 9 topics
- duplicate or related evidence existed through deterministic `dedup_key`
- dedup groups: 9
- multi-topic dedup groups: 0
- `provenance.live_fetching` was `false`
- `provenance.publication_status` was `not_published`
- Telegram delivery, OpenAI API usage, image generation, DOCX generation, and production Pages deployment remained not configured
- output stayed under `outputs/`
- `git ls-files outputs` returned no tracked files
- `git status --short` was clean after the rehearsal

Comparison with the first rehearsal:

- `2026-07-06` matched the `2026-07-05` metadata-only no-network pattern
- same topic count: yes
- same source observation count: yes
- same unresolved item count: yes
- same source IDs: yes
- same topic titles: yes
- both all unresolved: yes
- both all review-required: yes
- both `live_fetching: false`: yes
- both `publication_status: not_published`: yes
- no generated output was tracked by Git in either rehearsal

Manual classification:

- strong candidates: none
- weak candidates: all 9 candidates, because live fetching was disabled and source timing/review was incomplete
- duplicate or related candidates: none requiring merge; each candidate had a unique deterministic `dedup_key`
- unsafe candidates: none detected by validation
- ready for promotion: no

Local validation passed for the rehearsal:

- `compileall`
- `validate-topic-sources` for the example registry
- `validate-topic-sources` for the disabled live registry
- `discover-topics-live-dry-run 2026-07-06`
- `validate generated topics`
- `public-readiness`
- `unittest`: 174 tests OK
- `git diff --check`
- `git ls-files outputs`

This second rehearsal adds repeatability evidence for the manual artifact review process. It is not evidence of live fetching, source publication timing, report readiness, Telegram delivery, OpenAI usage, image generation, DOCX generation, or Pages production deployment.
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