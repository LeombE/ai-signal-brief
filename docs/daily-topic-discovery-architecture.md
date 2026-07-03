# Daily AI Topic Discovery Architecture

## Purpose

Daily topic discovery is the planned upstream process for identifying candidate AI stories before any public report is written or published.

The goal is to produce a safe, auditable topic-candidate artifact that helps a human reviewer decide what should become a reviewed canonical report. Topic discovery is not report publication, not GitHub Pages deployment, not Telegram delivery, not image generation, and not DOCX generation.

## Current Boundary

This document is an architecture plan only. It does not implement collectors, live source fetching, GitHub Actions schedules, OpenAI API usage, Telegram delivery, image generation, production Pages deployment, or historical migration.

Future implementation must remain offline-safe until each capability is explicitly approved and reviewed.

## Topic Discovery Versus Report Publication

Topic discovery answers: what may be worth reviewing today?

Report publication answers: what has been reviewed, sourced, rewritten, validated, and approved for public release?

Topic discovery may produce incomplete, uncertain, duplicated, or low-confidence candidates. Those candidates must not be treated as public reports. A reviewed report requires separate manual review, source mapping, quality gates, static page inspection, and publication approval.

## Source Registry Expansion Strategy

The existing `config/sources.example.json` registry defines general source priorities for canonical reports. Daily topic discovery should use a separate future registry so collector behavior can evolve without weakening report validation rules.

Future file, not created in this phase:

- `config/topic_sources.example.json`

The topic source registry should include:

- source identity and category
- source type compatible with existing report source types where possible
- official-source-first priority
- polling or observation strategy
- allowed fetch mode, such as official feed, public release page, repository metadata, or manually supplied snapshot
- expected update cadence
- attribution requirements
- rate-limit and terms notes
- whether the source is eligible for automated observation, manual-only observation, or disabled observation

## Official-Source-First Policy

Official sources should be checked before secondary coverage whenever possible.

Secondary technical news can help discover an item, but it should not be the sole basis for technical claims when an official announcement, paper, model card, repository, advisory, changelog, or regulatory source is available.

Topic discovery should preserve source provenance separately from ranking. A high-interest topic with weak sourcing should remain unresolved rather than being promoted into a strong report claim.

## Source Categories

Future topic discovery should support these categories:

- official company announcements
- model cards
- research papers
- public repositories
- benchmark and evaluation releases
- regulatory and policy sources
- credible technical news
- GitHub releases and changelogs
- public security advisories

Each category should define default priority, attribution rules, acceptable source types, and whether official confirmation is required before report publication.

## Source Observation Schema

Future source observations are low-level records of something seen at a source. They are not report claims.

Proposed source observation fields:

- `id`: stable observation ID
- `source_id`: registry source ID
- `source_category`: category from the topic source registry
- `source_type`: official, paper, repository, regulatory, news, social, or other where compatible
- `publisher`: source publisher
- `title`: observed item title
- `url`: public HTTPS URL
- `observed_at`: timestamp when the system observed the item
- `published_at`: source-declared publication timestamp when available
- `retrieved_at`: timestamp when content or metadata was retrieved
- `language`: observed language if known
- `raw_signal_type`: announcement, model_card, paper, repository_release, benchmark, advisory, policy_update, changelog, news_context, or other
- `summary`: short neutral observation summary
- `entities`: companies, models, products, projects, benchmarks, standards, regions
- `content_hash`: optional stable hash for change detection
- `source_confidence`: high, medium, or low
- `review_status`: new, reviewed, unresolved, rejected, or duplicate
- `safety_flags`: array of non-secret flags such as private_path_detected, weak_source, unclear_date, or requires_manual_review

## Topic Candidate Schema

Future file, not created in this phase:

- `schemas/topic-candidates.schema.json`
- `examples/topic-candidates.example.json`

A topic candidate aggregates one or more source observations into a reviewable potential story.

Proposed topic candidate fields:

- `schema_version`
- `scan_id`
- `scan_date`
- `generated_at`
- `timezone`
- `source_registry_id`
- `topic_id`
- `topic_title`
- `candidate_status`: new, update, follow_up, duplicate, unresolved, rejected, or quiet_day_note
- `topic_type`: model_release, product_release, research, benchmark, developer_tooling, security, policy, infrastructure, company_strategy, ecosystem, or other
- `summary`
- `companies`
- `models`
- `regions`
- `source_observation_ids`
- `source_ids`
- `primary_source_ids`
- `secondary_source_ids`
- `published_at_min`
- `observed_at_first`
- `observed_at_latest`
- `material_update_score`
- `importance_score`
- `novelty_score`
- `source_quality_score`
- `review_priority_score`
- `dedup_key`
- `related_topic_ids`
- `uncertainty_notes`
- `review_recommendation`: include, monitor, defer, reject, or needs_source_review
- `review_required`: boolean
- `safety_flags`

## Future CLI Commands

Future commands, not implemented in this phase:

```powershell
python -m ai_signal_brief discover-topics --date YYYY-MM-DD --sources config/topic_sources.example.json --out outputs/topic-candidates/YYYY-MM-DD.json
python -m ai_signal_brief validate-topics outputs/topic-candidates/YYYY-MM-DD.json
python -m ai_signal_brief rank-topics outputs/topic-candidates/YYYY-MM-DD.json
python -m ai_signal_brief topic-scan-readiness
```

Expected behavior:

- `discover-topics` writes local candidate artifacts only.
- `validate-topics` validates schema, source references, timestamps, safety flags, and no-secret rules.
- `rank-topics` ranks existing candidate artifacts without fetching live data.
- `topic-scan-readiness` checks config, schema files, output paths, source policy, and safety settings before any scheduled run.

## Future Implementation Files

Future files, not created in this phase:

- `config/topic_sources.example.json`
- `schemas/topic-candidates.schema.json`
- `examples/topic-candidates.example.json`
- `src/ai_signal_brief/topic_discovery.py`
- `tests/test_topic_discovery.py`
- `.github/workflows/daily-topic-scan.yml`

## Ranking And Scoring Rules

Topic ranking should be explainable and conservative. A topic should not outrank others solely because it is noisy or repeated.

Proposed scoring components:

- `source_quality_score`: official sources, papers, model cards, repositories, advisories, and regulatory sources score higher than secondary coverage.
- `material_update_score`: new model, new capability, production availability, security impact, policy change, benchmark result, or developer workflow impact.
- `novelty_score`: whether the item is new relative to previous observations and existing reviewed reports.
- `ecosystem_impact_score`: likely effect on developers, enterprises, researchers, policy, security, or open model ecosystems.
- `verification_score`: whether material facts can be mapped to public source IDs.
- `uncertainty_penalty`: unclear date, weak sourcing, ambiguous product status, missing official confirmation, or duplicated coverage.
- `freshness_score`: recency relative to the scan date and timezone.

A future `review_priority_score` can be a weighted combination of these components. Weights should be documented and tested before schedule activation.

## Deduplication Rules

Deduplication should prevent repeated daily coverage without suppressing genuinely material updates.

Proposed dedup keys:

- normalized title
- canonical URL
- company plus model or product
- source category plus release identifier
- repository owner/name plus release tag
- paper title plus arXiv or DOI identifier when available
- advisory identifier when available

Dedup behavior:

- Merge observations that clearly refer to the same event.
- Keep official and primary sources as canonical when duplicates exist.
- Preserve secondary sources as supporting context when useful.
- Mark duplicate candidates as duplicate rather than deleting them from audit artifacts.
- Do not deduplicate separate material updates just because they share the same company or model family.

## Material-Update Detection

A material update should have meaningful new information compared with previous observations or reviewed reports.

Material signals include:

- new model release or model-card availability
- new product capability
- public API availability
- pricing or availability change with source support
- benchmark or evaluation release
- repository release or significant changelog
- security advisory or patching workflow change
- regulatory or policy update
- production deployment or enterprise availability

Non-material signals include:

- repeated coverage without new facts
- reposted announcements
- vague teasers without source support
- social-only speculation
- minor copy edits or marketing restatements

## Watchlist Behavior

A watchlist should track vendors, model families, repositories, benchmark suites, policy sources, and security advisories that matter to daily AI coverage.

Watchlist entries should include:

- entity ID
- entity name
- category
- priority
- source IDs to observe
- expected update cadence
- last observed date
- last reviewed report date
- review notes

Watchlist matches should raise review priority but should not bypass source validation or manual review gates.

## Unresolved Or Uncertain Topic Behavior

Uncertain topics should remain visible without becoming strong claims.

Rules:

- Keep unresolved candidates in the topic artifact with clear `uncertainty_notes`.
- Mark unclear dates explicitly.
- Do not promote weakly sourced items into canonical reports.
- Prefer `monitor` or `needs_source_review` over `include` when official confirmation is missing.
- Avoid inferring publication, availability, benchmark meaning, or production readiness from ambiguous metadata.

## Quiet-Day Behavior

A quiet day is a valid scan result.

If no topic passes minimum review-priority thresholds, the scanner should produce a quiet-day candidate artifact rather than forcing a report.

Quiet-day output should include:

- scan metadata
- source categories checked
- count of observations
- count of rejected, duplicate, and unresolved candidates
- explanation that no publication candidate met the threshold

Quiet-day behavior prevents low-quality filler reports.

## Timezone And Timestamp Handling

The project currently uses `Asia/Kuala_Lumpur` for local report operations. Future scheduled scans should be explicit about timestamp semantics.

Definitions:

- `observed_at`: when the scanner or reviewer first observed the item.
- `published_at`: timestamp claimed by the source, if available.
- `retrieved_at`: when source metadata or content was retrieved.
- `generated_at`: when the topic candidate artifact was generated.
- `scan_date`: the local reporting date for the scan.

Rules:

- Store timestamps as ISO-8601 with timezone.
- Preserve source-declared `published_at` separately from local `observed_at`.
- Do not use `observed_at` as a substitute for `published_at`.
- If `published_at` is missing or ambiguous, mark it unresolved.

## Manual Review Gate Before Report Publication

Topic candidates must pass manual review before becoming canonical reports.

Required future gates:

- source review
- security review
- ranking review
- dedup review
- scheduler review
- CI/test review
- editorial review

A candidate should not enter `reports-reviewed/` until it has public sources, English rewritten prose, claim/source mapping, no private material, no secrets, and a completed review note.

## Delivery And Generation Boundaries

Future topic discovery must preserve these boundaries:

- No Telegram delivery before the Pages URL for the reviewed report is verified.
- No OpenAI API usage before a dedicated GitHub Secret is configured and reviewed.
- No image generation before a dedicated secret, cost controls, and artifact policy are approved.
- No production Pages deployment from topic discovery artifacts alone.
- No historical raw report copying.
- No private migration source copying.
- No generated candidates committed automatically in the first scheduled version.

## GitHub Actions Scheduler Strategy

Future workflow file, not created in this phase:

- `.github/workflows/daily-topic-scan.yml`

Strategy:

- Start with `workflow_dispatch` only.
- Add schedule only after local and manual runs pass.
- Use UTC cron.
- Avoid exact top of hour.
- Suggested Malaysia 04:07 schedule: `7 20 * * *`.
- First scheduled version uploads topic candidate artifacts only.
- Do not automatically commit generated candidates in the first scheduled version.
- Do not publish reports automatically.
- Do not send Telegram.
- Do not call OpenAI API.
- Do not generate images.
- Do not deploy production Pages.

## Testing Strategy

Future tests should cover:

- topic source registry loading
- topic candidate schema validation
- duplicate source IDs and topic IDs
- safe timestamp parsing
- source ID resolution
- ranking score determinism
- dedup key generation
- material-update classification
- quiet-day output
- secret and private-path rejection
- no network access in offline tests
- scheduler readiness checks

Tests should use committed safe fixtures and temporary output directories under ignored `outputs/` paths.

## Documentation Strategy

Future documentation should explain:

- how topic discovery differs from report publication
- source registry policy
- source category priorities
- scoring methodology
- dedup methodology
- quiet-day behavior
- scheduler activation checklist
- manual review gates
- security and secret boundaries

## Phase Exit Criteria For Future Implementation

A future implementation phase should not be considered complete until:

- topic source registry exists and validates
- topic candidate schema exists and validates
- examples are public-safe
- CLI commands are documented and tested
- no network is required for tests
- topic artifacts reject secrets and private paths
- public-readiness passes
- CI passes
- no scheduled workflow is enabled without explicit approval