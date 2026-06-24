# Source Registry

`config/sources.example.json` is the offline source registry example for AI Signal Brief.

## Source Priority Policy

The registry uses `official_sources_first`. Source categories are sorted by integer priority, where `1` is the highest priority. Official vendor or project sources must be priority `1`.

Default category order:

1. `official`
2. `paper`
3. `repository`
4. `regulatory`
5. `news`
6. `social`
7. `other`

## Official-Source-First Rule

When a story has both an official source and secondary coverage, the official source should be used for factual claims. News and social sources can add context, but they should not be the only support for technical claims when an official or primary source exists.

## Allowed Source Types

Allowed `source_type` values are compatible with `report.json`:

- `official`
- `paper`
- `repository`
- `regulatory`
- `news`
- `social`
- `other`

## Source Acceptance Rules

Every source entry must include:

- `id`
- `title`
- `publisher`
- `url`
- `source_type`
- `category_id`
- `priority`

The Phase 3 validator rejects duplicate category IDs, duplicate source IDs, invalid priorities, invalid source types, category mismatches, private/local URLs, local paths, and secret-like values.

## Validation Commands

```powershell
python -m ai_signal_brief validate-sources config/sources.example.json
python -m ai_signal_brief list-source-priorities
```

These commands are offline-only. They do not fetch URLs, scrape websites, call APIs, or send notifications.