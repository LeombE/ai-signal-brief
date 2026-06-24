# Offline Rendering

Phase 4 adds offline renderers for validated canonical `report.json` files.

## Commands

```powershell
python -m ai_signal_brief render-markdown examples/report.example.json --out outputs/report.example.md
python -m ai_signal_brief render-telegram examples/report.example.json --out outputs/telegram.example.txt
```

Both commands validate the report before rendering. Invalid reports are rejected and no external services are called.

## Markdown Output

The Markdown renderer includes:

- title
- report date
- `generated_at`
- timezone
- top story summary
- ranked stories
- story status and importance
- claim/source mapping
- complete source list
- provenance note
- AI/generated-content disclosure when present in report `metadata` or `provenance`

## Telegram Preview Output

The Telegram renderer writes a text file only. It includes:

- English title
- generated timestamp converted with the report timezone when possible
- top three story summary
- public URL only when present in report `metadata` or `provenance`
- clear generated offline preview note

The command does not send messages, call the Telegram API, or create DOCX files.

## Output Policy

`outputs/` is ignored by Git. Generated examples are local previews, not production publication artifacts. Renderer tests use temporary files and public example JSON only.