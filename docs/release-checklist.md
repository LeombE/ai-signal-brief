# Release Checklist

Use this checklist while maintaining the public GitHub repository.

## Repository Status

- [ ] Confirm public owner and repository name: `LeombE/ai-signal-brief`.
- [ ] Confirm repository URL: `https://github.com/LeombE/ai-signal-brief`.
- [ ] Confirm repository visibility is public.
- [ ] Confirm the current branch is `main`.
- [ ] Confirm the working tree is clean.
- [ ] Confirm `origin` points to `https://github.com/LeombE/ai-signal-brief.git`.

## CI And Local Verification

- [ ] Confirm latest GitHub Actions CI run is passing.
- [ ] Run `python -m ai_signal_brief public-readiness` and confirm PASS.
- [ ] Run `python -m unittest discover -s tests` and confirm OK.

## Safety

- [ ] Confirm no secrets are present.
- [ ] Confirm no local env values are present.
- [ ] Confirm no private migration source content is present.
- [ ] Confirm no generated ignored outputs are tracked.
- [ ] Confirm no Telegram token is present.
- [ ] Confirm Telegram delivery is not connected.
- [ ] Confirm no OpenAI API key is present.
- [ ] Confirm OpenAI Image API is not configured.
- [ ] Confirm no chat identifier is present.
- [ ] Confirm no mistaken prompt references are present.
- [ ] Confirm no historical reports have been migrated yet.

## Feature Boundaries

- [ ] Confirm GitHub Pages is not enabled.
- [ ] Confirm no deployment workflow exists.
- [ ] Confirm no Telegram workflow exists.
- [ ] Confirm no image generation workflow exists.
- [ ] Confirm no DOCX generation workflow exists.

## Local Verification Command

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

## Public Repository Boundary

Do not add Pages, deployment workflows, Telegram delivery, OpenAI API usage, image generation, DOCX generation, or historical reports until each capability is separately approved and validated.
