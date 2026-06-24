from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Any


ISO_8601_WITH_TIMEZONE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")

SECRET_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("telegram token", re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b")),
    ("openai api key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    (
        "secret assignment",
        re.compile(
            r"(?i)\b(?:OPENAI_API_KEY|TELEGRAM_BOT_TOKEN|BOT_TOKEN|CHAT_ID|api[_-]?key|token|secret|chat[_-]?id)\s*[:=]\s*[^<\s]+"
        ),
    ),
    ("test secret marker", re.compile(r"secret-like-value-for-test")),
)

REPORT_REQUIRED_FIELDS = (
    "schema_version",
    "report_id",
    "report_date",
    "generated_at",
    "timezone",
    "language",
    "title",
    "summary",
    "stories",
    "sources",
    "assets",
    "provenance",
)
SOURCE_REQUIRED_FIELDS = (
    "id",
    "title",
    "publisher",
    "url",
    "source_type",
    "published_at",
    "retrieved_at",
)
STORY_REQUIRED_FIELDS = (
    "id",
    "rank",
    "title",
    "status",
    "importance",
    "companies",
    "models",
    "regions",
    "claims",
    "source_ids",
    "analysis",
)
CLAIM_REQUIRED_FIELDS = (
    "id",
    "text",
    "source_ids",
    "verification_status",
    "confidence",
)
RUN_REQUIRED_FIELDS = (
    "schema_version",
    "run_id",
    "started_at",
    "timezone",
    "status",
    "mode",
    "environment",
    "artifacts",
    "delivery",
    "warnings",
    "errors",
)

STORY_STATUSES = {"new", "update", "follow_up", "correction"}
SOURCE_TYPES = {"official", "paper", "repository", "regulatory", "news", "social", "other"}
CLAIM_VERIFICATION_STATUSES = {"supported", "partially_supported", "unverified"}
CLAIM_CONFIDENCE = {"high", "medium", "low"}
RUN_STATUSES = {"success", "partial", "failed", "dry_run"}
RUN_MODES = {"manual", "scheduled", "test"}
RUN_ENVIRONMENTS = {"local", "github_actions", "other"}


@dataclass(frozen=True)
class ValidationResult:
    path: Path
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_report_path(path: str | Path) -> ValidationResult:
    report_path = Path(path)
    data, errors = _load_json(report_path)
    if errors:
        return ValidationResult(report_path, tuple(errors))
    errors.extend(validate_report(data))
    errors.extend(find_secret_like_values(data))
    return ValidationResult(report_path, tuple(errors))


def validate_run_path(path: str | Path) -> ValidationResult:
    run_path = Path(path)
    data, errors = _load_json(run_path)
    if errors:
        return ValidationResult(run_path, tuple(errors))
    errors.extend(validate_run(data))
    errors.extend(find_secret_like_values(data))
    return ValidationResult(run_path, tuple(errors))


def validate_report(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["$ must be an object"]

    _require_fields(data, REPORT_REQUIRED_FIELDS, "$", errors)
    _require_date(data, "report_date", "$", errors)
    _require_timestamp(data, "generated_at", "$", errors)

    if data.get("language") != "en":
        errors.append("$.language must be 'en'")

    sources = data.get("sources")
    source_ids: set[str] = set()
    if not isinstance(sources, list):
        errors.append("$.sources must be an array")
    else:
        for index, source in enumerate(sources):
            source_path = f"$.sources[{index}]"
            if not isinstance(source, dict):
                errors.append(f"{source_path} must be an object")
                continue
            _require_fields(source, SOURCE_REQUIRED_FIELDS, source_path, errors)
            source_id = _string_id(source, "id", source_path, errors)
            if source_id:
                if source_id in source_ids:
                    errors.append(f"{source_path}.id duplicates source id '{source_id}'")
                source_ids.add(source_id)
            _require_enum(source, "source_type", SOURCE_TYPES, source_path, errors)
            _require_timestamp(source, "published_at", source_path, errors)
            _require_timestamp(source, "retrieved_at", source_path, errors)

    stories = data.get("stories")
    story_ids: set[str] = set()
    claim_ids: set[str] = set()
    if not isinstance(stories, list):
        errors.append("$.stories must be an array")
    else:
        for index, story in enumerate(stories):
            _validate_story(story, index, source_ids, story_ids, claim_ids, errors)

    return errors


def validate_run(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["$ must be an object"]

    _require_fields(data, RUN_REQUIRED_FIELDS, "$", errors)
    _require_timestamp(data, "started_at", "$", errors)

    ended_at = data.get("ended_at")
    if ended_at is not None:
        _require_timestamp(data, "ended_at", "$", errors)

    _require_enum(data, "status", RUN_STATUSES, "$", errors)
    _require_enum(data, "mode", RUN_MODES, "$", errors)
    _require_enum(data, "environment", RUN_ENVIRONMENTS, "$", errors)

    for field_name in ("artifacts", "warnings", "errors"):
        if field_name in data and not isinstance(data[field_name], list):
            errors.append(f"$.{field_name} must be an array")

    if "delivery" in data and not isinstance(data["delivery"], dict):
        errors.append("$.delivery must be an object")

    artifacts = data.get("artifacts")
    if isinstance(artifacts, list):
        for index, artifact in enumerate(artifacts):
            artifact_path = f"$.artifacts[{index}]"
            if not isinstance(artifact, dict):
                errors.append(f"{artifact_path} must be an object")
                continue
            _require_fields(artifact, ("kind", "path"), artifact_path, errors)

    return errors


def find_secret_like_values(data: Any) -> list[str]:
    errors: list[str] = []
    for path, value in _iter_string_values(data):
        for label, pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(value):
                errors.append(f"{path} contains secret-like value: {label}")
    return errors


def _validate_story(
    story: Any,
    index: int,
    source_ids: set[str],
    story_ids: set[str],
    claim_ids: set[str],
    errors: list[str],
) -> None:
    story_path = f"$.stories[{index}]"
    if not isinstance(story, dict):
        errors.append(f"{story_path} must be an object")
        return

    _require_fields(story, STORY_REQUIRED_FIELDS, story_path, errors)
    story_id = _string_id(story, "id", story_path, errors)
    if story_id:
        if story_id in story_ids:
            errors.append(f"{story_path}.id duplicates story id '{story_id}'")
        story_ids.add(story_id)

    _require_enum(story, "status", STORY_STATUSES, story_path, errors)
    _validate_importance(story.get("importance"), story_path, errors)
    _validate_string_list_references(story, "source_ids", source_ids, story_path, errors)

    claims = story.get("claims")
    if not isinstance(claims, list):
        errors.append(f"{story_path}.claims must be an array")
        return

    for claim_index, claim in enumerate(claims):
        _validate_claim(claim, claim_index, story_path, source_ids, claim_ids, errors)


def _validate_claim(
    claim: Any,
    index: int,
    story_path: str,
    source_ids: set[str],
    claim_ids: set[str],
    errors: list[str],
) -> None:
    claim_path = f"{story_path}.claims[{index}]"
    if not isinstance(claim, dict):
        errors.append(f"{claim_path} must be an object")
        return

    _require_fields(claim, CLAIM_REQUIRED_FIELDS, claim_path, errors)
    claim_id = _string_id(claim, "id", claim_path, errors)
    if claim_id:
        if claim_id in claim_ids:
            errors.append(f"{claim_path}.id duplicates claim id '{claim_id}'")
        claim_ids.add(claim_id)

    _require_enum(claim, "verification_status", CLAIM_VERIFICATION_STATUSES, claim_path, errors)
    _require_enum(claim, "confidence", CLAIM_CONFIDENCE, claim_path, errors)
    _validate_string_list_references(claim, "source_ids", source_ids, claim_path, errors)


def _validate_importance(value: Any, path: str, errors: list[str]) -> None:
    importance_path = f"{path}.importance"
    if not isinstance(value, dict):
        errors.append(f"{importance_path} must be an object")
        return
    _require_fields(value, ("score", "rationale"), importance_path, errors)
    score = value.get("score")
    if not isinstance(score, int) or not 1 <= score <= 5:
        errors.append(f"{importance_path}.score must be an integer from 1 to 5")


def _validate_string_list_references(
    obj: dict[str, Any],
    field_name: str,
    valid_ids: set[str],
    path: str,
    errors: list[str],
) -> None:
    values = obj.get(field_name)
    field_path = f"{path}.{field_name}"
    if not isinstance(values, list):
        errors.append(f"{field_path} must be an array")
        return
    for index, value in enumerate(values):
        value_path = f"{field_path}[{index}]"
        if not isinstance(value, str) or not value:
            errors.append(f"{value_path} must be a non-empty string")
            continue
        if value not in valid_ids:
            errors.append(f"{value_path} references unknown source id '{value}'")


def _load_json(path: Path) -> tuple[Any, list[str]]:
    if not path.exists():
        return None, [f"{path} does not exist"]
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle), []
    except json.JSONDecodeError as exc:
        return None, [f"{path} is not valid JSON: {exc}"]


def _require_fields(obj: dict[str, Any], required: tuple[str, ...], path: str, errors: list[str]) -> None:
    for field_name in required:
        if field_name not in obj:
            errors.append(f"{path}.{field_name} is required")


def _string_id(obj: dict[str, Any], field_name: str, path: str, errors: list[str]) -> str | None:
    value = obj.get(field_name)
    if not isinstance(value, str) or not value:
        errors.append(f"{path}.{field_name} must be a non-empty string")
        return None
    return value


def _require_date(obj: dict[str, Any], field_name: str, path: str, errors: list[str]) -> None:
    value = obj.get(field_name)
    if not isinstance(value, str) or not DATE_ONLY.match(value):
        errors.append(f"{path}.{field_name} must be YYYY-MM-DD")


def _require_timestamp(obj: dict[str, Any], field_name: str, path: str, errors: list[str]) -> None:
    value = obj.get(field_name)
    if not isinstance(value, str) or not ISO_8601_WITH_TIMEZONE.match(value):
        errors.append(f"{path}.{field_name} must be ISO-8601 with timezone")


def _require_enum(
    obj: dict[str, Any],
    field_name: str,
    allowed: set[str],
    path: str,
    errors: list[str],
) -> None:
    value = obj.get(field_name)
    if value not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        errors.append(f"{path}.{field_name} must be one of: {allowed_values}")


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