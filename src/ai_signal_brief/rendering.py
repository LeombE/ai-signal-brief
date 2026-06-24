from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .validation import ValidationResult, find_secret_like_values, validate_report_path


class RenderError(RuntimeError):
    """Raised when a report cannot be rendered safely."""


def load_valid_report(path: str | Path) -> dict[str, Any]:
    report_path = Path(path)
    validation = validate_report_path(report_path)
    if not validation.ok:
        raise RenderError(_format_validation_errors(validation))
    with report_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise RenderError("Report must be a JSON object.")
    return data


def render_markdown_from_path(path: str | Path) -> str:
    return render_markdown(load_valid_report(path))


def render_telegram_from_path(path: str | Path) -> str:
    return render_telegram(load_valid_report(path))


def write_text_output(content: str, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    secret_errors = find_secret_like_values(content)
    if secret_errors:
        raise RenderError("Rendered output contains secret-like values: " + "; ".join(secret_errors))
    path.write_text(content, encoding="utf-8")
    return path


def render_markdown(report: dict[str, Any]) -> str:
    sources_by_id = _sources_by_id(report)
    lines: list[str] = []

    lines.append(f"# {report['title']}")
    lines.append("")
    lines.append(f"- Report date: {report['report_date']}")
    lines.append(f"- Generated at: {report['generated_at']}")
    lines.append(f"- Timezone: {report['timezone']}")

    disclosure = _disclosure(report)
    if disclosure:
        lines.append(f"- AI/generated-content disclosure: {disclosure}")

    lines.append("")
    lines.append("## Top Story Summary")
    top_stories = report.get("summary", {}).get("top_stories", [])
    if top_stories:
        for item in top_stories:
            rank = item.get("rank", "?")
            story_id = item.get("story_id", "unknown")
            headline = item.get("headline", "Untitled")
            why = item.get("why_it_matters", "")
            lines.append(f"{rank}. **{headline}** (`{story_id}`) - {why}")
    else:
        lines.append("No top stories provided.")

    lines.append("")
    lines.append("## Ranked Stories")
    for story in sorted(report.get("stories", []), key=lambda item: item.get("rank", 9999)):
        story_id = story.get("id", "unknown")
        importance = story.get("importance", {})
        lines.append("")
        lines.append(f"### {story.get('rank', '?')}. {story.get('title', 'Untitled')}")
        lines.append(f"- Story ID: `{story_id}`")
        lines.append(f"- Status: {story.get('status', 'unknown')}")
        lines.append(f"- Importance: {importance.get('score', '?')}/5 - {importance.get('rationale', '')}")
        lines.append(f"- Companies: {_join_or_none(story.get('companies', []))}")
        lines.append(f"- Models: {_join_or_none(story.get('models', []))}")
        lines.append(f"- Regions: {_join_or_none(story.get('regions', []))}")
        lines.append(f"- Story sources: {_format_source_refs(story.get('source_ids', []), sources_by_id)}")
        lines.append("")
        lines.append(story.get("analysis", ""))
        lines.append("")
        lines.append("#### Claims")
        claims = story.get("claims", [])
        if not claims:
            lines.append("- No claims provided.")
        for claim in claims:
            lines.append(
                "- "
                + f"`{claim.get('id', 'unknown')}` {claim.get('text', '')} "
                + f"[{claim.get('verification_status', 'unknown')}, {claim.get('confidence', 'unknown')} confidence] "
                + f"Sources: {_format_source_refs(claim.get('source_ids', []), sources_by_id)}"
            )

    lines.append("")
    lines.append("## Sources")
    for source in report.get("sources", []):
        lines.append(
            "- "
            + f"`{source.get('id', 'unknown')}` "
            + f"{source.get('title', 'Untitled')} - {source.get('publisher', 'Unknown publisher')} "
            + f"({source.get('source_type', 'unknown')}) "
            + f"{source.get('url', '')}"
        )

    lines.append("")
    lines.append("## Provenance")
    lines.append(_format_provenance(report.get("provenance", {})))
    lines.append("")
    lines.append("_Generated offline preview from validated canonical report JSON. No live sources were fetched._")
    lines.append("")
    return "\n".join(lines)


def render_telegram(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(report["title"])
    generated = _format_generated_at(report.get("generated_at", ""), report.get("timezone", "Asia/Kuala_Lumpur"))
    if generated:
        lines.append(f"Generated: {generated}")
    lines.append("Offline generated preview. No Telegram API call was made.")

    public_url = _public_url(report)
    if public_url:
        lines.append(f"Public URL: {public_url}")

    lines.append("")
    lines.append("Top stories:")
    top_stories = report.get("summary", {}).get("top_stories", [])[:3]
    if top_stories:
        for item in top_stories:
            rank = item.get("rank", "?")
            headline = item.get("headline", "Untitled")
            why = item.get("why_it_matters", "")
            lines.append(f"{rank}. {headline} - {why}")
    else:
        for story in sorted(report.get("stories", []), key=lambda item: item.get("rank", 9999))[:3]:
            importance = story.get("importance", {})
            lines.append(f"{story.get('rank', '?')}. {story.get('title', 'Untitled')} ({importance.get('score', '?')}/5)")

    lines.append("")
    lines.append("Source-backed; see report JSON for claim/source mapping.")
    lines.append("")
    return "\n".join(lines)


def _format_validation_errors(result: ValidationResult) -> str:
    return "Report validation failed: " + "; ".join(result.errors)


def _sources_by_id(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {source["id"]: source for source in report.get("sources", []) if isinstance(source, dict) and "id" in source}


def _format_source_refs(source_ids: list[str], sources_by_id: dict[str, dict[str, Any]]) -> str:
    refs: list[str] = []
    for source_id in source_ids:
        source = sources_by_id.get(source_id, {})
        title = source.get("title", source_id)
        refs.append(f"`{source_id}` ({title})")
    return ", ".join(refs) if refs else "none"


def _join_or_none(values: list[Any]) -> str:
    clean = [str(value) for value in values if value]
    return ", ".join(clean) if clean else "none"


def _format_provenance(provenance: Any) -> str:
    if not isinstance(provenance, dict) or not provenance:
        return "No provenance metadata provided."
    parts = [f"{key}: {value}" for key, value in sorted(provenance.items())]
    return "; ".join(parts)


def _disclosure(report: dict[str, Any]) -> str | None:
    for container_name in ("metadata", "provenance"):
        container = report.get(container_name)
        if not isinstance(container, dict):
            continue
        for key in ("ai_generated_content_disclosure", "generated_content_disclosure", "ai_disclosure"):
            value = container.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _public_url(report: dict[str, Any]) -> str | None:
    for container_name in ("metadata", "provenance"):
        container = report.get(container_name)
        if not isinstance(container, dict):
            continue
        for key in ("public_url", "canonical_url", "github_pages_url"):
            value = container.get(key)
            if isinstance(value, str) and value.startswith("https://"):
                return value
    return None


def _format_generated_at(value: str, timezone_name: str) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return value
        converted = parsed.astimezone(ZoneInfo(timezone_name or "Asia/Kuala_Lumpur"))
        return converted.isoformat(timespec="seconds")
    except Exception:
        return value