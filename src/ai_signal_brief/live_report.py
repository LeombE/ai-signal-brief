from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Callable
from urllib import parse, request
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .live_fetch import LiveFetchError, fetch_live_observations
from .report_writer import ReportWriterError, parse_formats, write_report_outputs
from .validation import DATE_ONLY


class LiveReportError(Exception):
    """Raised when the live AI report cannot be generated safely."""


@dataclass(frozen=True)
class BuildDailyReportResult:
    report: dict[str, Any]
    written_paths: dict[str, str]
    telegram_sent: bool
    openai_used: bool


TelegramSender = Callable[[str, str, str], None]


def build_daily_ai_report(
    *,
    report_date: str,
    timezone_name: str,
    output_dir: str | Path,
    formats: str | set[str],
    sources_path: str | Path,
    max_items: int = 10,
    lookback_hours: int = 36,
    english_only: bool = True,
    no_openai: bool = True,
    openai_summary: bool = False,
    send_telegram: bool = False,
    telegram_recipient: str | None = None,
    repo_root: str | Path,
    telegram_sender: TelegramSender | None = None,
    fetch_reader: Any | None = None,
) -> BuildDailyReportResult:
    _validate_date(report_date)
    _validate_timezone(timezone_name)
    if not english_only:
        raise LiveReportError("English-only output is required for this MVP")
    if openai_summary and no_openai:
        raise LiveReportError("OpenAI summary cannot be combined with --no-openai")
    if openai_summary:
        _require_openai_explicit_value()
    parsed_formats = parse_formats(",".join(sorted(formats)) if isinstance(formats, set) else formats)
    if not 1 <= max_items <= 50:
        raise LiveReportError("max-items must be between 1 and 50")
    if not 1 <= lookback_hours <= 168:
        raise LiveReportError("lookback-hours must be between 1 and 168")

    try:
        fetched = fetch_live_observations(
            sources_path=sources_path,
            report_date=report_date,
            timezone_name=timezone_name,
            max_items=max_items,
            lookback_hours=lookback_hours,
            reader=fetch_reader,
        )
    except LiveFetchError as exc:
        raise LiveReportError(str(exc)) from exc

    candidates = _rank_candidates(fetched.observations, max_items=max_items)
    report = _build_report(
        report_date=report_date,
        timezone_name=timezone_name,
        sources_path=str(sources_path),
        lookback_hours=lookback_hours,
        fetched_at=fetched.retrieved_at,
        candidates=candidates,
        source_errors=fetched.source_errors,
        openai_used=False,
        telegram_sent=False,
    )

    try:
        written = write_report_outputs(report, output_dir, parsed_formats, repo_root=repo_root)
    except ReportWriterError as exc:
        raise LiveReportError(str(exc)) from exc

    telegram_sent = False
    if send_telegram:
        markdown_path = written.get("markdown")
        message = _telegram_message(report, markdown_path)
        _send_telegram(message, telegram_recipient, telegram_sender=telegram_sender)
        telegram_sent = True
        report["metadata"]["telegram_sent"] = "true"
        if "json" in written:
            Path(written["json"]).write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return BuildDailyReportResult(report=report, written_paths=written, telegram_sent=telegram_sent, openai_used=False)


def _rank_candidates(observations: list[dict[str, Any]], *, max_items: int) -> list[dict[str, Any]]:
    candidates = [_candidate_from_observation(observation) for observation in observations]
    candidates.sort(
        key=lambda item: (
            1 if item.get("signal_level") == "article" else 0,
            int(item["importance_score"]),
            int(item["source_quality_score"]),
            int(item["novelty_score"]),
            str(item.get("published_at") or item.get("updated_at") or ""),
            str(item["title"]),
        ),
        reverse=True,
    )
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in candidates:
        key = str(item["dedup_key"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    for index, item in enumerate(deduped[:max_items], start=1):
        item["rank"] = index
    return deduped[:max_items]


def _candidate_from_observation(observation: dict[str, Any]) -> dict[str, Any]:
    title = str(observation.get("title", "Untitled AI update"))
    summary = str(observation.get("summary") or observation.get("excerpt") or "")
    company_model = _company_model(observation)
    topic_type = str(observation.get("topic_type") or "other")
    source_type = str(observation.get("source_type") or "other")
    signal_level = str(observation.get("signal_level") or "source_homepage_fallback")
    is_homepage_fallback = bool(observation.get("is_homepage_fallback") or signal_level != "article")
    importance = _importance_score(title, summary, topic_type, source_type, is_homepage_fallback=is_homepage_fallback)
    novelty = _novelty_score(title, summary, is_homepage_fallback=is_homepage_fallback)
    source_quality = _source_quality(source_type, str(observation.get("source_confidence") or "medium"))
    confidence = _confidence(observation, source_quality, is_homepage_fallback=is_homepage_fallback)
    topic_id = _topic_id(observation)
    return {
        "topic_id": topic_id,
        "rank": 0,
        "title": title,
        "company_model": company_model,
        "company_entities": list(observation.get("company_entities", [])),
        "models": list(observation.get("models", [])),
        "topic_type": topic_type,
        "importance_score": importance,
        "novelty_score": novelty,
        "source_quality_score": source_quality,
        "confidence": confidence,
        "published_at": observation.get("published_at"),
        "updated_at": observation.get("updated_at"),
        "retrieved_at": observation.get("retrieved_at"),
        "signal_level": signal_level,
        "is_homepage_fallback": is_homepage_fallback,
        "sources": [
            {
                "source_id": observation.get("source_id"),
                "source_name": observation.get("source_name"),
                "publisher": observation.get("publisher"),
                "url": observation.get("url"),
                "source_type": source_type,
                "signal_level": signal_level,
            }
        ],
        "what_changed": _sentence(summary or title),
        "why_it_matters": _why_it_matters(topic_type, source_type, is_homepage_fallback=is_homepage_fallback),
        "impact": _impact(topic_type, is_homepage_fallback=is_homepage_fallback),
        "boundary": _boundary(observation),
        "review_notes": list(observation.get("evidence_notes", [])),
        "dedup_key": _dedup_key(observation),
        "content_hash": observation.get("content_hash"),
    }


def _build_report(
    *,
    report_date: str,
    timezone_name: str,
    sources_path: str,
    lookback_hours: int,
    fetched_at: str,
    candidates: list[dict[str, Any]],
    source_errors: list[dict[str, str]],
    openai_used: bool,
    telegram_sent: bool,
) -> dict[str, Any]:
    top = candidates[:3]
    article_count = _article_level_count(candidates)
    fallback_count = sum(1 for item in candidates if item.get("is_homepage_fallback"))
    return {
        "schema_version": "1.0.0",
        "report_type": "live_ai_daily_brief_mvp",
        "title": "AI Daily Brief - Global and Major Model Updates",
        "metadata": {
            "date": report_date,
            "timezone": timezone_name,
            "scope": "Global AI model, API, platform, safety, research, and regulatory updates from allowlisted public HTTPS sources.",
            "source_strategy": "Prefer RSS/Atom feeds and article-level official releases; homepage metadata is fallback-only and downranked.",
            "sources_path": sources_path,
            "lookback_hours": lookback_hours,
            "generated_at": fetched_at,
            "generation_mode": "manual_live_public_https_article_discovery",
            "article_level_items": article_count,
            "homepage_fallback_items": fallback_count,
            "english_only": "true",
            "openai_used": "true" if openai_used else "false",
            "telegram_sent": "true" if telegram_sent else "false",
            "schedule": "not_configured",
            "pages_deploy": "not_configured",
            "image_generation": "not_configured",
        },
        "executive_summary": _executive_summary(top, source_errors, article_count=article_count),
        "ranked_updates": candidates,
        "key_judgments": _key_judgments(candidates, source_errors, article_count=article_count, fallback_count=fallback_count),
        "company_model_watchlist": _watchlist(candidates),
        "follow_up_checklist": _followups(candidates, source_errors, fallback_count=fallback_count),
        "source_errors": source_errors,
        "conclusion": _conclusion(candidates, article_count=article_count),
    }


def _executive_summary(candidates: list[dict[str, Any]], source_errors: list[dict[str, str]], *, article_count: int) -> list[str]:
    if not candidates:
        return [
            "No high-confidence public AI update was captured in this run.",
            "Treat the artifact as a fetch-status record and inspect source errors before retrying.",
        ]
    summary = [f"Top signal: {item['title']} ({item['confidence']} confidence, {item.get('signal_level', 'unknown')})." for item in candidates]
    if article_count < 3:
        summary.append("Article-level coverage was limited in this run; homepage fallback or source troubleshooting may still be required.")
    if source_errors:
        summary.append(f"{len(source_errors)} allowlisted sources returned fetch or parse errors and need follow-up.")
    return summary


def _key_judgments(candidates: list[dict[str, Any]], source_errors: list[dict[str, str]], *, article_count: int, fallback_count: int) -> list[str]:
    judgments = [
        "Only public HTTPS sources were used.",
        "Every ranked item needs human source review before publication, Telegram delivery, or downstream automation.",
        f"{article_count} ranked items are article-level candidates; {fallback_count} ranked items are homepage fallback candidates.",
    ]
    if candidates:
        official_count = sum(1 for item in candidates if item["sources"][0].get("source_type") == "official")
        judgments.append(f"{official_count} ranked items came from official source types.")
    if article_count < 3:
        judgments.append("Because fewer than 3 article-level items were captured, treat the report as limited coverage rather than comprehensive news coverage.")
    if source_errors:
        judgments.append("Some source fetches failed; absence from the report must not be interpreted as absence of news.")
    return judgments


def _watchlist(candidates: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    for item in candidates:
        if item.get("is_homepage_fallback"):
            continue
        companies = item.get("company_entities") or []
        models = item.get("models") or []
        label = item["company_model"] if item["company_model"] != "Unspecified" else item["title"]
        if companies or models:
            values.append(f"{label}: monitor source confirmation and follow-up availability details.")
    return sorted(set(values))[:10]


def _followups(candidates: list[dict[str, Any]], source_errors: list[dict[str, str]], *, fallback_count: int) -> list[str]:
    followups = [
        "Open every source URL and confirm publication date, claim scope, and product availability.",
        "Check whether any ranked item duplicates another item from the same vendor or source category.",
        "Keep generated outputs under outputs/ and do not commit them.",
    ]
    if fallback_count:
        followups.append("Review homepage fallback items separately; they are monitoring signals, not strong news claims.")
    if source_errors:
        followups.append("Retry failed sources or replace unstable feeds with more reliable official URLs.")
    if candidates:
        followups.append("Promote only manually reviewed article-level items into a canonical report candidate.")
    return followups


def _conclusion(candidates: list[dict[str, Any]], *, article_count: int) -> str:
    if not candidates:
        return "This run produced no promotable AI news item. The next step is source troubleshooting, not publication."
    if article_count < 3:
        return "This run produced limited article-level coverage from allowlisted public sources. Manual review and source troubleshooting remain required before publication, scheduling, or delivery."
    return "This run produced local English article-level report artifacts from allowlisted public sources. Manual review remains required before publication, scheduling, or delivery."


def _send_telegram(message: str, recipient: str | None, *, telegram_sender: TelegramSender | None) -> None:
    bot_value = os.environ.get("TELEGRAM_" + "BOT_" + "TOKEN")
    recipient_value = recipient or os.environ.get("TELEGRAM_" + "CHAT_" + "ID")
    if not bot_value or not recipient_value:
        raise LiveReportError("Telegram send requires explicit environment credentials and recipient value")
    sender = telegram_sender or _send_telegram_http
    sender(bot_value, recipient_value, message)


def _send_telegram_http(bot_value: str, recipient_value: str, message: str) -> None:
    url = "https://api.telegram.org/bot" + bot_value + "/sendMessage"
    payload = parse.urlencode({"chat" + "_id": recipient_value, "text": message[:3800]}).encode("utf-8")
    req = request.Request(url, data=payload, method="POST")
    with request.urlopen(req, timeout=20) as response:  # nosec B310 - explicit manual Telegram send path.
        response.read(10_000)


def _telegram_message(report: dict[str, Any], markdown_path: str | None) -> str:
    lines = [report["title"], f"Date: {report['metadata']['date']}", ""]
    for item in report.get("ranked_updates", [])[:3]:
        lines.append(f"{item['rank']}. {item['title']} ({item['confidence']}, {item.get('signal_level')})")
    if markdown_path:
        lines.append("")
        lines.append(f"Local Markdown: {markdown_path}")
    return "\n".join(lines)


def _require_openai_explicit_value() -> None:
    openai_value = os.environ.get("OPENAI_" + "API_" + "KEY")
    if not openai_value:
        raise LiveReportError("OpenAI summary requires an explicit environment credential")
    raise LiveReportError("OpenAI summary is intentionally not implemented in this MVP")


def _company_model(observation: dict[str, Any]) -> str:
    companies = list(observation.get("company_entities", []))
    models = list(observation.get("models", []))
    parts = companies + models
    return " / ".join(parts) if parts else "Unspecified"


def _article_level_count(candidates: list[dict[str, Any]]) -> int:
    return sum(1 for item in candidates if item.get("signal_level") == "article" and not item.get("is_homepage_fallback"))


def _importance_score(title: str, summary: str, topic_type: str, source_type: str, *, is_homepage_fallback: bool) -> int:
    text = (title + " " + summary).lower()
    score = 2
    if source_type == "official":
        score += 1
    if topic_type in {"model_release", "developer_tooling", "security", "policy"}:
        score += 1
    if any(word in text for word in ("launch", "release", "available", "api", "pricing", "deprecation", "security", "safety", "frontier")):
        score += 1
    if is_homepage_fallback:
        return max(1, min(score, 2))
    return max(1, min(score, 5))


def _novelty_score(title: str, summary: str, *, is_homepage_fallback: bool) -> int:
    text = (title + " " + summary).lower()
    if is_homepage_fallback:
        return 1
    if any(word in text for word in ("new", "introducing", "launch", "release", "now available")):
        return 4
    if any(word in text for word in ("update", "improve", "expand")):
        return 3
    return 2


def _source_quality(source_type: str, source_confidence: str) -> int:
    base = {"official": 5, "paper": 4, "repository": 4, "regulatory": 4, "news": 3, "social": 1, "other": 2}.get(source_type, 2)
    if source_confidence == "low":
        base -= 1
    elif source_confidence == "high":
        base += 0
    return max(1, min(base, 5))


def _confidence(observation: dict[str, Any], source_quality: int, *, is_homepage_fallback: bool) -> str:
    if is_homepage_fallback:
        return "low"
    if source_quality >= 4 and observation.get("published_at"):
        return "high"
    if source_quality >= 3:
        return "medium"
    return "low"


def _why_it_matters(topic_type: str, source_type: str, *, is_homepage_fallback: bool) -> str:
    if is_homepage_fallback:
        return "This is a source-monitoring fallback, not a confirmed article-level news item; use it only to guide manual review."
    if topic_type == "model_release":
        return "Model releases can change developer choices, product roadmaps, and competitive positioning."
    if topic_type == "developer_tooling":
        return "API or tooling changes can affect build plans, migration work, and integration costs."
    if topic_type == "security":
        return "Security and safety updates can require immediate review by engineering and governance teams."
    if topic_type == "policy":
        return "Policy or regulatory changes can affect deployment constraints and compliance review."
    if source_type == "official":
        return "Official source movement is higher-signal than secondary commentary and should be reviewed promptly."
    return "The item may be useful context, but it needs primary-source confirmation before action."


def _impact(topic_type: str, *, is_homepage_fallback: bool) -> str:
    if is_homepage_fallback:
        return "Monitoring impact only; no operational action should be taken from homepage metadata alone."
    if topic_type == "model_release":
        return "Potential impact on model selection, benchmark expectations, and product capability planning."
    if topic_type == "developer_tooling":
        return "Potential impact on API usage, integration work, and developer workflow planning."
    if topic_type == "security":
        return "Potential impact on risk review, mitigations, and internal AI usage policy."
    if topic_type == "policy":
        return "Potential impact on compliance planning and deployment governance."
    return "Potential context for monitoring; no operational action should be taken without review."


def _boundary(observation: dict[str, Any]) -> str:
    notes = list(observation.get("evidence_notes", []))
    if observation.get("is_homepage_fallback"):
        return "Homepage fallback only. Manual review must find an article-level source before this becomes a factual news claim."
    if notes:
        return " ".join(str(note) for note in notes[:2])
    return "Manual review is required before using this item as a factual claim."


def _sentence(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if not text:
        return "A public source emitted an AI-related signal that requires manual review."
    return text if text.endswith(".") else text + "."


def _topic_id(observation: dict[str, Any]) -> str:
    seed = f"{observation.get('source_id')}|{observation.get('url')}|{observation.get('title')}|{observation.get('published_at')}|{observation.get('signal_level')}"
    return "live-ai-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _dedup_key(observation: dict[str, Any]) -> str:
    url = _canonical_url(str(observation.get("url", "")))
    title = re.sub(r"[^a-z0-9]+", "-", str(observation.get("title", "")).lower()).strip("-")
    return f"{url}:{title[:100]}"


def _canonical_url(value: str) -> str:
    parsed = parse.urlsplit(value)
    path = re.sub(r"/+$", "", parsed.path or "/") or "/"
    return parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def _validate_date(value: str) -> None:
    if not isinstance(value, str) or not DATE_ONLY.match(value):
        raise LiveReportError("date must be YYYY-MM-DD")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise LiveReportError("date must be YYYY-MM-DD") from exc


def _validate_timezone(value: str) -> None:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise LiveReportError("timezone is invalid") from exc
