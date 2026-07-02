# GitHub Publication Plan

This repository is prepared for future publication as `spaceleoch/ai-signal-brief`.

Phase 10 adds publication preparation only. It does not create a GitHub remote, push commits, enable GitHub Pages, add production delivery, configure API keys, or migrate historical reports.

## Publication Status

Current status:

- local public-ready skeleton exists
- offline validation commands exist
- offline render, archive, site, and readiness checks exist
- GitHub Actions CI definition exists for offline checks
- no GitHub remote is required yet
- no secrets are required yet
- no Telegram delivery is configured
- no OpenAI Image API workflow is configured
- historical reports have not been migrated

## Intended Public Repository

Target repository:

```text
spaceleoch/ai-signal-brief
```

The current local repository should remain the source for a clean first push only after manual review.

## Required Pre-Publication Checks

Before creating or pushing to the public repository:

1. Confirm `git remote -v` is empty or intentionally configured.
2. Run the full local verification sequence from `README.md`.
3. Confirm `python -m ai_signal_brief public-readiness` returns PASS.
4. Confirm no secrets, local env values, or tokens are present.
5. Confirm no private migration source content is present.
6. Confirm generated ignored outputs are not tracked.
7. Confirm no Telegram token is present.
8. Confirm no OpenAI API key is present.
9. Confirm no historical reports have been migrated without review.
10. Confirm the intended owner and repository name are `spaceleoch/ai-signal-brief`.

## First Push Boundary

The first push is intentionally outside Phase 10. It should happen only after explicit approval and one final public readiness pass.
