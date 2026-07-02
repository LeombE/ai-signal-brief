# Reviewed Report Template

This folder contains public-safe placeholder templates for future manually reviewed English canonical reports.

These files are examples only. They are not real reports and must not be published as production data.

## Files

- `report.template.json`: placeholder canonical report structure
- `run.template.json`: placeholder run metadata structure
- `review.template.md`: manual review checklist and notes template

## Intended Future Use

When a real report candidate is ready in a later approved phase:

1. Create a dated folder under `reports-reviewed/YYYY/MM/DD/`.
2. Copy `report.template.json` to `reports-reviewed/YYYY/MM/DD/report.json`.
3. Copy `run.template.json` to `reports-reviewed/YYYY/MM/DD/run.json`.
4. Copy `review.template.md` to `reports-reviewed/YYYY/MM/DD/review.md`.
5. Replace every placeholder value with reviewed English canonical content.
6. Validate the report and run metadata locally.
7. Run the quality gate locally.
8. Build archive and site output locally.
9. Inspect generated static pages before any production Pages workflow is considered.

## Safety Boundaries

Do not copy raw historical reports, private source files, screenshots, DOCX files, HTML exports, Telegram exports, old builder scripts, local env files, private paths, API keys, Telegram credentials, chat identifiers, or OpenAI credentials into this folder or any future reviewed report folder.

The current GitHub Pages site uses sample/example data only. These templates do not enable production Pages, Telegram delivery, OpenAI Image API usage, scheduled automation, image generation, or DOCX generation.