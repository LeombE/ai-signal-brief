# GitHub Publication Plan

This repository has been pushed to GitHub as `LeombE/ai-signal-brief`.

Phase 12 records the post-push status only. It does not change repository visibility, enable GitHub Pages, add deployment workflows, configure API keys, connect Telegram delivery, generate images, create DOCX files, or migrate historical reports.

## Current Repository Status

Repository URL:

```text
https://github.com/LeombE/ai-signal-brief
```

Current status:

- repository has been pushed to GitHub
- repository visibility is currently Private
- latest GitHub Actions CI run is passing on commit `54bffa7`
- offline validation commands exist
- offline render, archive, site, and readiness checks exist
- GitHub Actions CI runs offline checks only
- GitHub Pages is not enabled
- no Telegram delivery is configured
- OpenAI Image API is not configured
- no secrets are required for the current offline workflow
- historical reports have not been migrated

## Publication Boundary

Changing repository visibility from Private to Public is intentionally outside Phase 12. Do it only after a final manual review and explicit approval.

## Required Checks Before Making Public

Before changing repository visibility from Private to Public:

1. Confirm `git branch --show-current` returns `main`.
2. Confirm `git status --short` is empty.
3. Confirm `git remote -v` points to `https://github.com/LeombE/ai-signal-brief.git`.
4. Confirm the latest GitHub Actions CI run is passing.
5. Run `python -m ai_signal_brief public-readiness` locally and confirm PASS.
6. Run `python -m unittest discover -s tests` locally and confirm OK.
7. Confirm no secrets, local env values, tokens, or API keys are present.
8. Confirm no private migration source content is present.
9. Confirm generated ignored outputs are not tracked.
10. Confirm no Telegram token is present.
11. Confirm no OpenAI API key is present.
12. Confirm no chat identifier is present.
13. Confirm no historical reports have been migrated without review.
14. Confirm GitHub Pages remains disabled unless separately approved.
15. Confirm no deployment workflow, Telegram workflow, or OpenAI Image API workflow is active.
16. Confirm the intended public owner and repository name are `LeombE/ai-signal-brief`.

## Post-Push Notes

The repository is ready for final visibility review, not production operation. The current project is an offline, public-safe skeleton and validation pipeline. Future live ingestion, Pages deployment, Telegram delivery, image generation, DOCX generation, and historical migration must be added in later approved phases.
