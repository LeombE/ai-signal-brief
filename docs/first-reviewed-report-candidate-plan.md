# First Reviewed Report Candidate Plan

This document defines how to select and audit the first manually reviewed report candidate for future publication. It is a planning document only. It does not migrate historical reports, create `reports-reviewed/YYYY/MM/DD/` content, publish real report data to GitHub Pages, send Telegram messages, call external APIs, generate images, create DOCX files, or enable production automation.

## Recommended First Candidate

Recommended candidate date: `2026-06-24`.

Reason: use one recent historical daily AI report as the first candidate because it represents the latest known private migration output and is expected to have enough story density to exercise the reviewed-report workflow, source mapping, archive generation, static-site rendering, and rollback process.

This recommendation is not approval to copy source material. The candidate date is only a target for manual review and reconstruction into sanitized English canonical files in a later phase.

## Phase Boundary

Do not do any of the following in this phase:

- Do not copy raw Chinese legacy daily-report content directly.
- Do not copy DOCX files, HTML exports, screenshots, Telegram exports, old builders, private assets, or cache files.
- Do not copy private local paths.
- Do not copy credentials, bot credentials, chat identifiers, API credentials, or environment files.
- Do not create `reports-reviewed/YYYY/MM/DD/` content.
- Do not publish real report data to GitHub Pages.
- Do not change workflow triggers or add production automation.

## Candidate Selection Criteria

Choose the first candidate only if it satisfies these reviewability criteria:

- Public source availability: each material story can be traced to public, attributable URLs.
- Claim/source traceability: every material claim can be mapped to one or more `source_ids`.
- Source quality: official sources, papers, repositories, regulatory material, or reputable public reporting are available.
- English rewrite feasibility: old prose can be rewritten into clear English without copying raw text.
- Deduplication clarity: recurring stories can be marked as `new`, `update`, `follow_up`, or `correction` without ambiguity.
- No private information: the candidate does not require private files, screenshots, local paths, or private assets.
- No unverifiable claims: unsupported claims can be removed or marked appropriately.
- Manageable story count: the candidate can be reviewed manually without creating an oversized first migration.
- Static page suitability: the final report can render cleanly in the static site with visible sources and claim references.

## Manual Candidate Audit Checklist

Before creating any real reviewed report folder in a later phase, complete this checklist for the selected candidate:

- [ ] Source URLs reviewed.
- [ ] Every material claim mapped to valid `source_ids`.
- [ ] Old Chinese prose rewritten into English.
- [ ] Story status reviewed.
- [ ] Importance score reviewed.
- [ ] No private paths.
- [ ] No secrets.
- [ ] No bot credentials, chat identifiers, or API credentials.
- [ ] No old raw migration artifacts.
- [ ] No DOCX files, HTML exports, screenshots, Telegram exports, or old builders copied.
- [ ] `report.json` passes `validate-report`.
- [ ] `run.json` passes `validate-run`.
- [ ] `quality-gate` passes.
- [ ] `dry-run-reviewed-report` passes.
- [ ] Generated static page manually reviewed.

## Source Review Procedure

For the selected candidate, reconstruct source records manually instead of copying raw migration output.

For each source:

1. Open the public source URL manually.
2. Confirm the publisher, title, publication date, and source type.
3. Prefer official sources when available.
4. Use news or social sources only when they add context that cannot be sourced from official material.
5. Record source metadata in canonical `report.json` format.
6. Remove claims that cannot be supported by the selected sources.

## Claim And Story Review Procedure

For each story:

1. Decide whether the story is `new`, `update`, `follow_up`, or `correction`.
2. Assign an importance score from 1 to 5.
3. Write a short importance rationale.
4. Rewrite the story in English from reviewed facts, not by translating or copying raw prose.
5. Create claim objects for material claims.
6. Map every claim to valid `source_ids`.
7. Remove duplicate or stale items.
8. Confirm that the rendered static page will be understandable without private context.

## Future Branch Strategy

When implementation is approved in a later phase, use a dedicated branch for the first candidate:

```text
candidate/2026-06-24-reviewed-report
```

Future branch workflow:

1. Create the candidate branch.
2. Prepare `reports-reviewed/2026/06/24/report.json` on that branch only.
3. Prepare `reports-reviewed/2026/06/24/run.json` on that branch only.
4. Prepare `reports-reviewed/2026/06/24/review.md` on that branch only.
5. Run local validation.
6. Run `dry-run-reviewed-report` locally.
7. Inspect ignored archive and static-site output under `outputs/`.
8. Open a pull request only after local validation passes.
9. Do not merge until manual review is complete.

## Required Future Commands

These commands are for a later candidate branch, not this phase:

```powershell
python -m ai_signal_brief validate-report reports-reviewed/2026/06/24/report.json
python -m ai_signal_brief validate-run reports-reviewed/2026/06/24/run.json
python -m ai_signal_brief validate-sources config/sources.example.json
python -m ai_signal_brief quality-gate --report reports-reviewed/2026/06/24/report.json --run reports-reviewed/2026/06/24/run.json --sources config/sources.example.json
python -m ai_signal_brief dry-run-reviewed-report --date 2026-06-24 --strict
python -m ai_signal_brief public-readiness
python -m unittest discover -s tests
```

## Rollback Plan

Do not merge or publish the candidate if any check fails.

Rollback options for a later candidate branch:

- abandon the candidate branch before merge
- remove the candidate commit before opening a pull request
- revert the candidate commit if it was merged prematurely
- keep the current sample GitHub Pages preview unchanged until the candidate is approved
- keep Telegram delivery disconnected until a reviewed Pages URL is verified in a later phase

## Approval Gate For Future Migration

A future phase may create the first real reviewed report only after this plan is accepted and the candidate branch is explicitly approved. The first candidate must remain manually reviewed, English, source-backed, and public-safe before it can be considered for production Pages publication.