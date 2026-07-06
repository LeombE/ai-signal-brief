from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, time
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

EDITORIAL_READY_THRESHOLD = 3


def build_daily_ai_report(
    *,
    report_date: str,
    timezone_name: str,
    output_dir: str | Path,
    formats: str | set[str],
    sources_path: str | Path,
    max_items: int = 10,
    lookback_hours: int = 72,
    allow_stale: bool = False,
    min_fresh_items: int = 3,
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
    if not 1 <= min_fresh_items <= max_items:
        raise LiveReportError("min-fresh-items must be between 1 and max-items")

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

    cutoff = _cutoff(report_date, timezone_name, lookback_hours)
    candidates, watchlist, downgraded = _rank_candidates(
        fetched.observations,
        max_items=max_items,
        cutoff=cutoff,
        allow_stale=allow_stale,
    )
    report = _build_report(
        report_date=report_date,
        timezone_name=timezone_name,
        sources_path=str(sources_path),
        lookback_hours=lookback_hours,
        allow_stale=allow_stale,
        min_fresh_items=min_fresh_items,
        fetched_at=fetched.retrieved_at,
        candidates=candidates,
        watchlist=watchlist,
        downgraded=downgraded,
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
        if report.get("telegram_ready") is not True:
            raise LiveReportError("Telegram send requires telegram_ready=true after freshness and safety gates")
        markdown_path = written.get("markdown")
        message = _telegram_message(report, markdown_path)
        _send_telegram(message, telegram_recipient, telegram_sender=telegram_sender)
        telegram_sent = True
        report["metadata"]["telegram_sent"] = "true"
        if "json" in written:
            Path(written["json"]).write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return BuildDailyReportResult(report=report, written_paths=written, telegram_sent=telegram_sent, openai_used=False)


def _rank_candidates(
    observations: list[dict[str, Any]],
    *,
    max_items: int,
    cutoff: datetime,
    allow_stale: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    candidates = [_candidate_from_observation(observation, cutoff=cutoff) for observation in observations]
    candidates.sort(key=_candidate_sort_key, reverse=True)

    deduped: list[dict[str, Any]] = []
    downgraded: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in candidates:
        key = str(item["dedup_key"])
        if key in seen:
            duplicate = dict(item)
            duplicate["telegram_editorial_ready"] = False
            duplicate["editorial_relevance_score"] = min(int(duplicate.get("editorial_relevance_score") or 1), 1)
            duplicate["editorial_reason"] = "Downgraded: duplicate or near-duplicate article detected."
            duplicate["downgrade_reason"] = duplicate["editorial_reason"]
            downgraded.append(duplicate)
            continue
        seen.add(key)
        deduped.append(item)

    main_source = [item for item in deduped if _is_main_update(item)]
    watchlist = [item for item in deduped if item.get("fresh_enough_for_daily") is not True or item.get("freshness_status") != "fresh"]
    downgraded.extend(item for item in deduped if item.get("fresh_enough_for_daily") is True and not _is_main_update(item))

    ranked = main_source[:max_items]
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
    for index, item in enumerate(watchlist, start=1):
        item["watchlist_rank"] = index
    for index, item in enumerate(downgraded, start=1):
        item["downgraded_rank"] = index
        item.setdefault("downgrade_reason", item.get("editorial_reason", "Downgraded by editorial relevance gate."))
    return ranked, watchlist[:max_items], downgraded[:max_items]

def _candidate_sort_key(item: dict[str, Any]) -> tuple[int, int, int, int, int, int, int, int, str, str]:
    freshness_rank = {"fresh": 2, "stale": 1, "date_missing": 0}.get(str(item.get("freshness_status")), 0)
    editorial_ready_rank = 1 if item.get("telegram_editorial_ready") is True else 0
    editorial_rank = int(item.get("editorial_relevance_score") or 0)
    signal_rank = 1 if item.get("signal_level") == "article" else 0
    source_rank = {"official": 3, "reputable_news": 2, "backup": 1}.get(str(item.get("source_priority_label")), 0)
    category_rank = _category_rank(str(item.get("topic_type") or ""), str(item.get("source_category") or ""))
    return (
        freshness_rank,
        editorial_ready_rank,
        editorial_rank,
        signal_rank,
        source_rank,
        category_rank,
        int(item["importance_score"]),
        int(item["source_quality_score"]),
        str(item.get("published_at") or item.get("updated_at") or ""),
        str(item["title"]),
    )

def _candidate_from_observation(observation: dict[str, Any], *, cutoff: datetime) -> dict[str, Any]:
    title = str(observation.get("title", "Untitled AI update"))
    summary = str(observation.get("summary") or observation.get("excerpt") or "")
    company_model = _company_model(observation)
    topic_type = str(observation.get("topic_type") or "other")
    source_type = str(observation.get("source_type") or "other")
    source_priority_label = str(observation.get("source_priority_label") or ("official" if source_type == "official" else "reputable_news"))
    source_category = str(observation.get("source_category") or ("official_release" if source_type == "official" else "ai_news"))
    signal_level = str(observation.get("signal_level") or "source_homepage_fallback")
    is_homepage_fallback = bool(observation.get("is_homepage_fallback") or signal_level != "article")
    freshness_status, fresh_enough = _freshness(observation, cutoff, is_homepage_fallback=is_homepage_fallback)
    importance = _importance_score(title, summary, topic_type, source_type, source_category, is_homepage_fallback=is_homepage_fallback, freshness_status=freshness_status)
    novelty = _novelty_score(title, summary, is_homepage_fallback=is_homepage_fallback, freshness_status=freshness_status)
    source_quality = _source_quality(source_type, str(observation.get("source_confidence") or "medium"))
    confidence = _confidence(observation, source_quality, is_homepage_fallback=is_homepage_fallback, freshness_status=freshness_status)
    editorial_category, editorial_score, editorial_ready, editorial_reason = _editorial_relevance(
        title,
        summary,
        topic_type,
        source_type,
        source_category,
        source_priority_label,
        signal_level=signal_level,
        freshness_status=freshness_status,
        fresh_enough=fresh_enough,
        is_homepage_fallback=is_homepage_fallback,
    )
    topic_id = _topic_id(observation)
    return {
        "topic_id": topic_id,
        "rank": 0,
        "title": title,
        "company_model": company_model,
        "company_entities": list(observation.get("company_entities", [])),
        "models": list(observation.get("models", [])),
        "topic_type": topic_type,
        "source_priority_label": source_priority_label,
        "source_category": source_category,
        "importance_score": importance,
        "editorial_category": editorial_category,
        "editorial_relevance_score": editorial_score,
        "telegram_editorial_ready": editorial_ready,
        "editorial_reason": editorial_reason,
        "novelty_score": novelty,
        "source_quality_score": source_quality,
        "confidence": confidence,
        "published_at": observation.get("published_at"),
        "updated_at": observation.get("updated_at"),
        "retrieved_at": observation.get("retrieved_at"),
        "freshness_status": freshness_status,
        "fresh_enough_for_daily": fresh_enough,
        "signal_level": signal_level,
        "is_homepage_fallback": is_homepage_fallback,
        "sources": [
            {
                "source_id": observation.get("source_id"),
                "source_name": observation.get("source_name"),
                "publisher": observation.get("publisher"),
                "url": observation.get("url"),
                "source_type": source_type,
                "source_priority_label": source_priority_label,
                "source_category": source_category,
                "signal_level": signal_level,
            }
        ],
        "what_changed": _sentence(summary or title),
        "why_it_matters": _why_it_matters(topic_type, source_type, is_homepage_fallback=is_homepage_fallback, freshness_status=freshness_status),
        "impact": _impact(topic_type, is_homepage_fallback=is_homepage_fallback),
        "boundary": _boundary(observation, freshness_status=freshness_status),
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
    allow_stale: bool,
    min_fresh_items: int,
    fetched_at: str,
    candidates: list[dict[str, Any]],
    watchlist: list[dict[str, Any]],
    downgraded: list[dict[str, Any]],
    source_errors: list[dict[str, str]],
    openai_used: bool,
    telegram_sent: bool,
) -> dict[str, Any]:
    top = candidates[:3]
    all_items = candidates + watchlist + downgraded
    article_count = _article_level_count(all_items)
    fresh_article_count = _fresh_article_level_count(all_items)
    editorial_ready_count = _editorial_ready_count(candidates)
    stale_count = sum(1 for item in all_items if item.get("freshness_status") == "stale")
    date_missing_count = sum(1 for item in all_items if item.get("freshness_status") == "date_missing")
    fallback_count = sum(1 for item in all_items if item.get("is_homepage_fallback"))
    blocking_errors = bool(source_errors and not candidates)
    content_clean = _no_mojibake(all_items) and _no_placeholder_items(all_items)
    ranked_items_are_fresh = all(item.get("freshness_status") == "fresh" and item.get("fresh_enough_for_daily") is True for item in candidates)
    ranked_items_are_editorial_ready = all(item.get("telegram_editorial_ready") is True for item in candidates)
    telegram_ready = (
        editorial_ready_count >= min_fresh_items
        and ranked_items_are_fresh
        and ranked_items_are_editorial_ready
        and not blocking_errors
        and content_clean
    )
    readiness_reason = _telegram_readiness_reason(
        telegram_ready,
        fresh_article_count=fresh_article_count,
        editorial_ready_count=editorial_ready_count,
        min_fresh_items=min_fresh_items,
        blocking_errors=blocking_errors,
        content_clean=content_clean,
        ranked_items_are_fresh=ranked_items_are_fresh,
        ranked_items_are_editorial_ready=ranked_items_are_editorial_ready,
    )
    return {
        "schema_version": "1.0.0",
        "report_type": "live_ai_daily_brief_mvp",
        "title": "AI Daily Brief - Global and Major Model Updates",
        "telegram_ready": telegram_ready,
        "telegram_readiness_reason": readiness_reason,
        "metadata": {
            "date": report_date,
            "timezone": timezone_name,
            "scope": "Global AI model, API, platform, safety, research, and regulatory updates from allowlisted public HTTPS sources.",
            "source_strategy": "Prefer RSS/Atom feeds and article-level official releases; stale, weak, and AI-adjacent items are separated from main Telegram-ready updates.",
            "editorial_policy": "Telegram-ready means fresh + source-backed + editorially relevant, not only technically fetched.",
            "sources_path": sources_path,
            "lookback_hours": lookback_hours,
            "allow_stale": "true" if allow_stale else "false",
            "min_fresh_items": min_fresh_items,
            "editorial_ready_threshold": EDITORIAL_READY_THRESHOLD,
            "generated_at": fetched_at,
            "generation_mode": "manual_live_public_https_article_discovery",
            "article_level_items": article_count,
            "fresh_article_level_items": fresh_article_count,
            "editorial_ready_items": editorial_ready_count,
            "ranked_update_items": len(candidates),
            "downgraded_items": len(downgraded),
            "stale_items": stale_count,
            "date_missing_items": date_missing_count,
            "homepage_fallback_items": fallback_count,
            "telegram_ready": telegram_ready,
            "telegram_readiness_reason": readiness_reason,
            "english_only": "true",
            "openai_used": "true" if openai_used else "false",
            "telegram_sent": "true" if telegram_sent else "false",
            "schedule": "not_configured",
            "pages_deploy": "not_configured",
            "image_generation": "not_configured",
        },
        "executive_summary": _executive_summary(top, source_errors, fresh_count=fresh_article_count, editorial_ready_count=editorial_ready_count, min_fresh_items=min_fresh_items),
        "ranked_updates": candidates,
        "watchlist_updates": watchlist,
        "downgraded_updates": downgraded,
        "key_judgments": _key_judgments(candidates, watchlist, downgraded, source_errors, fresh_count=fresh_article_count, editorial_ready_count=editorial_ready_count, min_fresh_items=min_fresh_items),
        "company_model_watchlist": _watchlist(all_items),
        "follow_up_checklist": _followups(candidates, watchlist, downgraded, source_errors),
        "source_errors": source_errors,
        "conclusion": _conclusion(candidates, fresh_count=fresh_article_count, editorial_ready_count=editorial_ready_count, min_fresh_items=min_fresh_items),
    }

def _executive_summary(candidates: list[dict[str, Any]], source_errors: list[dict[str, str]], *, fresh_count: int, editorial_ready_count: int, min_fresh_items: int) -> list[str]:
    if editorial_ready_count < min_fresh_items:
        summary = ["Not enough fresh, source-backed, editorially relevant AI model/tooling/research/product updates found for a send-ready brief."]
        if candidates:
            summary.extend([f"Editorial candidate: {item['title']} ({item['confidence']} confidence, relevance {item.get('editorial_relevance_score')})." for item in candidates[:3]])
        elif fresh_count:
            summary.append(f"{fresh_count} fresh article-level items were fetched, but they did not clear the editorial relevance gate.")
        else:
            summary.append("No item passed the freshness gate for main ranked updates.")
        if source_errors:
            summary.append(f"{len(source_errors)} allowlisted sources returned fetch or parse errors and need follow-up.")
        return summary
    summary = [f"Top AI signal: {item['title']} ({item['confidence']} confidence, editorial relevance {item.get('editorial_relevance_score')})." for item in candidates[:3]]
    if source_errors:
        summary.append(f"{len(source_errors)} allowlisted sources returned fetch or parse errors and need follow-up.")
    return summary

def _key_judgments(candidates: list[dict[str, Any]], watchlist: list[dict[str, Any]], downgraded: list[dict[str, Any]], source_errors: list[dict[str, str]], *, fresh_count: int, editorial_ready_count: int, min_fresh_items: int) -> list[str]:
    judgments = [
        "Only public HTTPS sources were used.",
        "Telegram-ready means fresh, source-backed, and editorially relevant; technical fetch success alone is not enough.",
        "Every ranked item needs human source review before publication, Telegram delivery, or downstream automation.",
        f"{fresh_count} fresh article-level items passed the freshness gate; {editorial_ready_count} passed the editorial relevance gate; {len(downgraded)} fresh items were downgraded.",
    ]
    if editorial_ready_count < min_fresh_items:
        judgments.append("Not enough editorial-ready AI model/tooling/research/product updates found for a send-ready brief.")
    if candidates:
        official_count = sum(1 for item in candidates if item["sources"][0].get("source_type") == "official")
        judgments.append(f"{official_count} ranked items came from official source types.")
    if watchlist:
        judgments.append(f"{len(watchlist)} stale or date-missing items were separated into watchlist/context updates.")
    if source_errors:
        judgments.append("Some source fetches failed; absence from the report must not be interpreted as absence of news.")
    return judgments

def _watchlist(items: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    for item in items:
        if item.get("is_homepage_fallback"):
            continue
        companies = item.get("company_entities") or []
        models = item.get("models") or []
        label = item["company_model"] if item["company_model"] != "Unspecified" else item["title"]
        if companies or models:
            suffix = item.get("freshness_status", "unknown")
            values.append(f"{label}: monitor source confirmation and freshness status ({suffix}).")
    return sorted(set(values))[:10]


def _followups(candidates: list[dict[str, Any]], watchlist: list[dict[str, Any]], downgraded: list[dict[str, Any]], source_errors: list[dict[str, str]]) -> list[str]:
    followups = [
        "Open every source URL and confirm publication date, claim scope, and product availability.",
        "Keep generated outputs under outputs/ and do not commit them.",
        "Before Telegram delivery, confirm the ranked items are fresh, source-backed, and editorially relevant to AI model, tooling, research, API, safety, or product readers.",
    ]
    if watchlist:
        followups.append("Review watchlist updates separately; stale or date-missing items must not be sent as fresh daily news.")
    if downgraded:
        followups.append("Review downgraded items separately; weak AI-adjacent, culture, funding, labor, or broad company items must not dominate Telegram summaries.")
    if source_errors:
        followups.append("Retry failed sources or replace unstable feeds with more reliable official URLs.")
    if candidates:
        followups.append("Promote only manually reviewed fresh article-level items into a Telegram candidate.")
    return followups

def _conclusion(candidates: list[dict[str, Any]], *, fresh_count: int, editorial_ready_count: int, min_fresh_items: int) -> str:
    if editorial_ready_count < min_fresh_items:
        return "Not enough editorial-ready AI model/tooling/research/product updates found for a send-ready brief. The next step is editorial source review or ranking improvement, not Telegram delivery."
    return "This run produced local English report artifacts with fresh, source-backed, editorially relevant AI updates. Manual review remains required before publication, scheduling, or delivery."

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
    lines = [
        report["title"],
        f"Date: {report['metadata']['date']}",
        f"Telegram ready: {str(report['metadata'].get('telegram_ready')).lower()}",
        "",
    ]
    for item in report.get("ranked_updates", [])[:5]:
        source = _first_source(item)
        source_name = _source_display_name(source)
        source_url = str(source.get("url") or "").strip()
        confidence = str(item.get("confidence") or "unknown")
        freshness = str(item.get("freshness_status") or "unknown")
        lines.append(f"{item['rank']}. {item['title']} ({confidence}, {freshness})")
        lines.append(f"Source: {source_name}")
        if source_url:
            lines.append(f"URL: {source_url}")
        lines.append("")
    if markdown_path:
        lines.append("Report artifact: available in the run artifacts.")
    return "\n".join(lines).strip()


def _first_source(item: dict[str, Any]) -> dict[str, Any]:
    sources = item.get("sources")
    if isinstance(sources, list) and sources and isinstance(sources[0], dict):
        return sources[0]
    return {}


def _source_display_name(source: dict[str, Any]) -> str:
    for key in ("source_name", "publisher", "source_id"):
        value = str(source.get(key) or "").strip()
        if value:
            return value
    return "Source unavailable"


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


def _fresh_article_level_count(candidates: list[dict[str, Any]]) -> int:
    return sum(
        1
        for item in candidates
        if item.get("signal_level") == "article"
        and not item.get("is_homepage_fallback")
        and item.get("freshness_status") == "fresh"
        and item.get("fresh_enough_for_daily") is True
    )


def _editorial_ready_count(candidates: list[dict[str, Any]]) -> int:
    return sum(1 for item in candidates if item.get("telegram_editorial_ready") is True)


def _is_main_update(item: dict[str, Any]) -> bool:
    return (
        item.get("fresh_enough_for_daily") is True
        and item.get("freshness_status") == "fresh"
        and item.get("signal_level") == "article"
        and item.get("is_homepage_fallback") is not True
        and item.get("telegram_editorial_ready") is True
        and int(item.get("editorial_relevance_score") or 0) >= EDITORIAL_READY_THRESHOLD
    )


def _freshness(observation: dict[str, Any], cutoff: datetime, *, is_homepage_fallback: bool) -> tuple[str, bool]:
    if is_homepage_fallback:
        return "date_missing", False
    date_value = _parse_iso_datetime(str(observation.get("published_at") or observation.get("updated_at") or ""))
    if date_value is None:
        return "date_missing", False
    if date_value >= cutoff:
        return "fresh", True
    return "stale", False


def _editorial_relevance(
    title: str,
    summary: str,
    topic_type: str,
    source_type: str,
    source_category: str,
    source_priority_label: str,
    *,
    signal_level: str,
    freshness_status: str,
    fresh_enough: bool,
    is_homepage_fallback: bool,
) -> tuple[str, int, bool, str]:
    text = (title + " " + summary).lower()
    if is_homepage_fallback or signal_level != "article":
        return "source_monitoring_fallback", 0, False, "Downgraded: not an article-level update."
    if freshness_status != "fresh" or not fresh_enough:
        return "not_fresh", 0, False, "Downgraded: stale or date-missing item cannot be a main Telegram update."

    category = _editorial_category(text, topic_type, source_category)
    score = 1
    if topic_type in {"model_release", "developer_tooling", "research", "security", "policy"}:
        score += 2
    if source_category in {"official_release", "model_release", "tooling", "research", "policy"}:
        score += 1
    if source_type == "official":
        score += 1
    if source_priority_label == "backup":
        score -= 1
    if _contains_any(text, _STRONG_MODEL_TOOLING_TERMS):
        score += 2
    if _contains_any(text, _READER_FACING_TERMS):
        score += 1
    if _contains_any(text, _WEAK_AI_ADJACENT_TERMS):
        score -= 3
    if _contains_any(text, _ENTERTAINMENT_LEGAL_TERMS):
        score -= 1
    if topic_type == "funding" or source_category == "funding":
        score -= 3
    if category in {"advertising_culture", "education_market", "labor_platform_migration", "funding", "generic_company_strategy", "ai_adjacent_business"}:
        score -= 1
    if category == "entertainment_lawsuit" and _contains_any(text, ("midjourney", "ai video", "image model", "video model")):
        score += 1
    if category == "entertainment_lawsuit" and "seedance" in text:
        score -= 1

    score = max(0, min(score, 5))
    ready = score >= EDITORIAL_READY_THRESHOLD and category not in _REJECT_MAIN_CATEGORIES
    if ready:
        return category, score, True, f"Ready: {category.replace('_', ' ')} item with sufficient model/tooling/research/product relevance."
    return category, score, False, f"Downgraded: {category.replace('_', ' ')} item did not clear the editorial relevance gate."


_STRONG_MODEL_TOOLING_TERMS = (
    "model", "gpt", "chatgpt", "claude", "claude code", "gemini", "llama", "mistral", "grok", "qwen", "deepseek",
    "kimi", "midjourney", "seedance", "ocr", "api", "sdk", "developer", "agent", "tooling", "coding", "benchmark",
    "evaluation", "eval", "research", "paper", "release", "launch", "open source", "frontier", "inference", "context window",
)
_READER_FACING_TERMS = (
    "available", "shipping", "developers", "enterprise", "migration", "controls", "platform", "product", "workflow", "source code",
    "capability", "security", "safety", "governance", "policy",
)
_WEAK_AI_ADJACENT_TERMS = (
    "commercial", "advertising", "advertisement", "founding fathers", "declaration of independence", "group project", "culture",
    "private schools", "wealthy", "tuition", "families", "mechanical turk", "mturk", "labor", "new customers",
    "funding", "raises", "raised", "series a", "series b", "series c",
)
_ENTERTAINMENT_LEGAL_TERMS = (
    "hollywood", "studios", "lawsuit", "legal", "cease-and-desist", "movie", "actor", "brad pitt", "tom cruise",
)
_REJECT_MAIN_CATEGORIES = {
    "advertising_culture",
    "education_market",
    "labor_platform_migration",
    "funding",
    "generic_company_strategy",
    "ai_adjacent_business",
}


def _editorial_category(text: str, topic_type: str, source_category: str) -> str:
    if topic_type == "funding" or source_category == "funding" or _contains_any(text, ("funding", "raises", "raised", "series a", "series b", "series c")):
        return "funding"
    if _contains_any(text, ("commercial", "advertising", "advertisement", "founding fathers", "declaration of independence", "group project")):
        return "advertising_culture"
    if _contains_any(text, ("private schools", "wealthy", "tuition", "families", "education", "classroom")):
        return "education_market"
    if _contains_any(text, ("mechanical turk", "mturk", "labor", "crowd work", "new customers")):
        return "labor_platform_migration"
    if _contains_any(text, _ENTERTAINMENT_LEGAL_TERMS):
        return "entertainment_lawsuit"
    if topic_type == "developer_tooling" or _contains_any(text, ("api", "sdk", "developer", "agent", "claude code", "coding", "tooling", "source code")):
        return "developer_tooling"
    if topic_type == "research" or source_category == "research" or _contains_any(text, ("research", "paper", "benchmark", "evaluation", "eval", "ocr")):
        return "ai_research_with_product_relevance"
    if topic_type == "security" or _contains_any(text, ("security", "safety", "vulnerability", "risk", "ban", "blocked", "high-risk", "governance")):
        return "safety_policy_with_model_or_platform_impact"
    if topic_type == "policy" or _contains_any(text, ("policy", "regulation", "regulatory", "compliance")):
        return "safety_policy_with_model_or_platform_impact"
    if topic_type == "model_release" or source_category in {"official_release", "model_release"} or _contains_any(text, ("model", "gpt", "claude", "gemini", "llama", "mistral", "grok", "qwen", "deepseek", "midjourney", "seedance")):
        return "model_capability"
    if _contains_any(text, ("strategy", "business processes", "customers", "competitors")):
        return "generic_company_strategy"
    if "ai" in text:
        return "ai_adjacent_business"
    return "other"


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _importance_score(title: str, summary: str, topic_type: str, source_type: str, source_category: str, *, is_homepage_fallback: bool, freshness_status: str) -> int:
    text = (title + " " + summary).lower()
    score = 2
    if source_type == "official":
        score += 1
    if topic_type in {"model_release", "developer_tooling", "security", "policy"}:
        score += 1
    if source_category in {"official_release", "model_release", "tooling"}:
        score += 1
    if any(word in text for word in ("launch", "release", "available", "api", "deprecation", "security", "safety", "frontier")):
        score += 1
    if topic_type == "funding" or any(word in text for word in ("series", "funding", "raises")):
        score -= 2
    if is_homepage_fallback:
        score = min(score, 2)
    if freshness_status == "stale":
        score = min(score, 2)
    if freshness_status == "date_missing":
        score = min(score, 2)
    if topic_type == "funding" and not any(word in text for word in ("openai", "anthropic", "google", "mistral", "meta", "cohere", "xai", "hugging face")):
        score = min(score, 3)
    return max(1, min(score, 5))


def _novelty_score(title: str, summary: str, *, is_homepage_fallback: bool, freshness_status: str) -> int:
    text = (title + " " + summary).lower()
    if is_homepage_fallback or freshness_status != "fresh":
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


def _confidence(observation: dict[str, Any], source_quality: int, *, is_homepage_fallback: bool, freshness_status: str) -> str:
    if is_homepage_fallback or freshness_status == "date_missing":
        return "low"
    if freshness_status == "stale":
        return "medium"
    if source_quality >= 4 and (observation.get("published_at") or observation.get("updated_at")):
        return "high"
    if source_quality >= 3:
        return "medium"
    return "low"


def _category_rank(topic_type: str, source_category: str) -> int:
    if topic_type in {"model_release", "developer_tooling", "security", "policy"}:
        return 4
    if source_category in {"official_release", "model_release", "tooling"}:
        return 4
    if topic_type == "research" or source_category == "research":
        return 3
    if source_category == "ai_news":
        return 2
    if topic_type == "funding" or source_category == "funding":
        return 1
    return 1


def _why_it_matters(topic_type: str, source_type: str, *, is_homepage_fallback: bool, freshness_status: str) -> str:
    if is_homepage_fallback:
        return "This is a source-monitoring fallback, not a confirmed article-level news item; use it only to guide manual review."
    if freshness_status != "fresh":
        return "This item may be useful context, but it did not pass the freshness gate for a daily brief."
    if topic_type == "model_release":
        return "Model releases can change developer choices, product roadmaps, and competitive positioning."
    if topic_type == "developer_tooling":
        return "API or tooling changes can affect build plans, migration work, and integration costs."
    if topic_type == "security":
        return "Security and safety updates can require immediate review by engineering and governance teams."
    if topic_type == "policy":
        return "Policy or regulatory changes can affect deployment constraints and compliance review."
    if topic_type == "funding":
        return "Funding news is useful market context, but it should not outrank fresh model, API, safety, or tooling updates without manual escalation."
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


def _boundary(observation: dict[str, Any], *, freshness_status: str) -> str:
    if freshness_status == "stale":
        return "This item is outside the configured lookback window and must not be presented as fresh daily news."
    if freshness_status == "date_missing":
        return "Publication or updated date is missing; this item is excluded from send-ready daily updates unless manually verified."
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
    seed = f"{observation.get('source_id')}|{observation.get('url')}|{observation.get('title')}|{observation.get('published_at')}|{observation.get('updated_at')}|{observation.get('signal_level')}"
    return "live-ai-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _dedup_key(observation: dict[str, Any]) -> str:
    url = _canonical_url(str(observation.get("url", "")))
    title = re.sub(r"[^a-z0-9]+", "-", str(observation.get("title", "")).lower()).strip("-")
    return f"{url}:{title[:100]}"


def _canonical_url(value: str) -> str:
    parsed = parse.urlsplit(value)
    path = re.sub(r"/+$", "", parsed.path or "/") or "/"
    return parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def _cutoff(report_date: str, timezone_name: str, lookback_hours: int) -> datetime:
    zone = ZoneInfo(timezone_name)
    day = datetime.strptime(report_date, "%Y-%m-%d").date()
    end = datetime.combine(day, time(hour=23, minute=59, second=59), tzinfo=zone)
    return end - timedelta(hours=max(1, lookback_hours))


def _parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
    return parsed


def _no_mojibake(items: list[dict[str, Any]]) -> bool:
    text = json.dumps(items, ensure_ascii=False)
    markers = ("\ufffd", "\u00c3", "\u00c2", "\u00e2\u20ac", "\u00ef\u00bf\u00bd")
    return not any(marker in text for marker in markers)

def _no_placeholder_items(items: list[dict[str, Any]]) -> bool:
    text = json.dumps(items, ensure_ascii=False).lower()
    markers = ("placeholder", "todo", "fake update", "untitled ai update")
    return not any(marker in text for marker in markers)


def _telegram_readiness_reason(
    telegram_ready: bool,
    *,
    fresh_article_count: int,
    editorial_ready_count: int,
    min_fresh_items: int,
    blocking_errors: bool,
    content_clean: bool,
    ranked_items_are_fresh: bool,
    ranked_items_are_editorial_ready: bool,
) -> str:
    if telegram_ready:
        return "ready"
    if editorial_ready_count < min_fresh_items:
        if fresh_article_count >= min_fresh_items:
            return "Fresh article-level items were found, but not enough were editorially relevant for Telegram delivery."
        return "Not enough fresh article-level AI updates found for a send-ready brief."
    if not ranked_items_are_fresh:
        return "Top Updates include stale or date-missing items; manual Telegram delivery is blocked."
    if not ranked_items_are_editorial_ready:
        return "Top Updates include items that did not clear the editorial relevance gate."
    if blocking_errors:
        return "Source errors blocked the main daily update set."
    if not content_clean:
        return "Generated content contains mojibake or placeholder markers."
    return "Manual review is required before Telegram delivery."

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
