# Live Source Discovery Readiness

## Status

Live-source discovery is not implemented. This document defines requirements, safety gates, and future phase boundaries for a possible live-source topic discovery mode.

The current project supports offline topic source validation, offline topic candidate validation, offline ranking, offline mock discovery, a replay-only fetch adapter for local safe fixtures, and a manual GitHub Actions Topic Scan Preview workflow that uses local fixture observations only. Future live-source registry extension fields and disabled-by-default source policy are documented in `docs/live-source-registry-extension-plan.md`; the future fetch adapter interface plan is documented in `docs/live-fetch-adapter-interface-plan.md`; the public-safe disabled example registry is `config/topic_sources.live.example.json`.

GitHub Actions CI for commit `85ec975 Add replay-only fetch adapter skeleton` was manually confirmed green in the GitHub UI. That result verifies the replay-only adapter path and local fixture checks; it does not enable live discovery, live HTTP fetching, scheduling, deployment, Telegram, OpenAI API usage, image generation, or DOCX generation.

GitHub Actions CI for commit `43d2344 Remove urllib imports from validation helpers` was manually confirmed green in the GitHub UI. That result verifies the no-urllib validation-helper safety fix: `urllib.parse` imports were removed while local HTTPS/source validation remains available. It does not enable live discovery, live HTTP fetching, scheduling, deployment, Telegram, OpenAI API usage, image generation, DOCX generation, or production Pages deployment.

GitHub Actions CI for commit `aa173c9 Add no-network live source dry-run` was manually confirmed green in the GitHub UI. That result verifies the `discover-topics-live-dry-run` path: it reads disabled live registry metadata only, requires artifact-only and metadata-only flags, writes unresolved review-required topic candidates under `outputs/`, and does not add `discover-topics-live`, live HTTP fetching, workflow changes, scheduling, deployment, Telegram, OpenAI API usage, image generation, DOCX generation, or production Pages deployment.

No schedule, live fetching, Telegram delivery, OpenAI API usage, image generation, DOCX generation, production Pages deployment, or automatic report publication is active. `discover-topics-live` does not exist; the current dry-run command is `discover-topics-live-dry-run` and remains no-network.

## Objective

Live-source discovery should eventually observe approved public AI sources and produce a reviewable topic-candidate artifact. Its purpose is to help a human reviewer identify possible report topics.

It must not publish reports, deploy production Pages, send Telegram messages, generate images, create DOCX files, or convert candidates into reviewed reports automatically.

## Boundary Definitions

Mock discovery:

- uses committed local fixture observations only
- performs no network access
- writes topic candidates under ignored `outputs/` paths
- supports CI and manual preview validation

Live source observation:

- would fetch or read approved public source metadata in a future phase
- would produce low-level source observations
- would preserve timestamps, source IDs, URLs, and retrieval metadata
- would remain artifact-only at first

Topic candidate generation:

- aggregates source observations into possible review topics
- may include uncertain, duplicate, rejected, or quiet-day candidates
- does not create a canonical report
- requires validation, ranking, dedup review, and manual artifact inspection

Reviewed report publication:

- uses manually reviewed English canonical report JSON
- requires source and claim review
- requires quality gates and public-readiness checks
- remains separate from topic discovery

## Minimum Source Safety Requirements

Every future live source must satisfy all of these requirements before observation is enabled:

- public HTTPS URL
- no login requirement
- no paywall requirement
- no private workspace or private file URL
- no secret-bearing URL, query string, header, cookie, or token
- clear publisher identity
- clear attribution path
- compatible source type
- documented update cadence
- documented rate-limit or acceptable-use notes
- documented fetch mode
- explicit enabled/disabled state in the registry

The source registry must remain official-source-first. Secondary coverage can help discover a topic, but technical claims should prefer official announcements, papers, model cards, repositories, advisories, changelogs, or regulatory sources when available.

## Allowed Source Types

Allowed source types should stay compatible with the canonical report schema:

- `official`
- `paper`
- `repository`
- `regulatory`
- `news`
- `social`
- `other`

Allowed source categories may include:

- official company announcements
- official blogs and release notes
- model cards
- research papers and technical reports
- public repositories and release notes
- benchmark or evaluation releases
- security advisories
- standards, policy, and regulatory sources
- credible technical news used for context

## Disallowed Source Types

Future live-source discovery must reject or disable:

- private files or local paths
- login-only pages
- paywalled content
- private workspaces
- private chat exports
- private mailing lists
- personal inboxes
- direct message content
- private social pages
- scraped social/private pages
- URLs containing secrets, tokens, credentials, session IDs, or private query parameters
- raw historical report exports
- screenshots, DOCX, HTML exports, or legacy generated artifacts as source inputs
- untrusted mirrors without attribution
- content that cannot be attributed to a public publisher

## Fetch Policy

A future fetch adapter must be conservative by default.

Required policy:

- use explicit allowlisted sources from the topic source registry
- use public HTTPS only
- use a documented user-agent string
- use short timeouts
- use per-source observation limits
- use total scan observation limits
- cache fetched metadata under ignored `outputs/cache/`
- never commit raw HTML, response bodies, cache files, or generated outputs by default
- prefer official feeds, release pages, repositories, and structured metadata over broad scraping
- respect robots, terms, rate limits, and publisher usage expectations
- fail closed when a source is unclear, unavailable, private, or rate limited

The first live test should be artifact-only. It should upload generated topic candidates for manual inspection and should not commit them.

## Robots, Rate-Limit, And Caching Policy

Future implementation must define source-level fetch limits before any networked workflow runs.

Minimum requirements:

- per-request timeout
- per-source maximum observations
- per-run maximum observations
- cache TTL or cache key policy
- retry count of zero or a small bounded value
- backoff behavior for transient failure
- safe behavior for HTTP 401, 403, 404, 408, 429, and 5xx responses
- clear logging without secrets or response bodies
- no raw HTML committed to Git

If rate limits are hit, the scanner should mark the source as unavailable for that run and continue only if enough other safe sources remain. It should not retry aggressively.

## Delivery And Generation Boundaries

Future live discovery must preserve these boundaries:

- no Telegram delivery before the reviewed report Pages URL is verified
- no OpenAI API usage before a dedicated GitHub Secret, cost controls, and review policy exist
- no image generation before a dedicated secret, cost controls, artifact policy, and manual approval exist
- no DOCX generation in topic discovery
- no production Pages publication from topic candidates
- no automatic reviewed report creation from live discovery
- no historical raw report publishing
- no private migration source copying

## Manual Review Gate Before Publication

A live-discovered topic candidate can only become a reviewed report after manual review.

Minimum review gates:

- source URLs reviewed
- publisher attribution reviewed
- source IDs resolved
- claim/source mapping reviewed
- ranking and dedup behavior reviewed
- uncertainty notes reviewed
- English report wording reviewed
- no private paths
- no secrets
- no raw historical exports
- quality gate passes
- public-readiness passes
- generated static page manually inspected before publication

## Artifact-Only First Live Test Strategy

The first future live-source test should be manual-only and artifact-only.

Expected behavior:

1. Run by `workflow_dispatch` only.
2. Use approved registry entries only.
3. Fetch bounded metadata from public HTTPS sources only.
4. Write observations and topic candidates under ignored `outputs/` paths.
5. Validate generated topic candidates.
6. Rank generated topic candidates with explanations.
7. Upload a short-lived artifact.
8. Require manual artifact inspection.
9. Do not publish reports.
10. Do not deploy Pages.
11. Do not send Telegram messages.
12. Do not call OpenAI APIs.
13. Do not generate images.
14. Do not create DOCX files.
15. Do not add a schedule.

## Future CLI Shape

Future CLI command, not implemented:

```powershell
python -m ai_signal_brief discover-topics-live-dry-run --date YYYY-MM-DD --sources config/topic_sources.live.example.json --out outputs/topic-candidates-live-dry-run/YYYY-MM-DD.json --artifact-only --metadata-only
```

Expected future arguments:

- `--date YYYY-MM-DD`
- `--sources config/topic_sources.example.json`
- `--out outputs/topic-candidates-live/YYYY-MM-DD.json`
- `--dry-run`
- `--cache outputs/cache/`
- `--timeout-seconds N`
- `--max-observations N`
- `--source-id SOURCE_ID` for narrow manual tests
- `--no-cache` for explicit local debugging only

The command must validate configuration before fetching and must reject unsafe output paths.

## Future Implementation Phases

Future phases should be explicit and separately approved:

1. Add live source registry examples with all live entries disabled by default, following `docs/live-source-registry-extension-plan.md`.
2. Add a safe fetch adapter interface without enabling any live workflow.
3. Add HTTP timeout, user-agent, response-size, and error-handling policy.
4. Add cache layer under ignored `outputs/cache/`.
5. Add fetch fixtures and replay tests with no network requirement.
6. Keep `discover-topics-live-dry-run` as the no-network metadata-only validation path; do not add `discover-topics-live` without separate approval.
7. Only after separate approval, consider a manual `workflow_dispatch` live-source dry run that uploads artifacts only.
8. Review artifacts manually.
9. Only later consider schedule.
10. Only after reviewed reports and Pages URLs are verified, consider delivery integrations.

## Safety Gates

Required gates before and after any future live run:

- `validate-topic-sources`
- generated candidate validation
- `rank-topics --explain`
- `public-readiness`
- unit tests
- no private paths
- no secrets
- no raw HTML committed
- no generated outputs committed
- source observation count limits
- timeout limits
- safe cache location under ignored `outputs/cache/`
- manual artifact inspection
- manual review before report candidate creation

Failure to pass any gate must block publication.

## Failure Modes And Safe Behavior

Expected failure modes:

- source unavailable
- source returns 401 or 403
- source returns 429
- source returns 5xx
- timeout
- invalid or missing timestamp
- duplicate observation
- weak source quality
- private URL detected
- secret-like marker detected
- unsafe output path
- over observation limit
- cache read or write failure

Safe behavior:

- fail closed for unsafe sources
- mark uncertain items unresolved
- produce a quiet-day or partial artifact only when validation allows it
- do not publish reports
- do not commit generated files
- do not retry aggressively
- do not expose response bodies or secret-like strings in logs
- require manual follow-up for unresolved sources

## Rollback Plan

If a future live-source preview produces unsafe, noisy, or incorrect output:

1. Disable the workflow or keep it manual-only.
2. Remove or disable the source registry entry.
3. Delete generated artifacts from GitHub Actions if needed.
4. Revert the implementation commit if code behavior is unsafe.
5. Keep production Pages and Telegram disconnected.
6. Do not promote any candidate from the failed run.
7. Document the failure mode before another attempt.

## Future Review Checklist

Before live discovery is enabled, reviewers should cover these roles:

- source-reviewer: source list, attribution, source type, official-source-first behavior
- security-reviewer: secrets, private paths, unsafe URLs, logging, cache behavior
- ranking/dedup-reviewer: scoring, duplicate grouping, unresolved topics, quiet-day behavior
- scheduler-reviewer: no schedule before approval, safe cron only after manual success
- editorial-reviewer: no topic candidate treated as a final report claim
- test-reviewer: fixture coverage, replay tests, no-network CI, failure-mode tests

## Exit Criteria Before Scheduling

A scheduled live-source workflow must not be considered until all of these are true:

- manual live dry run exists and passes
- artifact-only run has been inspected
- source registry entries are reviewed
- fetch policy is documented and tested
- replay tests pass without network access
- public-readiness passes
- generated artifacts contain no private paths or secrets
- at least one reviewed report flow has been completed manually
- production Pages URL behavior is verified
- rollback plan is documented
- schedule receives separate approval
