# Release Checklist

Use this checklist before creating the public GitHub repository or pushing local commits.

## Repository Target

- [ ] Confirm public owner and repository name: `spaceleoch/ai-signal-brief`.
- [ ] Confirm no GitHub remote is configured unless explicitly intended.
- [ ] Confirm the current branch is ready for publication.

## Safety

- [ ] Confirm `python -m ai_signal_brief public-readiness` returns PASS.
- [ ] Confirm no secrets are present.
- [ ] Confirm no local env values are present.
- [ ] Confirm no private migration source content is present.
- [ ] Confirm no generated ignored outputs are tracked.
- [ ] Confirm no Telegram token is present.
- [ ] Confirm no OpenAI API key is present.
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

## Publication Boundary

Do not push until publication is explicitly approved after the checklist passes.
