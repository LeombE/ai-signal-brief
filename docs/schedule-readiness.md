# Schedule Readiness

Scheduling is not approved yet. This document defines the gates that must pass before a future scheduled topic-discovery workflow can even be proposed.

The current approved state is no-network and manual. `discover-topics-live-dry-run` reads disabled live registry metadata only and writes reviewable artifacts under ignored `outputs/` paths.

## Current Boundary

The project must remain in this state until a later phase separately approves more capability:

- no live HTTP fetching
- no `discover-topics-live` command
- no scheduled workflow
- no production Pages deployment
- no Telegram delivery
- no OpenAI API usage
- no image generation
- no DOCX generation
- no automatic report publication
- no generated outputs committed

## Required Gates Before Any Schedule Proposal

All gates must pass before schedule work is considered:

- several manual dry-runs have succeeded on different dates or source subsets
- every generated artifact has been manually reviewed
- `public-readiness` passes after each dry-run
- `git status --short` confirms generated outputs are not staged
- `git ls-files outputs` confirms generated outputs are not tracked
- live source registry entries remain `enabled: false` until separately approved
- live source registry entries remain `fetch_mode: disabled` until separately approved
- no private paths, tokens, chat IDs, API keys, `.env` values, or private migration markers appear
- documentation does not claim real live fetching occurred
- no generated topic is promoted to a report without manual source review
- no Pages, Telegram, OpenAI, image, DOCX, or production publication behavior is introduced
- Topic Scan Preview remains `workflow_dispatch` only
- any future scheduled workflow is approved in a separate phase

## Schedule-Readiness Review Checklist

Before proposing any schedule, record evidence for:

- latest CI is green
- workflow remains manual-only
- no schedule exists
- live dry-run remains no-network
- output stays under `outputs/`
- topics remain unresolved and review-required
- source attribution is present
- confidence and uncertainty fields are present
- duplicate or related topics are marked or clearly reviewable
- unsafe or private sources are rejected
- generated outputs are not committed
- no Telegram, OpenAI API, image generation, DOCX generation, Pages production deployment, or report publication behavior exists

## Risk Controls

Use these controls to avoid accidental production behavior:

- accidental schedule enablement: require separate approval and review workflow diffs before any schedule is added
- metadata dry-run confused with live fetching: describe dry-run output as no-network, metadata-only, and artifact-only
- generated outputs committed: run `git status --short` and `git ls-files outputs` before every commit
- unreviewed topics published: keep all candidates unresolved and review-required until human source review is complete
- accidental external side effects: do not add Telegram, OpenAI, image, DOCX, Pages production, or live HTTP behavior in schedule-readiness phases
- source registry enabled too early: keep `enabled: false` and `fetch_mode: disabled` until a separate live-fetch approval phase

## Future Workflow Shape

A future schedule must not be the next step. The safe order is:

1. local manual dry-run review
2. documentation of review results
3. optional `workflow_dispatch` artifact-only preview, still no schedule
4. repeated manual artifact review
5. separate schedule proposal only after review evidence is stable

Any future workflow must upload artifacts only at first. It must not deploy Pages, send Telegram, call OpenAI, generate images, create DOCX, publish reports, or enable live fetching without separate approval.