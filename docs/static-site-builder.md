# Offline Static Site Builder

Phase 8 adds a stdlib-only static site builder that renders a local HTML preview from an existing archive.

The site builder is offline. It does not fetch sources, scrape websites, call model APIs, generate images, send Telegram messages, create DOCX files, create GitHub Actions, or publish outputs.

## Command

```powershell
python -m ai_signal_brief build-site --archive outputs/archive-example --out outputs/site-example
```

## Inputs

The builder reads:

- `outputs/archive-example/index.json`
- archived `report.json` files
- archived `run.json` files
- archived `index.md` files when available

## Outputs

The builder writes:

```text
outputs/site-example/index.html
outputs/site-example/assets/style.css
outputs/site-example/YYYY/MM/DD/index.html
outputs/site-example/manifest.json
```

`outputs/` is generated output and should remain ignored by Git.

## Homepage Content

The homepage includes:

- project title: `AI Signal Brief`
- archive summary
- reports sorted by `report_date` descending
- report title
- report date
- generated timestamp
- links to each report page
- offline-generated disclosure

## Report Page Content

Each report page includes:

- report title
- report date
- generated timestamp
- timezone
- top story summary
- ranked stories
- story status and importance
- claims and source references
- complete source list
- provenance note
- link back to the homepage

## Safety Rules

All report content is HTML-escaped. The site uses only local generated CSS and includes no external scripts, no external CSS, and no remote images.

The builder rejects unsafe archive paths and output paths outside the repository. Generated files are scanned for secret-like values, private paths, mistaken prompt references, and legacy private builder references.