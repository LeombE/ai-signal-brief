# Topic Scan Preview Workflow

`Topic Scan Preview` is a manual GitHub Actions workflow for the offline mock topic discovery pipeline.

Workflow file:

```text
.github/workflows/topic-scan-preview.yml
```

## Trigger

The workflow uses `workflow_dispatch` only. It does not run on push, pull request, schedule, or any automatic event.

## Permissions

The workflow uses read-only repository permissions:

```yaml
permissions:
  contents: read
```

## What It Does

The workflow:

1. Checks out the repository.
2. Sets up Python.
3. Runs `python -m compileall src`.
4. Validates `config/topic_sources.example.json`.
5. Runs offline mock topic discovery with `tests/fixtures/topic_observations.valid.json`.
6. Writes generated output to `outputs/topic-candidates/${{ github.run_id }}/topic-candidates.json`.
7. Validates the generated topic candidate JSON.
8. Runs offline ranking with `--explain`.
9. Uploads `outputs/topic-candidates/${{ github.run_id }}/` as `topic-candidates-preview`.

Artifact retention is 7 days.

## What It Does Not Do

The workflow does not:

- fetch live sources
- scrape websites
- call external news APIs
- publish reports
- deploy GitHub Pages
- send Telegram messages
- call OpenAI APIs
- generate images
- create DOCX files
- commit generated outputs
- schedule automation
- migrate historical reports
- read private migration folders

## Artifact Boundary

Generated topic candidates are preview artifacts only. They are not committed to Git and they are not production reports.

Reviewers should download the artifact from a manual workflow run and inspect:

- `topic-candidates.json`
- source observation mapping
- topic IDs and dedup keys
- unresolved items
- ranking output in the workflow logs

## Future Scheduling Boundary

A scheduled topic scan should be considered only in a later approved phase after the manual preview workflow has been reviewed and accepted. Any future scheduled workflow must keep the same no-secrets, no-private-data, and public-source policy boundaries.
