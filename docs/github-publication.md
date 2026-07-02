# GitHub Publication Plan

This repository is prepared for future publication as `LeombE/ai-signal-brief`.

Phase 11A is a final pre-push audit and command-preparation phase only. It does not create a GitHub remote, create a GitHub repository, push commits, enable GitHub Pages, add production delivery, configure API keys, or migrate historical reports.

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
LeombE/ai-signal-brief
```

The current local repository should remain the source for a clean first push only after manual review.

## Required Pre-Publication Checks

Before creating or pushing to the public repository:

1. Confirm `git branch --show-current` returns `main`.
2. Confirm `git status --short` is empty.
3. Confirm `git remote -v` is empty before remote setup.
4. Run the full local verification sequence from `README.md`.
5. Confirm `python -m ai_signal_brief public-readiness` returns PASS.
6. Confirm no secrets, local env values, or tokens are present.
7. Confirm no private migration source content is present.
8. Confirm generated ignored outputs are not tracked.
9. Confirm no Telegram token is present.
10. Confirm no OpenAI API key is present.
11. Confirm no chat identifier is present.
12. Confirm no historical reports have been migrated without review.
13. Confirm the intended owner and repository name are `LeombE/ai-signal-brief`.

## First Push Checklist

Complete these steps manually before the first push:

1. Create an empty GitHub repository named `ai-signal-brief` under `LeombE`.
2. Do not initialize the GitHub repository with a README, license, gitignore, or workflow files.
3. Re-run the final local audit commands.
4. Add the remote only after the empty repository exists.
5. Push `main` only after the local audit remains clean.
6. Check the GitHub Actions CI run after the first push.
7. Do not enable GitHub Pages until a later approved phase.

## Phase 11B Command Template

Run these only after explicit approval:

```powershell
git remote add origin https://github.com/LeombE/ai-signal-brief.git
git remote -v
git push -u origin main
```

## First Push Boundary

The first push is intentionally outside Phase 11A. It should happen only after explicit approval and one final public readiness pass.
