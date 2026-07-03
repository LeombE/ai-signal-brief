# Topic Sources And Topic Candidates

## Purpose

Topic discovery is the future upstream process for finding possible AI stories. It is not report publication.

A topic candidate is only a review object. It can be unresolved, duplicated, low confidence, or rejected. It must not become a public report until a human reviewer confirms sources, claim mapping, wording, safety, and publication readiness.

## Files Added In This Phase

- `config/topic_sources.example.json`
- `schemas/topic-candidates.schema.json`
- `examples/topic-candidates.example.json`

These files are public-safe examples. They do not implement collectors, schedules, live fetching, Telegram delivery, OpenAI API calls, image generation, DOCX generation, or production Pages deployment.

## Topic Source Registry

`config/topic_sources.example.json` defines a future source registry for daily topic discovery. It is separate from the canonical report source registry so source observation behavior can evolve without weakening report validation.

The registry includes `schema_version`, `source_policy`, `allowed_source_types`, `categories`, `sources`, `priority`, `reliability_tier`, `expected_update_frequency`, `allowed_fetch_mode`, attribution requirements, and safety notes.

All example sources are disabled by default. A later implementation phase must explicitly decide which sources can be observed and how. Live-source eligibility, fetch policy, caching, and artifact-only test requirements are documented in `docs/live-source-discovery-readiness.md`.

## Source Categories

The registry models these categories:

- official company announcements
- model cards
- research papers
- public repositories
- benchmark and evaluation releases
- regulatory and policy sources
- credible technical news
- GitHub releases and changelogs
- public security advisories

Official and primary sources should take priority over secondary coverage. Credible news can help discover topics, but technical claims should prefer official announcements, papers, model cards, repositories, advisories, changelogs, or regulatory sources when available.

## Topic Candidate Schema

`schemas/topic-candidates.schema.json` defines the future topic candidate artifact shape.

Top-level fields include:

- `schema_version`
- `scan_id`
- `scan_date`
- `generated_at`
- `timezone`
- `topics`
- `source_observations`
- `dedup_groups`
- `unresolved_items`
- `provenance`

Each topic supports:

- `topic_id`
- `topic_title`
- `candidate_status`
- `topic_type`
- `companies`
- `models`
- `regions`
- `source_observation_ids`
- `source_ids`
- `primary_source_ids`
- `material_update_score`
- `importance_score`
- `novelty_score`
- `source_quality_score`
- `confidence`
- `uncertainty_notes`
- `review_recommendation`
- `review_required`
- `safety_flags`
- `dedup_key`
- `related_topic_ids`

## Example Candidate File

`examples/topic-candidates.example.json` uses placeholder data only. It does not contain real current news claims.

The example demonstrates:

- one unresolved placeholder model-card topic
- one quiet-day placeholder topic
- one source observation
- one dedup group
- one unresolved item
- provenance that keeps the artifact not published and not connected to delivery or generation systems

## Quiet Days

Quiet days are valid. If no topic clears the review threshold, the system should produce an artifact explaining that no publication candidate was found rather than forcing a low-quality report.

## Uncertain Topics

Uncertain topics should remain visible but unresolved. They should not be promoted to canonical reports until a reviewer can confirm the source, date, claim scope, and public attribution.

## Dedup And Material-Update Scoring

Deduplication should group repeated observations without deleting the audit trail.

Material-update scoring should favor topics with real changes, such as a new model card, official launch, API availability, benchmark release, security advisory, repository release, or policy update. Repeated coverage without new facts should receive lower priority.

Ranking should consider source quality, material update strength, novelty, ecosystem impact, verification confidence, and uncertainty penalties.

## Manual Review Gate

A topic candidate requires manual review before report generation.

Minimum gates before report publication:

- source review
- claim/source mapping review
- security review
- dedup review
- ranking review
- editorial review
- generated page review
- public-readiness check

## Future Workflow Strategy

The first workflow should be `workflow_dispatch` only.

A scheduled workflow should be considered only after local and manual runs pass. The proposed future Malaysia 04:07 schedule is `7 20 * * *` in UTC.

The first scheduled version should upload topic candidate artifacts only. It should not automatically commit generated candidates, publish reports, deploy production Pages, send Telegram messages, call OpenAI APIs, generate images, or create DOCX files.

## Safety Boundaries

Future topic discovery must preserve these boundaries:

- no private source copying
- no raw historical report copying
- no secrets or private local paths
- no Telegram delivery
- no OpenAI API calls
- no image generation
- no DOCX generation
- no production Pages deployment from topic candidates alone
- no automatic report publication

## Offline Validation Commands

Topic source and topic candidate validation is implemented as offline-only CLI checks. These commands load local JSON files, validate structure and references, reject secret-like or private markers, and do not fetch live sources.

```powershell
python -m ai_signal_brief validate-topic-sources config/topic_sources.example.json
python -m ai_signal_brief validate-topics examples/topic-candidates.example.json
python -m ai_signal_brief rank-topics examples/topic-candidates.example.json --explain
python -m ai_signal_brief discover-topics --date 2026-06-24 --sources config/topic_sources.example.json --mock-observations tests/fixtures/topic_observations.valid.json --out outputs/topic-candidates/2026-06-24.json --rank
```

The topic source registry validator checks required fields, unique category/source IDs, allowed source types, category references, positive priorities, reliability tiers, fetch modes, public HTTPS URLs, and no private/local or secret-like markers.

The topic candidate validator checks required top-level fields, ISO-8601 timestamps with timezones, unique topic/source observation IDs, source and observation references, score ranges, candidate status, confidence, review flags, unresolved and quiet-day behavior, and no private/local or secret-like markers.

The topic ranking command validates input before ranking. It combines `source_quality_score`, `material_update_score`, `importance_score`, `novelty_score`, confidence adjustment, uncertainty penalty, safety flag penalty, and material-evidence adjustment. It keeps unresolved and quiet-day candidates visible, marks lower-ranked duplicate or related topics as `duplicate_or_related`, and writes generated ranked JSON only when `--out` points under `outputs/`.

Deduplication uses `dedup_key` first and `related_topic_ids` as an audit signal. It never deletes candidate records silently; duplicate and related candidates remain available for manual review. Material-update detection treats official releases, model cards, repository releases, papers, regulatory sources, and security advisories as stronger evidence, while news-only or social-only items remain cautious and do not upgrade uncertain claims.

The mock discovery command reads local placeholder observation fixtures only. It validates `config/topic_sources.example.json`, converts local observations into topic candidates, preserves `observed_at` and `published_at`, generates deterministic topic IDs and dedup keys, writes output only under `outputs/`, validates the generated candidate JSON, and can run `rank-topics` when `--rank` is passed. It does not fetch live sources.

## Future Work

Live source discovery, readiness checks, scheduled scans, and publication are still unimplemented. Future live-source planning is documented in `docs/live-source-discovery-readiness.md`. Planned future commands remain separate from the current validators, mock discovery, and ranker:

```powershell
python -m ai_signal_brief topic-scan-readiness
```
