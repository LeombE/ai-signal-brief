# Live AI Daily Report MVP

`build-daily-ai-report` is the first explicit live-source command in this project. It is manual-only and scoped to allowlisted public HTTPS AI sources.

This command is separate from replay and dry-run commands. Existing replay and `discover-topics-live-dry-run` paths remain no-network.

## Command

```powershell
python -m ai_signal_brief build-daily-ai-report --date YYYY-MM-DD --timezone Asia/Kuala_Lumpur --out outputs/daily-reports/YYYY-MM-DD --format markdown,json,docx --english-only --no-openai --sources config/live_ai_sources.example.json --lookback-hours 72 --min-fresh-items 3
```

Default behavior:

- writes local files only under `outputs/`
- generates English output only
- includes source URLs, source notes, and signal-level labels
- does not send Telegram
- does not call OpenAI
- does not add schedule
- does not deploy Pages
- does not generate images
- does not commit outputs

## Source Policy

The source allowlist lives at `config/live_ai_sources.example.json`.

Source rules:

- public HTTPS only
- official or high-signal AI sources first
- no login-required sources
- no restricted access sources
- no non-HTTPS URLs
- no local paths
- no private repositories or workspaces
- no raw full-page HTML committed to Git
- every item must retain source attribution

The MVP starts with official or high-signal sources for OpenAI, Anthropic, Google AI, Google DeepMind, Meta AI, Mistral, Cohere, xAI, and Hugging Face context. Where supported, the allowlist may include a public HTTPS `feed_url` so RSS/Atom entries are preferred over homepage metadata.

When official sources do not provide enough fresh article-level updates, the allowlist can include reputable public AI/news RSS feeds as backup coverage. Current backup/reputable sources include TechCrunch AI, VentureBeat AI, The Decoder AI, MIT Technology Review AI, and The Verge AI. These sources are marked `source_priority_label: reputable_news` or `backup`, retain source attribution, and remain lower priority than official release/changelog/blog sources.

Each source may declare:

- `source_priority_label`: `official`, `reputable_news`, or `backup`
- `source_category`: `official_release`, `ai_news`, `research`, `model_release`, `tooling`, `policy`, or `funding`
- `max_items`: per-source item limit before global report ranking



## Freshness And Telegram Readiness

The daily report is not send-ready merely because it generated files. By default, `build-daily-ai-report` uses a 72-hour freshness window for main ranked updates:

- RSS/Atom entries use `pubDate`, `published`, or `updated` when present.
- HTML article pages may use `article:published_time`, `article:modified_time`, `og:updated_time`, `datePublished`, `dateModified`, `pubdate`, `dc.date`, `itemprop="datePublished"`, and JSON-LD `datePublished` / `dateModified`.
- Dates are not invented. If no parseable date exists, the item is marked `freshness_status: date_missing` and `fresh_enough_for_daily: false`.
- Items older than `--lookback-hours` are marked `freshness_status: stale` and are excluded from Top AI Model / Tooling Updates.
- Stale and date-missing items are written to `watchlist_updates` for manual review.
- Fresh article-level items still need to clear the editorial relevance gate before they can enter the main Telegram candidate set.
- `telegram_ready` is true only when at least `--min-fresh-items` items are fresh, article-level, source-backed, and editorially relevant to AI model, tooling, research, API, safety, or product readers.

If the report has enough fresh article-level items but too few editorial-ready items, the report states that the fetched items were not editorially relevant enough for Telegram delivery. In that state, files may still be useful for source review, but they are not ready for Telegram delivery.

## Source Parsing Quality

The live report parser now prefers article-level evidence in this order:

1. RSS or Atom feed entries from the source URL or an allowlisted `feed_url`
2. `rel=alternate` RSS/Atom feeds discovered from the source homepage
3. article-card links discovered on the source homepage
4. homepage metadata fallback only when no article-level item is available

Homepage fallback items are deliberately downranked. They are marked with `signal_level: source_homepage_fallback`, low confidence, low novelty, and explicit review notes. They should be treated as monitoring evidence only, not as strong news claims.

Feed entries preserve title, link, published or updated time when available, summary, and author metadata when present. The parser repairs common mojibake in titles such as malformed dash characters and rejects common navigation, tag, category, privacy, login, pricing-only, and index pages.

If fewer than three fresh article-level candidates are found, the report is marked `telegram_ready: false`. That is a quality warning, not evidence that no AI news exists.

## Output Files

For an output directory such as `outputs/daily-reports/2026-07-05`, the command may write:

- `report.json`: structured fetched observations, ranked updates, source notes, and safety metadata
- `report.md`: English Markdown report
- `report.docx`: local Word document generated with the Python standard library when `docx` is requested

Generated files are local artifacts. They must stay ignored and untracked.

## Report Structure

The Markdown and DOCX report follows this structure:

1. AI Daily Brief - Global and Major Model Updates
2. Metadata table
3. Executive Summary
4. Top AI Model / Tooling Updates
5. Watchlist / Context Items
6. Downgraded or Excluded Items
7. Key Judgments
8. Detailed News Analysis
9. Company and Model Watchlist
10. Follow-up Checklist
11. Conclusion

## Ranking And Review

Ranking now has a separate editorial relevance gate. Main updates require fresh article-level evidence plus an `editorial_relevance_score` at or above the configured threshold. Preferred main-report categories include model capability changes, developer tooling, AI API/platform changes, research with product relevance, safety/policy items with model or platform impact, enterprise AI tooling, and benchmark/evaluation releases with clear AI relevance.

Lower-priority or downgraded categories include funding, generic company strategy, advertising/culture, education-market stories, labor/platform migration, broad policy without model/platform impact, entertainment/legal context, and other AI-adjacent business news. These items can remain visible in `downgraded_updates`, but they do not count toward `telegram_ready`.

Every item remains subject to manual source review before publication or downstream delivery.

## Telegram Boundary

Telegram delivery is off by default. The CLI only sends when `--send-telegram` is explicitly provided, the report has `telegram_ready: true`, and both a bot credential and a recipient value are available from the environment or explicit arguments.

Unit tests mock the sending path. CI must not send Telegram messages.

## OpenAI Boundary

OpenAI usage is off by default. The MVP does not require model calls. The explicit summary option fails closed unless a later approved phase implements a reviewed OpenAI path.

CI must not call OpenAI APIs.

## Safety Checklist

Before treating a generated daily report as review evidence, confirm:

- command was run manually
- outputs stayed under `outputs/`
- generated files were not staged or tracked
- no schedule was added
- no workflow was modified
- Telegram was not sent unless explicitly requested
- OpenAI was not used unless explicitly requested in a later approved path
- no images were generated
- no Pages deployment occurred
- source URLs are public HTTPS and attributable
- report language is English
- main updates have `telegram_editorial_ready: true`
- downgraded culture, funding, labor, education, or generic company items do not dominate the Telegram candidate set

## Manual Smoke Command

```powershell
python -m ai_signal_brief build-daily-ai-report --date 2026-07-05 --timezone Asia/Kuala_Lumpur --out outputs/daily-reports/2026-07-05-v3 --format markdown,json,docx --english-only --no-openai --max-items 10 --lookback-hours 72 --min-fresh-items 3 --sources config/live_ai_sources.example.json
```

If one or more live sources fail, inspect `source_errors` in `report.json`. A fetch failure is not evidence that no news exists.