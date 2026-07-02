# Release Checklist

Use this checklist before creating the public GitHub repository or pushing local commits.

## Repository Target

- [ ] Confirm public owner and repository name: `spaceleoch/ai-signal-brief`.
- [ ] Confirm no GitHub remote is configured unless explicitly intended.
- [ ] Confirm the current branch is `main`.
- [ ] Confirm the working tree is clean.

## Safety

- [ ] Confirm `python -m ai_signal_brief public-readiness` returns PASS.
- [ ] Confirm no secrets are present.
- [ ] Confirm no local env values are present.
- [ ] Confirm no private migration source content is present.
- [ ] Confirm no generated ignored outputs are tracked.
- [ ] Confirm no Telegram token is present.
- [ ] Confirm no OpenAI API key is present.
- [ ] Confirm no chat identifier is present.
- [ ] Confirm no mistaken prompt references are present.
- [ ] Confirm no historical reports have been migrated yet.

## Local Verification

Run the same offline command sequence used by CI:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m compileall src
python -m ai_signal_brief --version
python -m ai_signal_brief doctor
python -m ai_signal_brief validate-report examples/report.example.json
python -m ai_signal_brief validate-run examples/run.example.json
python -m ai_signal_brief validate-sources config/sources.example.json
python -m ai_signal_brief quality-gate --report examples/report.example.json --run examples/run.example.json --sources config/sources.example.json
python -m ai_signal_brief archive-report --report examples/report.example.json --run examples/run.example.json --sources config/sources.example.json --out outputs/archive-example
python -m ai_signal_brief build-site --archive outputs/archive-example --out outputs/site-example
python -m ai_signal_brief public-readiness
python -m unittest discover -s tests
```

## First Push Checklist

- [ ] Create an empty GitHub repository at `spaceleoch/ai-signal-brief`.
- [ ] Do not initialize the remote repository with generated files.
- [ ] Run `git branch --show-current` and confirm `main`.
- [ ] Run `git status --short` and confirm no output.
- [ ] Run `git remote -v` and confirm no existing remote before setup.
- [ ] Run `python -m ai_signal_brief public-readiness` and confirm PASS.
- [ ] Run `python -m unittest discover -s tests` and confirm OK.
- [ ] Add the GitHub remote only after the empty repository exists.
- [ ] Push `main` only after explicit approval.
- [ ] Review the first GitHub Actions CI run.

## Phase 11B Commands

Run these only after explicit approval:

```powershell
git remote add origin https://github.com/spaceleoch/ai-signal-brief.git
git remote -v
git push -u origin main
```

## Publication Boundary

Do not push until publication is explicitly approved after the checklist passes.
