# Live AI Daily Report MVP

`build-daily-ai-report` is the first explicit live-source command in this project. It is manual-only and scoped to allowlisted public HTTPS AI sources.

This command is separate from replay and dry-run commands. Existing replay and `discover-topics-live-dry-run` paths remain no-network.

## Command

```powershell
python -m ai_signal_brief build-daily-ai-report --date YYYY-MM-DD --timezone Asia/Kuala_Lumpur --out outputs/daily-reports/YYYY-MM-DD --format markdown,json,docx --english-only --no-openai --sources config/live_ai_sources.example.json
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


## Source Parsing Quality

The live report parser now prefers article-level evidence in this order:

1. RSS or Atom feed entries from the source URL or an allowlisted `feed_url`
2. `rel=alternate` RSS/Atom feeds discovered from the source homepage
3. article-card links discovered on the source homepage
4. homepage metadata fallback only when no article-level item is available

Homepage fallback items are deliberately downranked. They are marked with `signal_level: source_homepage_fallback`, low confidence, low novelty, and explicit review notes. They should be treated as monitoring evidence only, not as strong news claims.

Feed entries preserve title, link, published or updated time when available, summary, and author metadata when present. The parser repairs common mojibake in titles such as malformed dash characters and rejects common navigation, tag, category, privacy, login, pricing-only, and index pages.

If fewer than three article-level candidates are found, the report states that article-level coverage was limited. That is a quality warning, not evidence that no AI news exists.

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
4. Top Updates Ranked by Importance
5. Key Judgments
6. Detailed News Analysis
7. Company and Model Watchlist
8. Follow-up Checklist
9. Conclusion

## Ranking And Review

Ranking prioritizes:

1. official model, API, or platform releases
2. availability, pricing, migration, or deprecation changes
3. major model capability announcements
4. safety, security, and regulatory updates
5. research releases from official labs or strong primary sources
6. lower-evidence or repeated items are downgraded

Every item remains subject to manual source review before publication or downstream delivery.

## Telegram Boundary

Telegram delivery is off by default. The CLI only sends when `--send-telegram` is explicitly provided and both a bot credential and a recipient value are available from the environment or explicit arguments.

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

## Manual Smoke Command

```powershell
python -m ai_signal_brief build-daily-ai-report --date 2026-07-05 --timezone Asia/Kuala_Lumpur --out outputs/daily-reports/2026-07-05-v2 --format markdown,json,docx --english-only --no-openai --max-items 10 --lookback-hours 72 --sources config/live_ai_sources.example.json
```

If one or more live sources fail, inspect `source_errors` in `report.json`. A fetch failure is not evidence that no news exists.