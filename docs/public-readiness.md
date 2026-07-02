# Public Readiness Audit

Phase 9 adds a stdlib-only audit for checking whether tracked repository files are ready for a public GitHub release.

The audit is offline. It does not fetch sources, call APIs, generate images, send Telegram messages, create DOCX files, create GitHub Actions, create remotes, or push to GitHub.

## Command

```powershell
python -m ai_signal_brief public-readiness
```

## Scope

The command audits tracked Git files only. Generated ignored outputs are not part of the public readiness surface unless they are accidentally tracked.

Intentional invalid fixtures are allow-listed narrowly by file path and check category so validation tests can keep negative examples without making the production repository fail readiness.

## Checks

The audit checks for:

- token-like or key-like values
- chat identifier assignments
- env value assignments
- private local paths
- private migration markers
- mistaken prompt markers
- legacy private builder markers
- generated output paths tracked by Git
- required public docs
- required technical docs
- required schemas
- required examples
- documented core CLI commands

## Output Contract

On success:

```text
Public readiness PASS
Tracked files checked: N
```

On failure:

```text
Public readiness FAIL
Tracked files checked: N
Failed checks:
- check_name: path
```

The command prints check names and paths only. It must not print secret values.