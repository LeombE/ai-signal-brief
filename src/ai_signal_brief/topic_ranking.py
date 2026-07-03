from __future__ import annotations

from dataclasses import dataclass
import copy
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

from .topic_validation import validate_topics_path
from .validation import find_secret_like_values, find_public_safety_issues

RANKING_SCHEMA_VERSION = "1.0.0"
WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
CONFIDENCE_ADJUSTMENT = {"high": 0.35, "medium": 0.0, "low": -0.45}
STATUS_PENALTY = {
    "new": 0.0,
    "update": 0.0,
    "follow_up": 0.1,
    "unresolved": 0.75,
    "duplicate": 1.0,
    "rejected": 2.0,
    "quiet_day_note": 1.25,
}
STRONG_SIGNAL_TYPES = {"official_release", "release_notes", "model_card", "security_advisory", "changelog", "repository_release"}
STRONG_SOURCE_TYPES = {"official", "paper", "repository", "regulatory"}
CAUTIOUS_SOURCE_TYPES = {"news", "social"}
PRIVATE_AI_MARKER = "AI" + "\u65e5\u62a5"
CHAT_MARKER = "chat" + "_id"
ENV_MARKER = "." + "env"
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


class TopicRankingError(RuntimeError):
    """Raised when topic candidates cannot be ranked safely."""


@dataclass(frozen=True)
class TopicRankingResult:
    input_path: Path
    ranked: dict[str, Any]

    @property
    def topics(self) -> list[dict[str, Any]]:
        topics = self.ranked.get("ranked_topics", [])
        return topics if isinstance(topics, list) else []


def rank_topics_from_path(
    path: str | Path,
    *,
    top_n: int | None = None,
    include_unresolved: bool = True,
) -> TopicRankingResult:
    topic_path = Path(path)
    validation = validate_topics_path(topic_path)
    if not validation.ok:
        raise TopicRankingError("invalid topic candidates JSON: " + "; ".join(validation.errors))
    with topic_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise TopicRankingError("topic candidates JSON must be an object")
    ranked = rank_topics(data, top_n=top_n, include_unresolved=include_unresolved)
    _reject_unsafe_values(ranked)
    return TopicRankingResult(input_path=topic_path, ranked=ranked)


def rank_topics(data: dict[str, Any], *, top_n: int | None = None, include_unresolved: bool = True) -> dict[str, Any]:
    if top_n is not None and top_n < 1:
        raise TopicRankingError("top-n must be a positive integer")

    observations = _observations_by_id(data)
    scored_topics = [_ranked_topic(topic, observations) for topic in data.get("topics", []) if isinstance(topic, dict)]
    dedup_audit = _dedup_audit(scored_topics)
    _apply_dedup_status(scored_topics, dedup_audit)

    filtered = [topic for topic in scored_topics if include_unresolved or topic["candidate_status"] != "unresolved"]
    if not filtered and scored_topics:
        filtered = list(scored_topics)
    ranked_topics = sorted(filtered, key=_ranking_sort_key)
    for rank, topic in enumerate(ranked_topics, start=1):
        topic["rank"] = rank

    visible_topics = ranked_topics[:top_n] if top_n is not None else ranked_topics
    return {
        "schema_version": RANKING_SCHEMA_VERSION,
        "source_scan_id": data.get("scan_id"),
        "scan_date": data.get("scan_date"),
        "generated_at": data.get("generated_at"),
        "timezone": data.get("timezone"),
        "ranking_formula": {
            "source_quality_score_weight": 0.22,
            "material_update_score_weight": 0.28,
            "importance_score_weight": 0.32,
            "novelty_score_weight": 0.18,
            "confidence_adjustment": CONFIDENCE_ADJUSTMENT,
            "status_penalty": STATUS_PENALTY,
            "uncertainty_note_penalty_each": 0.18,
            "safety_flag_penalty_each": 0.12,
            "strong_material_evidence_bonus": 0.25,
            "news_or_social_only_penalty": 0.25,
        },
        "ranked_topics": visible_topics,
        "total_topics": len(scored_topics),
        "returned_topics": len(visible_topics),
        "include_unresolved": include_unresolved,
        "top_n": top_n,
        "dedup_audit": dedup_audit,
        "unresolved_items": copy.deepcopy(data.get("unresolved_items", [])),
        "provenance": {
            "mode": "offline_ranking_only",
            "validated_before_ranking": True,
            "live_fetching": False,
            "telegram_delivery": False,
            "openai_api_usage": False,
            "image_generation": False,
            "docx_generation": False,
        },
    }


def write_ranked_topics_output(ranked: dict[str, Any], output_path: str | Path, *, repo_root: str | Path | None = None) -> Path:
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    destination = _resolve_safe_outputs_path(output_path, root)
    _reject_unsafe_values(ranked, {"output_path": destination.relative_to(root).as_posix()})
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(ranked, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination


def render_topic_ranking_summary(result: TopicRankingResult, *, explain: bool = False) -> str:
    ranked = result.ranked
    lines = [
        "Topic ranking PASS",
        f"Input: {result.input_path}",
        f"Scan date: {ranked.get('scan_date')}",
        f"Topics shown: {ranked.get('returned_topics')} of {ranked.get('total_topics')}",
        "",
        "Ranked topics:",
    ]
    for topic in ranked.get("ranked_topics", []):
        lines.append(
            f"{topic['rank']}. {topic['topic_id']} | score={topic['ranking_score']:.3f} | "
            f"status={topic['candidate_status']} | dedup={topic['dedup_status']} | material={topic['material_update_signal']}"
        )
        lines.append(f"   {topic['topic_title']}")
        if explain:
            explanation = topic.get("ranking_explanation", {})
            parts = [f"{key}={value}" for key, value in explanation.items()]
            lines.append("   explain: " + ", ".join(parts))
    lines.append("")
    lines.append("Dedup audit:")
    for entry in ranked.get("dedup_audit", []):
        lines.append(
            f"- {entry['dedup_key']}: canonical={entry['canonical_topic_id']}; "
            f"topics={', '.join(entry['topic_ids'])}; related={', '.join(entry['related_topic_ids']) or 'none'}"
        )
    return "\n".join(lines)


def _ranked_topic(topic: dict[str, Any], observations: dict[str, dict[str, Any]]) -> dict[str, Any]:
    topic_copy = copy.deepcopy(topic)
    observed = [observations[obs_id] for obs_id in topic.get("source_observation_ids", []) if obs_id in observations]
    material_signal, material_adjustment = _material_update_signal(topic, observed)
    uncertainty_penalty = min(1.0, len(topic.get("uncertainty_notes", [])) * 0.18)
    safety_penalty = min(0.9, len(topic.get("safety_flags", [])) * 0.12)
    status_penalty = STATUS_PENALTY.get(str(topic.get("candidate_status")), 0.5)
    confidence_adjustment = CONFIDENCE_ADJUSTMENT.get(str(topic.get("confidence")), -0.2)
    base_score = (
        _score(topic, "importance_score") * 0.32
        + _score(topic, "material_update_score") * 0.28
        + _score(topic, "source_quality_score") * 0.22
        + _score(topic, "novelty_score") * 0.18
    )
    ranking_score = max(0.0, base_score + confidence_adjustment + material_adjustment - uncertainty_penalty - safety_penalty - status_penalty)
    topic_copy.update(
        {
            "rank": None,
            "ranking_score": round(ranking_score, 3),
            "dedup_status": "candidate",
            "material_update_signal": material_signal,
            "ranking_explanation": {
                "base_score": round(base_score, 3),
                "confidence_adjustment": round(confidence_adjustment, 3),
                "material_evidence_adjustment": round(material_adjustment, 3),
                "uncertainty_penalty": round(uncertainty_penalty, 3),
                "safety_flags_penalty": round(safety_penalty, 3),
                "status_penalty": round(status_penalty, 3),
            },
        }
    )
    return topic_copy


def _material_update_signal(topic: dict[str, Any], observations: list[dict[str, Any]]) -> tuple[str, float]:
    if topic.get("candidate_status") == "quiet_day_note":
        return "quiet_day", 0.0
    raw_signal_types = {str(observation.get("raw_signal_type", "")).lower() for observation in observations}
    source_types = {str(observation.get("source_type", "")).lower() for observation in observations}
    if raw_signal_types & STRONG_SIGNAL_TYPES or source_types & STRONG_SOURCE_TYPES:
        if topic.get("candidate_status") == "unresolved":
            return "strong_evidence_but_unresolved", 0.05
        return "strong_material_evidence", 0.25
    if source_types and source_types <= CAUTIOUS_SOURCE_TYPES:
        return "cautious_news_or_social_only", -0.25
    if observations:
        return "moderate_material_evidence", 0.0
    return "no_source_observation", -0.35


def _dedup_audit(scored_topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    related_pairs: set[tuple[str, str]] = set()
    topic_ids = {str(topic.get("topic_id")) for topic in scored_topics}
    for topic in scored_topics:
        dedup_key = str(topic.get("dedup_key") or topic.get("topic_id"))
        group = groups.setdefault(dedup_key, {"dedup_key": dedup_key, "topic_ids": [], "related_topic_ids": set()})
        group["topic_ids"].append(str(topic.get("topic_id")))
        for related_id in topic.get("related_topic_ids", []):
            if related_id in topic_ids:
                group["related_topic_ids"].add(str(related_id))
                related_pairs.add(tuple(sorted((str(topic.get("topic_id")), str(related_id)))))
    for left, right in sorted(related_pairs):
        key = "related:" + ":".join((left, right))
        groups.setdefault(key, {"dedup_key": key, "topic_ids": [left, right], "related_topic_ids": {left, right}})
    audit: list[dict[str, Any]] = []
    for group in groups.values():
        topic_ids_in_group = list(dict.fromkeys(group["topic_ids"]))
        canonical = _canonical_topic_id(topic_ids_in_group, scored_topics)
        audit.append(
            {
                "dedup_key": group["dedup_key"],
                "canonical_topic_id": canonical,
                "topic_ids": topic_ids_in_group,
                "related_topic_ids": sorted(group["related_topic_ids"]),
                "duplicate_or_related_count": max(0, len(set(topic_ids_in_group + sorted(group["related_topic_ids"]))) - 1),
                "action": "mark_duplicate_or_related_for_review" if len(topic_ids_in_group) > 1 or group["related_topic_ids"] else "single_candidate",
            }
        )
    audit.sort(key=lambda entry: (entry["dedup_key"], entry["canonical_topic_id"]))
    return audit


def _apply_dedup_status(scored_topics: list[dict[str, Any]], audit: list[dict[str, Any]]) -> None:
    canonical_by_topic: dict[str, set[str]] = {}
    duplicate_or_related_ids: set[str] = set()
    for entry in audit:
        ids = set(entry.get("topic_ids", [])) | set(entry.get("related_topic_ids", []))
        if len(ids) <= 1:
            continue
        canonical = str(entry.get("canonical_topic_id"))
        for topic_id in ids:
            canonical_by_topic.setdefault(topic_id, set()).add(canonical)
            if topic_id != canonical:
                duplicate_or_related_ids.add(topic_id)
    for topic in scored_topics:
        topic_id = str(topic.get("topic_id"))
        if topic_id in duplicate_or_related_ids or topic.get("candidate_status") == "duplicate":
            topic["dedup_status"] = "duplicate_or_related"
        elif topic_id in canonical_by_topic:
            topic["dedup_status"] = "canonical_in_dedup_group"
        else:
            topic["dedup_status"] = "unique"


def _canonical_topic_id(topic_ids: list[str], scored_topics: list[dict[str, Any]]) -> str:
    by_id = {str(topic.get("topic_id")): topic for topic in scored_topics}
    candidates = [by_id[topic_id] for topic_id in topic_ids if topic_id in by_id]
    if not candidates:
        return topic_ids[0] if topic_ids else ""
    candidates.sort(key=_ranking_sort_key)
    return str(candidates[0].get("topic_id"))


def _ranking_sort_key(topic: dict[str, Any]) -> tuple[float, float, float, str]:
    return (
        -float(topic.get("ranking_score", 0.0)),
        -float(topic.get("importance_score", 0.0)),
        -float(topic.get("material_update_score", 0.0)),
        str(topic.get("topic_id", "")),
    )


def _observations_by_id(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    observations: dict[str, dict[str, Any]] = {}
    for observation in data.get("source_observations", []):
        if isinstance(observation, dict) and isinstance(observation.get("observation_id"), str):
            observations[observation["observation_id"]] = observation
    return observations


def _score(topic: dict[str, Any], key: str) -> float:
    value = topic.get(key)
    return float(value) if isinstance(value, (int, float)) else 0.0


def _resolve_safe_outputs_path(output_path: str | Path, repo_root: Path) -> Path:
    raw_output = str(output_path)
    if not raw_output or "://" in raw_output or raw_output.startswith(("~", "\\")):
        raise TopicRankingError("unsafe output path rejected")
    _reject_unsafe_path_text(raw_output)

    root = repo_root.resolve()
    outputs_root = (root / "outputs").resolve()
    candidate = Path(output_path)
    if not candidate.is_absolute():
        normalized = raw_output.replace("\\", "/")
        pure_path = PurePosixPath(normalized)
        if any(part in {"", ".."} for part in pure_path.parts):
            raise TopicRankingError("unsafe output path rejected")
        candidate = root / Path(*pure_path.parts)
    elif WINDOWS_DRIVE_PATH.match(raw_output) is None and raw_output.startswith("/"):
        raise TopicRankingError("unsafe output path rejected")

    resolved = candidate.resolve()
    try:
        resolved.relative_to(outputs_root)
    except ValueError as exc:
        raise TopicRankingError("output path must stay under outputs/") from exc
    return resolved


def _reject_unsafe_path_text(raw_output: str) -> None:
    value = {"output_path": raw_output}
    if find_secret_like_values(value) or find_public_safety_issues(value):
        raise TopicRankingError("unsafe output path rejected")
    lowered = raw_output.lower()
    if PRIVATE_AI_MARKER.lower() in lowered or CHAT_MARKER in lowered or ENV_MARKER in lowered:
        raise TopicRankingError("unsafe output path rejected")
    if any(marker in lowered for marker in LEGACY_MARKERS) or any(marker in lowered for marker in MISTAKEN_PROMPT_MARKERS):
        raise TopicRankingError("unsafe output path rejected")


def _reject_unsafe_values(*values: Any) -> None:
    for value in values:
        if find_secret_like_values(value) or find_public_safety_issues(value):
            raise TopicRankingError("ranked topic output contains unsafe values")
        for text in _iter_strings(value):
            lowered = text.lower()
            if PRIVATE_AI_MARKER.lower() in lowered or CHAT_MARKER in lowered or ENV_MARKER in lowered:
                raise TopicRankingError("ranked topic output contains unsafe values")
            if any(marker in lowered for marker in LEGACY_MARKERS) or any(marker in lowered for marker in MISTAKEN_PROMPT_MARKERS):
                raise TopicRankingError("ranked topic output contains unsafe values")


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
