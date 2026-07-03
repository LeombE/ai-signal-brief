from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .topic_ranking import TopicRankingError, rank_topics_from_path, render_topic_ranking_summary
from .topic_validation import VALID_CANDIDATE_STATUSES, VALID_TOPIC_TYPES, validate_topic_sources_path, validate_topics_path
from .validation import SOURCE_TYPES, find_public_safety_issues, find_secret_like_values

OBSERVATIONS_SCHEMA_VERSION = "1.0.0"
TOPIC_CANDIDATES_SCHEMA_VERSION = "1.0.0"
WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO_WITH_TIMEZONE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})$")
PRIVATE_AI_MARKER = "AI" + "\u65e5\u62a5"
CHAT_MARKER = "chat" + "_id"
ENV_MARKER = "." + "env"
FORBIDDEN_EXPORT_MARKERS = (".docx", ".htm", "telegram_export", "telegram-export", "raw_migration", "raw-historical-export")
LEGACY_MARKERS = (
    "build" + "_report_",
    "send" + "-telegram" + "-report",
    "generate" + "_ai_word" + "_report",
)
MISTAKEN_PROMPT_MARKERS = (
    "github" + "-daily" + "-intelligence",
    "00_MASTER" + "_PROMPT.md",
    "feat/public" + "-github" + "-daily" + "-intelligence",
)
STRONG_SIGNAL_TYPES = {"official_release", "release_notes", "model_card", "security_advisory", "repository_release", "changelog"}
CAUTIOUS_SOURCE_TYPES = {"news", "social"}
SOURCE_QUALITY_BY_TYPE = {
    "official": 5,
    "paper": 5,
    "repository": 4,
    "regulatory": 5,
    "news": 3,
    "social": 2,
    "other": 2,
}


class TopicDiscoveryError(RuntimeError):
    """Raised when offline mock topic discovery cannot run safely."""


@dataclass(frozen=True)
class TopicDiscoveryResult:
    output_path: Path
    candidates: dict[str, Any]
    ranked_summary: str | None = None


def discover_topics_from_mock(
    *,
    scan_date: str,
    sources_path: str | Path,
    mock_observations_path: str | Path,
    output_path: str | Path,
    timezone_name: str = "Asia/Kuala_Lumpur",
    rank: bool = False,
    quiet_ok: bool = False,
    repo_root: str | Path | None = None,
) -> TopicDiscoveryResult:
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    _validate_date(scan_date)
    generated_at = _generated_at(scan_date, timezone_name)

    source_registry = _load_valid_source_registry(sources_path)
    source_ids = _registry_source_ids(source_registry)
    mock_data = _load_mock_observations(mock_observations_path)
    observations = mock_data.get("observations", [])
    if not isinstance(observations, list):
        raise TopicDiscoveryError("mock observations must contain an observations array")
    if not observations and not quiet_ok:
        raise TopicDiscoveryError("quiet-day observations require --quiet-ok")
    _validate_mock_observations(mock_data, source_ids)

    candidates = _build_topic_candidates(
        scan_date=scan_date,
        generated_at=generated_at,
        timezone_name=timezone_name,
        source_registry=source_registry,
        observations=observations,
        quiet_ok=quiet_ok,
    )
    _reject_unsafe_values(candidates)

    destination = _resolve_safe_outputs_path(output_path, root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(candidates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    validation = validate_topics_path(destination)
    if not validation.ok:
        raise TopicDiscoveryError("generated topic candidates failed validation: " + "; ".join(validation.errors))

    ranked_summary: str | None = None
    if rank:
        try:
            ranked_result = rank_topics_from_path(destination, include_unresolved=True)
        except TopicRankingError as exc:
            raise TopicDiscoveryError("generated topic candidates failed ranking: " + str(exc)) from exc
        ranked_summary = render_topic_ranking_summary(ranked_result, explain=False)

    return TopicDiscoveryResult(output_path=destination, candidates=candidates, ranked_summary=ranked_summary)


def render_discovery_summary(result: TopicDiscoveryResult) -> str:
    lines = [
        "Topic discovery PASS",
        f"Output: {result.output_path}",
        f"Scan date: {result.candidates.get('scan_date')}",
        f"Topics: {len(result.candidates.get('topics', []))}",
        f"Source observations: {len(result.candidates.get('source_observations', []))}",
        f"Unresolved items: {len(result.candidates.get('unresolved_items', []))}",
    ]
    if result.ranked_summary:
        lines.append("")
        lines.append(result.ranked_summary)
    return "\n".join(lines)


def _load_valid_source_registry(path: str | Path) -> dict[str, Any]:
    validation = validate_topic_sources_path(path)
    if not validation.ok:
        raise TopicDiscoveryError("invalid topic source registry: " + "; ".join(validation.errors))
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise TopicDiscoveryError("topic source registry must be an object")
    return data


def _load_mock_observations(path: str | Path) -> dict[str, Any]:
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise TopicDiscoveryError("mock observations JSON is invalid") from exc
    if not isinstance(data, dict):
        raise TopicDiscoveryError("mock observations JSON must be an object")
    _reject_unsafe_values(data)
    if data.get("schema_version") != OBSERVATIONS_SCHEMA_VERSION:
        raise TopicDiscoveryError("mock observations schema_version must be 1.0.0")
    return data


def _validate_mock_observations(data: dict[str, Any], source_ids: set[str]) -> None:
    observations = data.get("observations")
    if not isinstance(observations, list):
        raise TopicDiscoveryError("mock observations must contain an observations array")
    seen: set[str] = set()
    for index, observation in enumerate(observations):
        path = f"observations[{index}]"
        if not isinstance(observation, dict):
            raise TopicDiscoveryError(f"{path} must be an object")
        _require_observation_fields(observation, path)
        observation_id = str(observation["observation_id"])
        if observation_id in seen:
            raise TopicDiscoveryError(f"{path}.observation_id duplicates observation id")
        seen.add(observation_id)
        source_id = str(observation["source_id"])
        if source_id not in source_ids:
            raise TopicDiscoveryError(f"{path}.source_id references unknown topic source")
        _require_enum(observation, "source_type", SOURCE_TYPES, path)
        _require_enum(observation, "topic_type", VALID_TOPIC_TYPES, path)
        _require_enum(observation, "candidate_status", VALID_CANDIDATE_STATUSES, path)
        _require_timestamp(observation, "observed_at", path)
        _require_optional_timestamp(observation, "published_at", path)
        _require_optional_timestamp(observation, "retrieved_at", path)
        _require_public_https_url(observation, "url", path)
        for field in ("companies", "models", "regions", "uncertainty_notes", "safety_flags", "related_observation_ids"):
            _require_string_list(observation, field, path)
        for field in ("material_update_score", "importance_score", "novelty_score"):
            _require_score(observation, field, path)
        if observation.get("confidence") not in {"high", "medium", "low"}:
            raise TopicDiscoveryError(f"{path}.confidence must be high, medium, or low")


def _require_observation_fields(observation: dict[str, Any], path: str) -> None:
    required = (
        "observation_id",
        "source_id",
        "title",
        "url",
        "observed_at",
        "published_at",
        "retrieved_at",
        "source_type",
        "raw_signal_type",
        "summary",
        "topic_type",
        "candidate_status",
        "companies",
        "models",
        "regions",
        "material_update_score",
        "importance_score",
        "novelty_score",
        "confidence",
        "uncertainty_notes",
        "safety_flags",
        "dedup_key",
        "related_observation_ids",
    )
    for field in required:
        if field not in observation:
            raise TopicDiscoveryError(f"{path}.{field} is required")
    for field in ("observation_id", "source_id", "title", "url", "observed_at", "source_type", "raw_signal_type", "summary", "topic_type", "candidate_status", "dedup_key"):
        if not isinstance(observation.get(field), str) or not observation.get(field):
            raise TopicDiscoveryError(f"{path}.{field} must be a non-empty string")


def _build_topic_candidates(
    *,
    scan_date: str,
    generated_at: str,
    timezone_name: str,
    source_registry: dict[str, Any],
    observations: list[Any],
    quiet_ok: bool,
) -> dict[str, Any]:
    if not observations and quiet_ok:
        return _quiet_day_candidates(scan_date, generated_at, timezone_name)

    source_quality = _source_quality_by_id(source_registry)
    source_observations: list[dict[str, Any]] = []
    topics: list[dict[str, Any]] = []
    unresolved_items: list[dict[str, str]] = []
    observation_to_topic: dict[str, str] = {}

    for observation in sorted((item for item in observations if isinstance(item, dict)), key=lambda item: str(item.get("observation_id", ""))):
        topic_id = _topic_id(observation)
        observation_id = str(observation["observation_id"])
        observation_to_topic[observation_id] = topic_id
        source_id = str(observation["source_id"])
        source_observations.append(_source_observation_entry(observation))
        uncertainty_notes = list(observation.get("uncertainty_notes", []))
        candidate_status = str(observation["candidate_status"])
        if observation.get("published_at") is None and candidate_status != "quiet_day_note":
            candidate_status = "unresolved"
            note = "Published time is not available in the mock observation."
            if note not in uncertainty_notes:
                uncertainty_notes.append(note)
        topic = {
            "topic_id": topic_id,
            "topic_title": str(observation["title"]),
            "candidate_status": candidate_status,
            "topic_type": str(observation["topic_type"]),
            "companies": list(observation.get("companies", [])),
            "models": list(observation.get("models", [])),
            "regions": list(observation.get("regions", [])),
            "source_observation_ids": [observation_id],
            "source_ids": [source_id],
            "primary_source_ids": [source_id],
            "material_update_score": _material_score(observation),
            "importance_score": int(observation["importance_score"]),
            "novelty_score": int(observation["novelty_score"]),
            "source_quality_score": source_quality.get(source_id, SOURCE_QUALITY_BY_TYPE.get(str(observation["source_type"]), 2)),
            "confidence": str(observation["confidence"]),
            "uncertainty_notes": uncertainty_notes,
            "review_recommendation": "needs_source_review" if candidate_status == "unresolved" else "include",
            "review_required": True,
            "safety_flags": list(observation.get("safety_flags", [])) + ["mock_observation", "manual_review_required"],
            "dedup_key": str(observation["dedup_key"]),
            "related_topic_ids": [],
        }
        topics.append(topic)
        if candidate_status == "unresolved":
            unresolved_items.append(
                {
                    "id": "unresolved-" + topic_id,
                    "topic_id": topic_id,
                    "reason": "Mock observation requires manual source or timing review before publication.",
                    "review_action": "Verify public source timing and claim scope before promotion.",
                }
            )

    _apply_related_topic_ids(topics, observations, observation_to_topic)
    dedup_groups = _dedup_groups(topics)
    topics.sort(key=lambda topic: str(topic["topic_id"]))
    source_observations.sort(key=lambda observation: str(observation["observation_id"]))
    unresolved_items.sort(key=lambda item: str(item["id"]))

    return {
        "schema_version": TOPIC_CANDIDATES_SCHEMA_VERSION,
        "scan_id": "mock-topic-scan-" + scan_date,
        "scan_date": scan_date,
        "generated_at": generated_at,
        "timezone": timezone_name,
        "topics": topics,
        "source_observations": source_observations,
        "dedup_groups": dedup_groups,
        "unresolved_items": unresolved_items,
        "provenance": {
            "generation_mode": "offline_mock_observations_only",
            "source_registry": "config/topic_sources.example.json",
            "live_fetching": False,
            "publication_status": "not_published",
            "telegram_delivery": "not_connected",
            "openai_api_usage": "not_configured",
            "image_generation": "not_configured",
            "docx_generation": "not_configured",
            "production_pages_deploy": "not_configured",
        },
    }


def _quiet_day_candidates(scan_date: str, generated_at: str, timezone_name: str) -> dict[str, Any]:
    topic_id = "topic-quiet-day-" + scan_date
    return {
        "schema_version": TOPIC_CANDIDATES_SCHEMA_VERSION,
        "scan_id": "mock-topic-scan-" + scan_date,
        "scan_date": scan_date,
        "generated_at": generated_at,
        "timezone": timezone_name,
        "topics": [
            {
                "topic_id": topic_id,
                "topic_title": "Quiet-day mock observation placeholder",
                "candidate_status": "quiet_day_note",
                "topic_type": "other",
                "companies": [],
                "models": [],
                "regions": [],
                "source_observation_ids": [],
                "source_ids": [],
                "primary_source_ids": [],
                "material_update_score": 0,
                "importance_score": 0,
                "novelty_score": 0,
                "source_quality_score": 0,
                "confidence": "low",
                "uncertainty_notes": ["No mock observation cleared review thresholds for this local dry run."],
                "review_recommendation": "defer",
                "review_required": True,
                "safety_flags": ["quiet_day", "mock_observation", "no_publication_candidate"],
                "dedup_key": "quiet-day-" + scan_date,
                "related_topic_ids": [],
            }
        ],
        "source_observations": [],
        "dedup_groups": [
            {
                "dedup_key": "quiet-day-" + scan_date,
                "topic_ids": [topic_id],
                "canonical_topic_id": topic_id,
                "reason": "Quiet-day placeholder generated from an empty local mock observation set.",
            }
        ],
        "unresolved_items": [],
        "provenance": {
            "generation_mode": "offline_mock_quiet_day_only",
            "live_fetching": False,
            "publication_status": "not_published",
            "telegram_delivery": "not_connected",
            "openai_api_usage": "not_configured",
            "image_generation": "not_configured",
            "docx_generation": "not_configured",
            "production_pages_deploy": "not_configured",
        },
    }


def _source_observation_entry(observation: dict[str, Any]) -> dict[str, Any]:
    return {
        "observation_id": str(observation["observation_id"]),
        "source_id": str(observation["source_id"]),
        "title": str(observation["title"]),
        "url": str(observation["url"]),
        "observed_at": str(observation["observed_at"]),
        "published_at": observation.get("published_at"),
        "retrieved_at": observation.get("retrieved_at"),
        "source_type": str(observation["source_type"]),
        "raw_signal_type": str(observation["raw_signal_type"]),
        "summary": str(observation["summary"]),
        "entities": {
            "companies": list(observation.get("companies", [])),
            "models": list(observation.get("models", [])),
            "regions": list(observation.get("regions", [])),
        },
        "content_hash": _content_hash(observation),
        "source_confidence": str(observation.get("confidence", "medium")),
        "safety_flags": list(observation.get("safety_flags", [])) + ["mock_observation"],
    }


def _material_score(observation: dict[str, Any]) -> int:
    score = int(observation["material_update_score"])
    raw_signal_type = str(observation.get("raw_signal_type", "")).lower()
    source_type = str(observation.get("source_type", "")).lower()
    if raw_signal_type in STRONG_SIGNAL_TYPES or source_type in {"official", "paper", "repository", "regulatory"}:
        return min(5, score + 1)
    if source_type in CAUTIOUS_SOURCE_TYPES:
        return max(0, score - 1)
    return score


def _apply_related_topic_ids(topics: list[dict[str, Any]], observations: list[Any], observation_to_topic: dict[str, str]) -> None:
    topics_by_id = {str(topic["topic_id"]): topic for topic in topics}
    for observation in observations:
        if not isinstance(observation, dict):
            continue
        topic_id = observation_to_topic.get(str(observation.get("observation_id")))
        if not topic_id or topic_id not in topics_by_id:
            continue
        related_topic_ids = []
        for related_observation_id in observation.get("related_observation_ids", []):
            related_topic_id = observation_to_topic.get(str(related_observation_id))
            if related_topic_id and related_topic_id != topic_id:
                related_topic_ids.append(related_topic_id)
        topics_by_id[topic_id]["related_topic_ids"] = sorted(set(related_topic_ids))


def _dedup_groups(topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[str]] = {}
    for topic in topics:
        groups.setdefault(str(topic["dedup_key"]), []).append(str(topic["topic_id"]))
    dedup_groups = []
    for dedup_key, topic_ids in sorted(groups.items()):
        sorted_ids = sorted(topic_ids)
        dedup_groups.append(
            {
                "dedup_key": dedup_key,
                "topic_ids": sorted_ids,
                "canonical_topic_id": sorted_ids[0],
                "reason": "Generated from shared mock observation dedup_key." if len(sorted_ids) > 1 else "Single mock observation candidate.",
            }
        )
    return dedup_groups


def _registry_source_ids(source_registry: dict[str, Any]) -> set[str]:
    return {str(source["id"]) for source in source_registry.get("sources", []) if isinstance(source, dict) and isinstance(source.get("id"), str)}


def _source_quality_by_id(source_registry: dict[str, Any]) -> dict[str, int]:
    quality: dict[str, int] = {}
    for source in source_registry.get("sources", []):
        if not isinstance(source, dict) or not isinstance(source.get("id"), str):
            continue
        source_type = str(source.get("source_type", ""))
        reliability = str(source.get("reliability_tier", ""))
        base = SOURCE_QUALITY_BY_TYPE.get(source_type, 2)
        if reliability == "primary":
            base = min(5, base + 1)
        elif reliability == "context":
            base = max(1, base - 1)
        quality[source["id"]] = base
    return quality


def _topic_id(observation: dict[str, Any]) -> str:
    seed = str(observation.get("observation_id") or observation.get("title") or observation.get("dedup_key"))
    slug = _slug(seed)
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
    return f"topic-{slug}-{digest}"


def _slug(value: str) -> str:
    lowered = value.lower()
    chars = []
    for char in lowered:
        if char.isalnum():
            chars.append(char)
        elif chars and chars[-1] != "-":
            chars.append("-")
    slug = "".join(chars).strip("-")
    return slug[:48] or "mock-topic"


def _content_hash(observation: dict[str, Any]) -> str:
    payload = json.dumps(
        {
            "source_id": observation.get("source_id"),
            "title": observation.get("title"),
            "url": observation.get("url"),
            "observed_at": observation.get("observed_at"),
            "summary": observation.get("summary"),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _generated_at(scan_date: str, timezone_name: str) -> str:
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise TopicDiscoveryError("timezone is invalid") from exc
    date_value = datetime.strptime(scan_date, "%Y-%m-%d").date()
    timestamp = datetime.combine(date_value, time(hour=4, minute=0, second=0), tzinfo=zone)
    return timestamp.isoformat()


def _validate_date(value: str) -> None:
    if not isinstance(value, str) or not DATE_ONLY.match(value):
        raise TopicDiscoveryError("date must be YYYY-MM-DD")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise TopicDiscoveryError("date must be YYYY-MM-DD") from exc


def _require_enum(obj: dict[str, Any], field: str, allowed: set[str], path: str) -> None:
    if obj.get(field) not in allowed:
        raise TopicDiscoveryError(f"{path}.{field} must be one of: {', '.join(sorted(allowed))}")


def _require_string_list(obj: dict[str, Any], field: str, path: str) -> None:
    value = obj.get(field)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise TopicDiscoveryError(f"{path}.{field} must be an array of strings")


def _require_score(obj: dict[str, Any], field: str, path: str) -> None:
    value = obj.get(field)
    if not isinstance(value, int) or not 0 <= value <= 5:
        raise TopicDiscoveryError(f"{path}.{field} must be an integer from 0 to 5")


def _require_timestamp(obj: dict[str, Any], field: str, path: str) -> None:
    value = obj.get(field)
    if not isinstance(value, str) or not ISO_WITH_TIMEZONE.match(value):
        raise TopicDiscoveryError(f"{path}.{field} must be ISO-8601 with timezone")


def _require_optional_timestamp(obj: dict[str, Any], field: str, path: str) -> None:
    value = obj.get(field)
    if value is not None and (not isinstance(value, str) or not ISO_WITH_TIMEZONE.match(value)):
        raise TopicDiscoveryError(f"{path}.{field} must be ISO-8601 with timezone or null")


def _require_public_https_url(obj: dict[str, Any], field: str, path: str) -> None:
    value = obj.get(field)
    if not isinstance(value, str) or not value:
        raise TopicDiscoveryError(f"{path}.{field} must be a non-empty string")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.hostname in {"localhost", "127.0.0.1", "0.0.0.0"}:
        raise TopicDiscoveryError(f"{path}.{field} must be public HTTPS")


def _resolve_safe_outputs_path(output_path: str | Path, repo_root: Path) -> Path:
    raw_output = str(output_path)
    if not raw_output or "://" in raw_output or raw_output.startswith(("~", "\\")):
        raise TopicDiscoveryError("unsafe output path rejected")
    _reject_unsafe_path_text(raw_output)
    root = repo_root.resolve()
    outputs_root = (root / "outputs").resolve()
    candidate = Path(output_path)
    if not candidate.is_absolute():
        normalized = raw_output.replace("\\", "/")
        pure_path = PurePosixPath(normalized)
        if any(part in {"", ".."} for part in pure_path.parts):
            raise TopicDiscoveryError("unsafe output path rejected")
        candidate = root / Path(*pure_path.parts)
    elif WINDOWS_DRIVE_PATH.match(raw_output) is None and raw_output.startswith("/"):
        raise TopicDiscoveryError("unsafe output path rejected")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(outputs_root)
    except ValueError as exc:
        raise TopicDiscoveryError("output path must stay under outputs/") from exc
    return resolved


def _reject_unsafe_path_text(raw_output: str) -> None:
    value = {"output_path": raw_output}
    if find_secret_like_values(value) or find_public_safety_issues(value):
        raise TopicDiscoveryError("unsafe output path rejected")
    lowered = raw_output.lower()
    if PRIVATE_AI_MARKER.lower() in lowered or CHAT_MARKER in lowered or ENV_MARKER in lowered:
        raise TopicDiscoveryError("unsafe output path rejected")
    if any(marker in lowered for marker in FORBIDDEN_EXPORT_MARKERS + LEGACY_MARKERS + MISTAKEN_PROMPT_MARKERS):
        raise TopicDiscoveryError("unsafe output path rejected")


def _reject_unsafe_values(*values: Any) -> None:
    for value in values:
        if find_secret_like_values(value) or find_public_safety_issues(value):
            raise TopicDiscoveryError("mock topic discovery input contains unsafe values")
        for text in _iter_strings(value):
            lowered = text.lower()
            if PRIVATE_AI_MARKER.lower() in lowered or CHAT_MARKER in lowered or ENV_MARKER in lowered:
                raise TopicDiscoveryError("mock topic discovery input contains unsafe values")
            if any(marker in lowered for marker in FORBIDDEN_EXPORT_MARKERS + LEGACY_MARKERS + MISTAKEN_PROMPT_MARKERS):
                raise TopicDiscoveryError("mock topic discovery input contains unsafe values")


def _iter_strings(value: Any) -> list[str]:
    strings: list[str] = []
    if isinstance(value, str):
        strings.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            strings.extend(_iter_strings(child))
    elif isinstance(value, list):
        for child in value:
            strings.extend(_iter_strings(child))
    return strings
