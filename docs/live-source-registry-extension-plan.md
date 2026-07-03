# Live Source Registry Extension Plan

## Status

This document is a planning artifact only. It does not create a live source registry JSON file, implement live fetching, modify workflows, add a schedule, call external APIs, send Telegram messages, use OpenAI APIs, generate images, create DOCX files, or deploy Pages.

The current topic discovery implementation remains offline-only. Existing commands validate local examples, rank local topic candidates, and run mock discovery from committed fixtures.

## Objective

The future live-source registry extension should describe which public sources may be observed, how they may be fetched, what limits apply, and which review gates must pass before any observation can influence a reviewed report candidate.

The registry must be conservative by default: every future live source starts disabled, requires public HTTPS, carries rate-limit metadata, and remains artifact-only during the first live dry-run phase.

## Future Registry Fields

Future live-source entries should extend the topic source registry with these fields:

| Field | Requirement | Purpose |
| --- | --- | --- |
| `enabled` | required, default `false` | Prevents accidental live observation before explicit review. |
| `source_id` | required | Stable source identifier used by observations and topic candidates. |
| `title` | required | Human-readable source name. |
| `publisher` | required | Public publisher or owning organization. |
| `source_type` | required | Must be compatible with report source types. |
| `category_id` | required | Links the source to a topic source category. |
| `priority` | required | Supports official-source-first ordering. |
| `reliability_tier` | required | Indicates primary, official, high, medium, or low review trust. |
| `url` | required | Public HTTPS URL only. |
| `fetch_mode` | required | The intended observation mechanism for the source. |
| `allowed_fetch_mode` | required | The validator-approved fetch mode list or value. |
| `expected_update_frequency` | required | Expected cadence such as daily, weekly, irregular, or manual. |
| `max_requests_per_run` | required | Upper bound for a single workflow or local run. |
| `min_seconds_between_requests` | required | Per-source throttling requirement. |
| `timeout_seconds` | required | Per-request timeout ceiling. |
| `cache_ttl_minutes` | required | Metadata cache duration under ignored `outputs/cache/`. |
| `attribution_required` | required | Must be `true` for live-enabled sources. |
| `manual_review_required` | required | Must be `true` before publication. |
| `robots_policy_note` | required | Human-readable note on robots, terms, or acceptable use. |
| `rate_limit_note` | required | Human-readable rate-limit or request policy note. |
| `safety_notes` | required | Risks, constraints, and operational notes. |
| `disallowed_content_rules` | required | Source-specific exclusions and content boundaries. |

Recommended optional fields for a later implementation:

- `owner_contact`
- `last_policy_reviewed_at`
- `allowed_content_types`
- `max_response_bytes`
- `requires_structured_metadata`
- `default_language`
- `region_scope`
- `manual_review_notes`

## Disabled-By-Default Policy

Every future live source must start as:

```json
{
  "enabled": false,
  "manual_review_required": true,
  "attribution_required": true
}
```

A source can become eligible for a manual live dry run only after:

- source URL is public HTTPS
- source type is allowed
- publisher identity is clear
- fetch mode is documented
- request limits are documented
- robots or acceptable-use note is documented
- no login, paywall, private workspace, signed URL, or credential-bearing URL is required
- source passes `validate-topic-sources`
- source has a documented rollback or disable path

Disabled sources may remain in examples as documentation fixtures only. They must not be fetched by default.

## Future Disabled Source Examples

Future documentation-only examples may include:

- official company announcement pages
- model card hubs
- research paper feeds
- public code repositories
- public release and changelog pages
- public benchmark or evaluation pages
- regulatory and policy sources
- public security advisories
- credible technical news sources

These examples should demonstrate registry shape and review policy. They should not imply live fetching is active.

## Source Category Policies

### Official Company Announcement Pages

Useful because they provide primary-source release, availability, API, and product-change evidence.

- risk level: medium
- allowed fetch mode: official feed, official release page metadata, or manual snapshot
- manual review required: yes
- can support: release existence, stated availability, official positioning, changelog facts
- must not support alone: third-party benchmark interpretation, customer adoption claims, unstated performance comparisons

### Model Card Hubs

Useful because model cards often contain technical capability, safety, limitation, evaluation, and availability details.

- risk level: medium
- allowed fetch mode: official model card metadata or manually supplied snapshot
- manual review required: yes
- can support: model name, model family, release metadata, documented limitations, evaluation statements as written
- must not support alone: broad market impact, independent benchmark conclusions, claims not present in the model card

### Research Paper Feeds

Useful because papers can reveal new models, methods, evaluations, datasets, or safety findings.

- risk level: medium
- allowed fetch mode: public paper metadata, repository metadata, or manual DOI/arXiv-style entry review
- manual review required: yes
- can support: paper title, authorship, abstract-level contribution, publication timing, linked artifacts
- must not support alone: production availability, vendor roadmap claims, real-world deployment claims

### Public Code Repositories

Useful because releases, tags, changelogs, and README updates can show developer-facing changes.

- risk level: medium
- allowed fetch mode: repository release metadata, tag metadata, changelog metadata, or manual repository snapshot
- manual review required: yes
- can support: repository release, version tag, public changelog, linked model or tool artifact
- must not support alone: business impact, security posture, production readiness beyond documented release facts

### Public Release And Changelog Pages

Useful because they provide time-ordered product, API, and tooling changes.

- risk level: medium
- allowed fetch mode: public changelog feed, release page metadata, or manual snapshot
- manual review required: yes
- can support: feature availability, release date as stated, API or product change description
- must not support alone: user adoption, benchmark superiority, unstated pricing impact

### Public Benchmark Or Evaluation Pages

Useful because benchmark and evaluation pages can identify material model or system changes.

- risk level: high
- allowed fetch mode: official benchmark metadata or manual snapshot only
- manual review required: yes
- can support: benchmark entry existence, score as published, evaluation date if stated
- must not support alone: broad model superiority, real-world capability, safety conclusions outside the benchmark scope

### Regulatory And Policy Sources

Useful because regulation, standards, and official policy updates can materially affect deployment and compliance.

- risk level: medium
- allowed fetch mode: official public registry, official release page, official document metadata, or manual snapshot
- manual review required: yes
- can support: official document existence, publication date, jurisdiction, stated policy scope
- must not support alone: legal advice, compliance conclusions, enforcement predictions

### Public Security Advisories

Useful because advisories can identify vulnerabilities, mitigations, patches, or ecosystem risk.

- risk level: high
- allowed fetch mode: official advisory feed, public CVE-style metadata, repository security advisory metadata, or manual snapshot
- manual review required: yes
- can support: advisory existence, affected package/model/tool as stated, severity as published, mitigation as stated
- must not support alone: exploitability beyond advisory text, operational impact, unstated risk level

### Credible Technical News Sources

Useful for discovery and context when primary sources are not yet obvious.

- risk level: high
- allowed fetch mode: public article metadata or manual snapshot only
- manual review required: yes
- can support: secondary context, discovery lead, quoted public statements when attributable
- must not support alone: technical claims when official sources exist, benchmark conclusions, private roadmap claims, rumors

## Disallowed Sources

Future live-source discovery must reject or disable:

- login-required pages
- paywalled pages
- private social media pages
- personal accounts requiring authentication
- pages with secrets, signed URLs, access tokens, session IDs, or private query strings
- private repository files
- local machine paths
- raw private migration files
- screenshots
- DOCX exports
- Telegram exports
- HTML exports from private workflows
- unreviewed scraped social posts
- direct messages
- private groups or channels
- personal inboxes
- private docs or drives

These inputs must not be used as live-source registry entries or source observation inputs.

## Fetch Modes

Future fetch modes should be explicit. Recommended values:

- `disabled`
- `manual_snapshot`
- `official_feed`
- `official_page_metadata`
- `repository_release_metadata`
- `paper_metadata`
- `advisory_metadata`
- `regulatory_metadata`
- `news_metadata`

Initial examples should use `disabled` or `manual_snapshot`. Network-capable fetch modes should not become active until separate implementation and review phases.

## Rate-Limit And Timeout Policy

Every future live source must define conservative limits:

- `max_requests_per_run`: start at `1` for initial dry-run candidates
- `min_seconds_between_requests`: non-zero for any repeated source access
- `timeout_seconds`: short and bounded, recommended initial maximum of `10`
- `cache_ttl_minutes`: non-zero for network-capable modes
- `max_response_bytes`: recommended optional cap before storing metadata

If a source returns 401, 403, 408, 429, or 5xx, the scanner should fail closed for that source, record a safe unresolved note, and avoid aggressive retries.

## Future Validation Requirements

Future validators must enforce:

- every live source is public HTTPS
- every live source is disabled by default at first
- every live source has rate-limit metadata
- every live source declares expected update frequency
- every live source declares fetch mode and allowed fetch mode
- every live source has attribution metadata
- every live source has manual review required before publication
- every live source has robots and rate-limit notes
- every live source passes `validate-topic-sources`
- every live observation remains artifact-only in the first live dry run
- no generated outputs are committed
- no raw HTML is committed
- no automatic report publication occurs
- no Telegram, OpenAI API, image generation, or DOCX generation occurs in source discovery
- no private paths or secret-like values appear in registry, observations, artifacts, logs, or docs

## Future Implementation Phase Plan

Phase 49: create disabled live source registry example.

- documentation and JSON example only
- all live entries disabled by default
- no live fetch adapter
- no workflow changes

Phase 50: add source registry validation for live fields.

- validate new fields
- validate disabled-by-default policy
- validate rate-limit metadata
- validate fetch-mode values
- no network access

Phase 51: add fetch adapter interface with replay-only tests.

- interface and dependency-free adapters only
- no live workflow
- replay fixtures only
- no external API calls in tests

Phase 52: add recorded fixture parser tests.

- parse committed safe fixtures
- reject secrets and private paths
- test timeout/error classification without network

Phase 53: manual live dry-run workflow_dispatch, artifact only.

- manual trigger only
- approved disabled-to-enabled test source subset only after review
- upload artifacts only
- no commit, no Pages, no Telegram, no OpenAI, no image, no DOCX

Phase 54: manual artifact review.

- inspect generated candidates
- inspect source observations
- inspect ranking and dedup output
- document false positives and unsafe behavior

Phase 55 and later: consider schedule only after repeated safe manual runs.

- schedule requires separate approval
- first scheduled version must remain artifact-only
- publication and delivery stay separate

## Review Checklist

Before live registry entries are enabled, reviewers should confirm:

- source is public HTTPS
- source is attributable
- source is not paywalled or login-gated
- source has no secret-bearing URL
- source has correct `source_type` and `category_id`
- source has documented fetch mode
- source has conservative request limits
- source has cache TTL
- source has manual review required
- source has robots and rate-limit notes
- source has disallowed content rules
- source can be disabled quickly
- generated observations remain artifact-only
- no source candidate can publish a report automatically

## Non-Goals

This plan does not:

- create a live registry JSON file
- implement live fetching
- add a scheduled workflow
- modify GitHub Actions
- call external APIs
- fetch live web pages
- send Telegram messages
- call OpenAI APIs
- generate images
- create DOCX files
- deploy Pages
- publish reports
- migrate historical private reports
