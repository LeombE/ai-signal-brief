# Final Human Review Checklist: 2026-06-24 Reviewed Report Candidate

## Scope

This checklist is for Draft PR #1, `Add 2026-06-24 Reviewed Report Candidate`.

The candidate remains draft content. It is not merged, not published to production Pages, and not connected to any delivery automation.

## Candidate Files To Review

- `reports-reviewed/2026/06/24/report.json`
- `reports-reviewed/2026/06/24/run.json`
- `reports-reviewed/2026/06/24/review.md`
- `reports-reviewed/2026/06/24/pr-draft.md`
- `reports-reviewed/2026/06/24/pr-review-comment.md`

## Final Source URL Review

Reviewer should confirm:

- `anthropic-claude-tag` is still public, attributable, and relevant to the Claude Tag claims.
- `mistral-ocr-4` is still public, attributable, and relevant to the OCR 4 claims.
- `qwen-36-27b-hf` is still public, attributable, and relevant to the Qwen model-card claims.
- `openai-daybreak` is still public, attributable, and relevant to the Daybreak claims.
- `openai-patch-the-planet` is still public, attributable, and relevant to the Patch the Planet claims.
- `xai-goal` is still public, attributable, and relevant to the `/goal` claims.

## Claim And Source ID Mapping Review

Reviewer should confirm:

- Every material claim in `report.json` has at least one valid `source_id`.
- Every story-level `source_id` resolves to an entry in the report source list.
- Every claim-level `source_id` resolves to an entry in the report source list.
- No story makes a stronger factual claim than the listed sources support.
- No benchmark, pricing, or operational metric is added or emphasized without a separate source review.

## Qwen Timing Uncertainty Review

Reviewer should confirm:

- Qwen remains framed as a cautious model-card update.
- The candidate does not describe Qwen3.6-27B as a verified same-day launch.
- Publication timing remains unresolved unless a stable public source is added later.

## English Editorial Review

Reviewer should confirm:

- The report is clear, concise, and English-only.
- Story status and importance rationale are understandable.
- Analysis text is conservative and avoids promotional wording.
- Unresolved items remain visible to a future reviewer.

## Draft And Publication Disclosure Review

Reviewer should confirm:

- `candidate_draft` is visible in provenance or review notes.
- `not_published` is visible in provenance or review notes.
- Manual review requirement remains visible.
- The candidate does not imply production publication, deployment, or delivery.

## Browser Visual Inspection

Reviewer should generate and inspect the local static page before any later publication step:

- Run `python -m ai_signal_brief dry-run-reviewed-report --date 2026-06-24 --strict`.
- Inspect the generated local homepage and dated report page under `outputs/reviewed-site-dry-run/2026/06/24/`.
- Confirm title, report date, generated time, timezone, top story summary, ranked stories, claims, source references, source list, and provenance are readable.
- Confirm generated outputs remain under `outputs/` and are not committed.

## Security Review

Reviewer should confirm:

- No private local paths are present.
- No secrets, tokens, credential-like values, or API keys are present.
- No raw Chinese report text is copied into the candidate.
- No private source files, screenshots, generated office documents, generated web exports, delivery exports, or old builder scripts are copied into the candidate.
- No mistaken prompt references are present.
- `public-readiness` passes after any further edits.

## Non-Action Checks

Reviewer should confirm:

- No Telegram delivery is connected or triggered.
- No OpenAI API call is configured or triggered.
- No image generation is configured or triggered.
- No DOCX creation is configured or triggered.
- No production Pages publication is triggered.
- No workflow or production automation is changed by this candidate.

## Decision Options

Choose one of the following after final human review:

- Keep Draft open: use this if review is incomplete or any uncertainty remains.
- Revise candidate: use this if source mapping, wording, visual output, or safety review needs changes.
- Later mark ready for review: use this only after final human review and local validation pass.
- Do not merge yet: default decision until the candidate is explicitly approved in a later phase.

## Current Recommendation

Keep Draft open. Continue human editorial and source review later. Do not merge yet.