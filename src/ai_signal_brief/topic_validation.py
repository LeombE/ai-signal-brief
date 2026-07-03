from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .validation import (
    DATE_ONLY,
    ISO_8601_WITH_TIMEZONE,
    SOURCE_TYPES,
    ValidationResult,
    _load_json,
    _require_fields,
    _url_has_private_location,
    find_public_safety_issues,
    find_secret_like_values,
)

TOPIC_SOURCE_REGISTRY_REQUIRED_FIELDS = (
    "schema_version",
    "source_policy",
    "allowed_source_types",
    "categories",
    "sources",
)
TOPIC_SOURCE_CATEGORY_REQUIRED_FIELDS = ("id", "priority", "reliability_tier", "description")
TOPIC_SOURCE_ENTRY_REQUIRED_FIELDS = (
    "id",
    "title",
    "publisher",
    "url",
    "source_type",
    "category_id",
    "priority",
    "reliability_tier",
    "expected_update_frequency",
    "allowed_fetch_mode",
    "attribution_requirements",
    "safety_notes",
)
TOPIC_CANDIDATES_REQUIRED_FIELDS = (
    "schema_version",
    "scan_id",
    "scan_date",
    "generated_at",
    "timezone",
    "topics",
    "source_observations",
    "dedup_groups",
    "unresolved_items",
    "provenance",
)
TOPIC_REQUIRED_FIELDS = (
    "topic_id",
    "topic_title",
    "candidate_status",
    "topic_type",
    "companies",
    "models",
    "regions",
    "source_observation_ids",
    "source_ids",
    "primary_source_ids",
    "material_update_score",
    "importance_score",
    "novelty_score",
    "source_quality_score",
    "confidence",
    "uncertainty_notes",
    "review_recommendation",
    "review_required",
    "safety_flags",
    "dedup_key",
    "related_topic_ids",
)
SOURCE_OBSERVATION_REQUIRED_FIELDS = (
    "observation_id",
    "source_id",
    "title",
    "url",
    "observed_at",
    "source_type",
    "summary",
    "safety_flags",
)
VALID_RELIABILITY_TIERS = {"primary", "primary_or_context", "context"}
VALID_FETCH_MODES = {"manual_review", "public_feed", "repository_metadata", "official_page_snapshot", "manual_snapshot", "disabled"}
VALID_CANDIDATE_STATUSES = {"new", "update", "follow_up", "duplicate", "unresolved", "rejected", "quiet_day_note"}
VALID_TOPIC_TYPES = {"model_release", "product_release", "research", "benchmark", "developer_tooling", "security", "policy", "infrastructure", "company_strategy", "ecosystem", "other"}
VALID_CONFIDENCE = {"high", "medium", "low"}
VALID_REVIEW_RECOMMENDATIONS = {"include", "monitor", "defer", "reject", "needs_source_review"}
FORBIDDEN_EXPORT_MARKERS = (".docx", ".htm", "telegram_export", "telegram-export", "raw_migration", "raw-historical-export")
LEGACY_MARKERS = (
    "build" + "_report_",
    "send" + "-telegram" + "-report",
    "generate" + "_ai_word" + "_report",
)
PRIVATE_AI_MARKER = "AI" + "\u65e5\u62a5"
CHAT_MARKER = "chat" + "_id"
ENV_MARKER = "." + "env"


def validate_topic_sources_path(path: str | Path) -> ValidationResult:
    topic_sources_path = Path(path)
    data, errors = _load_json(topic_sources_path)
    if errors:
        return ValidationResult(topic_sources_path, tuple(errors))
    errors.extend(validate_topic_sources(data))
    errors.extend(_safety_errors(data))
    return ValidationResult(topic_sources_path, tuple(errors))


def validate_topics_path(path: str | Path, *, known_source_ids: set[str] | None = None) -> ValidationResult:
    topics_path = Path(path)
    data, errors = _load_json(topics_path)
    if errors:
        return ValidationResult(topics_path, tuple(errors))
    errors.extend(validate_topics(data, known_source_ids=known_source_ids))
    errors.extend(_safety_errors(data))
    return ValidationResult(topics_path, tuple(errors))


def validate_topic_sources(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["$ must be an object"]

    _require_fields(data, TOPIC_SOURCE_REGISTRY_REQUIRED_FIELDS, "$", errors)
    if not data.get("schema_version"):
        errors.append("$.schema_version must be present")
    if not data.get("source_policy"):
        errors.append("$.source_policy must be present")

    allowed_types = _validate_allowed_source_types(data.get("allowed_source_types"), errors)
    allowed_fetch_modes = set(data.get("allowed_fetch_modes", [])) if isinstance(data.get("allowed_fetch_modes"), list) else VALID_FETCH_MODES

    categories = data.get("categories")
    category_ids: set[str] = set()
    if not isinstance(categories, list) or not categories:
        errors.append("$.categories must be a non-empty array")
    else:
        for index, category in enumerate(categories):
            _validate_topic_source_category(category, index, category_ids, errors)

    sources = data.get("sources")
    source_ids: set[str] = set()
    if not isinstance(sources, list) or not sources:
        errors.append("$.sources must be a non-empty array")
    else:
        for index, source in enumerate(sources):
            _validate_topic_source_entry(source, index, category_ids, allowed_types, allowed_fetch_modes, source_ids, errors)

    return errors


def validate_topics(data: Any, *, known_source_ids: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["$ must be an object"]

    _require_fields(data, TOPIC_CANDIDATES_REQUIRED_FIELDS, "$", errors)
    _require_non_empty_string(data, "scan_id", "$", errors)
    _require_date(data, "scan_date", "$", errors)
    _require_timestamp(data, "generated_at", "$", errors)
    _require_non_empty_string(data, "timezone", "$", errors)

    observations = data.get("source_observations")
    observation_ids: set[str] = set()
    observation_source_ids: set[str] = set()
    if not isinstance(observations, list):
        errors.append("$.source_observations must be an array")
    else:
        for index, observation in enumerate(observations):
            _validate_source_observation(observation, index, observation_ids, observation_source_ids, errors)

    valid_source_ids = set(observation_source_ids)
    if known_source_ids:
        valid_source_ids.update(known_source_ids)

    topics = data.get("topics")
    topic_ids: set[str] = set()
    if not isinstance(topics, list):
        errors.append("$.topics must be an array")
    else:
        for index, topic in enumerate(topics):
            _validate_topic(topic, index, topic_ids, observation_ids, valid_source_ids, errors)

    dedup_groups = data.get("dedup_groups")
    if not isinstance(dedup_groups, list):
        errors.append("$.dedup_groups must be an array")
    else:
        for index, group in enumerate(dedup_groups):
            _validate_dedup_group(group, index, topic_ids, errors)

    unresolved_items = data.get("unresolved_items")
    if not isinstance(unresolved_items, list):
        errors.append("$.unresolved_items must be an array")
    else:
        for index, item in enumerate(unresolved_items):
            _validate_unresolved_item(item, index, topic_ids, errors)

    return errors


def _validate_allowed_source_types(value: Any, errors: list[str]) -> set[str]:
    if not isinstance(value, list) or not value:
        errors.append("$.allowed_source_types must be a non-empty array")
        return set()
    allowed: set[str] = set()
    for index, source_type in enumerate(value):
        if not isinstance(source_type, str) or not source_type:
            errors.append(f"$.allowed_source_types[{index}] must be a non-empty string")
            continue
        if source_type not in SOURCE_TYPES:
            errors.append(f"$.allowed_source_types[{index}] must be compatible with report source_type values")
        allowed.add(source_type)
    return allowed


def _validate_topic_source_category(category: Any, index: int, category_ids: set[str], errors: list[str]) -> None:
    path = f"$.categories[{index}]"
    if not isinstance(category, dict):
        errors.append(f"{path} must be an object")
        return
    _require_fields(category, TOPIC_SOURCE_CATEGORY_REQUIRED_FIELDS, path, errors)
    category_id = _require_non_empty_string(category, "id", path, errors)
    if category_id:
        if category_id in category_ids:
            errors.append(f"{path}.id duplicates category id '{category_id}'")
        category_ids.add(category_id)
    _require_positive_int(category, "priority", path, errors)
    _require_enum(category, "reliability_tier", VALID_RELIABILITY_TIERS, path, errors)


def _validate_topic_source_entry(source: Any, index: int, category_ids: set[str], allowed_types: set[str], allowed_fetch_modes: set[str], source_ids: set[str], errors: list[str]) -> None:
    path = f"$.sources[{index}]"
    if not isinstance(source, dict):
        errors.append(f"{path} must be an object")
        return
    _require_fields(source, TOPIC_SOURCE_ENTRY_REQUIRED_FIELDS, path, errors)
    source_id = _require_non_empty_string(source, "id", path, errors)
    if source_id:
        if source_id in source_ids:
            errors.append(f"{path}.id duplicates source id '{source_id}'")
        source_ids.add(source_id)
    source_type = _require_enum(source, "source_type", SOURCE_TYPES, path, errors)
    if source_type and allowed_types and source_type not in allowed_types:
        errors.append(f"{path}.source_type is not listed in allowed_source_types")
    category_id = _require_non_empty_string(source, "category_id", path, errors)
    if category_id and category_id not in category_ids:
        errors.append(f"{path}.category_id references unknown category id '{category_id}'")
    _require_positive_int(source, "priority", path, errors)
    _require_enum(source, "reliability_tier", VALID_RELIABILITY_TIERS, path, errors)
    _require_non_empty_string(source, "expected_update_frequency", path, errors)
    _require_enum(source, "allowed_fetch_mode", allowed_fetch_modes or VALID_FETCH_MODES, path, errors)
    _require_non_empty_string(source, "attribution_requirements", path, errors)
    _require_non_empty_string(source, "safety_notes", path, errors)
    _require_public_https_url(source, "url", path, errors)


def _validate_source_observation(observation: Any, index: int, observation_ids: set[str], observation_source_ids: set[str], errors: list[str]) -> None:
    path = f"$.source_observations[{index}]"
    if not isinstance(observation, dict):
        errors.append(f"{path} must be an object")
        return
    _require_fields(observation, SOURCE_OBSERVATION_REQUIRED_FIELDS, path, errors)
    observation_id = _require_non_empty_string(observation, "observation_id", path, errors)
    if observation_id:
        if observation_id in observation_ids:
            errors.append(f"{path}.observation_id duplicates source observation id '{observation_id}'")
        observation_ids.add(observation_id)
    source_id = _require_non_empty_string(observation, "source_id", path, errors)
    if source_id:
        observation_source_ids.add(source_id)
    _require_public_https_url(observation, "url", path, errors)
    _require_timestamp(observation, "observed_at", path, errors)
    _require_optional_timestamp(observation, "published_at", path, errors)
    _require_optional_timestamp(observation, "retrieved_at", path, errors)
    _require_enum(observation, "source_type", SOURCE_TYPES, path, errors)
    _require_string_list(observation, "safety_flags", path, errors)


def _validate_topic(topic: Any, index: int, topic_ids: set[str], observation_ids: set[str], valid_source_ids: set[str], errors: list[str]) -> None:
    path = f"$.topics[{index}]"
    if not isinstance(topic, dict):
        errors.append(f"{path} must be an object")
        return
    _require_fields(topic, TOPIC_REQUIRED_FIELDS, path, errors)
    topic_id = _require_non_empty_string(topic, "topic_id", path, errors)
    if topic_id:
        if topic_id in topic_ids:
            errors.append(f"{path}.topic_id duplicates topic id '{topic_id}'")
        topic_ids.add(topic_id)
    _require_enum(topic, "candidate_status", VALID_CANDIDATE_STATUSES, path, errors)
    _require_enum(topic, "topic_type", VALID_TOPIC_TYPES, path, errors)
    for field in ("companies", "models", "regions", "uncertainty_notes", "safety_flags", "related_topic_ids"):
        _require_string_list(topic, field, path, errors)
    _validate_reference_list(topic, "source_observation_ids", observation_ids, path, errors, "source observation")
    if topic.get("candidate_status") == "quiet_day_note" and not topic.get("source_ids"):
        _require_string_list(topic, "source_ids", path, errors)
        _require_string_list(topic, "primary_source_ids", path, errors)
    else:
        _validate_reference_list(topic, "source_ids", valid_source_ids, path, errors, "source")
        _validate_reference_list(topic, "primary_source_ids", valid_source_ids, path, errors, "source")
    for field in ("material_update_score", "importance_score", "novelty_score", "source_quality_score"):
        _require_score(topic, field, path, errors)
    _require_enum(topic, "confidence", VALID_CONFIDENCE, path, errors)
    _require_enum(topic, "review_recommendation", VALID_REVIEW_RECOMMENDATIONS, path, errors)
    if not isinstance(topic.get("review_required"), bool):
        errors.append(f"{path}.review_required must be a boolean")
    _require_non_empty_string(topic, "dedup_key", path, errors)


def _validate_dedup_group(group: Any, index: int, topic_ids: set[str], errors: list[str]) -> None:
    path = f"$.dedup_groups[{index}]"
    if not isinstance(group, dict):
        errors.append(f"{path} must be an object")
        return
    _require_fields(group, ("dedup_key", "topic_ids", "canonical_topic_id", "reason"), path, errors)
    _require_non_empty_string(group, "dedup_key", path, errors)
    _validate_reference_list(group, "topic_ids", topic_ids, path, errors, "topic")
    canonical = _require_non_empty_string(group, "canonical_topic_id", path, errors)
    if canonical and canonical not in topic_ids:
        errors.append(f"{path}.canonical_topic_id references unknown topic id '{canonical}'")


def _validate_unresolved_item(item: Any, index: int, topic_ids: set[str], errors: list[str]) -> None:
    path = f"$.unresolved_items[{index}]"
    if not isinstance(item, dict):
        errors.append(f"{path} must be an object")
        return
    _require_fields(item, ("id", "topic_id", "reason", "review_action"), path, errors)
    _require_non_empty_string(item, "id", path, errors)
    topic_id = _require_non_empty_string(item, "topic_id", path, errors)
    if topic_id and topic_id not in topic_ids:
        errors.append(f"{path}.topic_id references unknown topic id '{topic_id}'")


def _safety_errors(data: Any) -> list[str]:
    errors = []
    errors.extend(find_secret_like_values(data))
    errors.extend(find_public_safety_issues(data))
    for path, value in _iter_string_values(data):
        lowered = value.lower()
        if PRIVATE_AI_MARKER in value:
            errors.append(f"{path} contains private AI source marker")
        if CHAT_MARKER in lowered or ENV_MARKER in lowered:
            errors.append(f"{path} contains unsafe configuration marker")
        if any(marker in lowered for marker in FORBIDDEN_EXPORT_MARKERS):
            errors.append(f"{path} contains unsupported export marker")
        if any(marker in lowered for marker in LEGACY_MARKERS):
            errors.append(f"{path} contains legacy builder reference")
    return errors


def _iter_string_values(value: Any, path: str = "$") -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    if isinstance(value, str):
        items.append((path, value))
    elif isinstance(value, dict):
        for key, child in value.items():
            items.extend(_iter_string_values(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            items.extend(_iter_string_values(child, f"{path}[{index}]"))
    return items


def _require_non_empty_string(obj: dict[str, Any], field: str, path: str, errors: list[str]) -> str | None:
    value = obj.get(field)
    if not isinstance(value, str) or not value:
        errors.append(f"{path}.{field} must be a non-empty string")
        return None
    return value


def _require_positive_int(obj: dict[str, Any], field: str, path: str, errors: list[str]) -> None:
    value = obj.get(field)
    if not isinstance(value, int) or value < 1:
        errors.append(f"{path}.{field} must be a positive integer")


def _require_score(obj: dict[str, Any], field: str, path: str, errors: list[str]) -> None:
    value = obj.get(field)
    if not isinstance(value, (int, float)) or not 0 <= value <= 5:
        errors.append(f"{path}.{field} must be a number from 0 to 5")


def _require_date(obj: dict[str, Any], field: str, path: str, errors: list[str]) -> None:
    value = obj.get(field)
    if not isinstance(value, str) or not DATE_ONLY.match(value):
        errors.append(f"{path}.{field} must be YYYY-MM-DD")


def _require_timestamp(obj: dict[str, Any], field: str, path: str, errors: list[str]) -> None:
    value = obj.get(field)
    if not isinstance(value, str) or not ISO_8601_WITH_TIMEZONE.match(value):
        errors.append(f"{path}.{field} must be ISO-8601 with timezone")


def _require_optional_timestamp(obj: dict[str, Any], field: str, path: str, errors: list[str]) -> None:
    value = obj.get(field)
    if value is not None and (not isinstance(value, str) or not ISO_8601_WITH_TIMEZONE.match(value)):
        errors.append(f"{path}.{field} must be ISO-8601 with timezone or null")


def _require_enum(obj: dict[str, Any], field: str, allowed: set[str], path: str, errors: list[str]) -> str | None:
    value = obj.get(field)
    if value not in allowed:
        errors.append(f"{path}.{field} must be one of: {', '.join(sorted(allowed))}")
        return None
    return value


def _require_string_list(obj: dict[str, Any], field: str, path: str, errors: list[str]) -> None:
    values = obj.get(field)
    if not isinstance(values, list):
        errors.append(f"{path}.{field} must be an array")
        return
    for index, value in enumerate(values):
        if not isinstance(value, str):
            errors.append(f"{path}.{field}[{index}] must be a string")


def _validate_reference_list(obj: dict[str, Any], field: str, valid_ids: set[str], path: str, errors: list[str], label: str) -> None:
    values = obj.get(field)
    if not isinstance(values, list):
        errors.append(f"{path}.{field} must be an array")
        return
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value:
            errors.append(f"{path}.{field}[{index}] must be a non-empty string")
            continue
        if value not in valid_ids:
            errors.append(f"{path}.{field}[{index}] references unknown {label} id '{value}'")


def _require_public_https_url(obj: dict[str, Any], field: str, path: str, errors: list[str]) -> None:
    value = obj.get(field)
    if not isinstance(value, str) or not value:
        errors.append(f"{path}.{field} must be a non-empty string")
        return
    if _url_has_private_location(value):
        errors.append(f"{path}.{field} must be public HTTPS and not local/private")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        errors.append(f"{path}.{field} must be public HTTPS")
