from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any


REPLAY_FIXTURE_SCHEMA_VERSION = "1.0.0"
REQUIRED_FIXTURE_FIELDS = (
    "fixture_schema_version",
    "source_id",
    "source_type",
    "title",
    "url",
    "observed_at",
    "published_at",
    "retrieved_at",
    "fetch_mode",
    "content_type",
    "reduced_metadata",
    "entities",
    "content_hash",
    "source_confidence",
    "safety_flags",
)
SOURCE_TYPES = {"official", "paper", "repository", "regulatory", "news", "social", "other"}
SOURCE_CONFIDENCE = {"high", "medium", "low"}
ISO_WITH_TIMEZONE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
SHA256_HEX = re.compile(r"^[a-f0-9]{64}$")
WINDOWS_PATH = re.compile(r"\b[A-Za-z]:\\")
PRIVATE_HOST = re.compile(r"^(?:localhost|127\.|0\.0\.0\.0|10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[0-1])\.)", re.IGNORECASE)
SECRET_PATTERNS = (
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b"),
    re.compile("secret" + "-like" + "-value" + "-for" + "-test"),
    re.compile(r"(?i)\b(?:OPENAI_API_KEY|TELEGRAM_BOT_TOKEN|BOT_TOKEN|api[_-]?key|token|secret)\s*[:=]\s*[^<\s]+"),
)
RAW_HTML_PATTERNS = (
    re.compile(r"(?is)<\s*!doctype\s+html"),
    re.compile(r"(?is)<\s*html\b"),
    re.compile(r"(?is)<\s*body\b"),
    re.compile(r"(?is)</\s*html\s*>"),
)
RAW_CONTENT_KEYS = {
    "raw_html",
    "html",
    "body",
    "article_body",
    "full_text",
    "full_article",
    "response_body",
    "page_source",
    "screenshot",
    "docx_export",
    "telegram_export",
}
PRIVATE_AI_MARKER = "AI" + "\u65e5" + "\u62a5"
CHAT_MARKER = "chat" + "_id"
MISTAKEN_PROMPT_MARKER = "github" + "-daily" + "-intelligence"
LEGACY_MARKERS = (
    "build" + "_report_",
    "send" + "-telegram" + "-report",
    "generate" + "_ai_word" + "_report",
)
EXPORT_MARKERS = (".docx", ".htm", "telegram_export", "telegram-export", "raw_migration", "raw-historical-export")


class FetchAdapterError(Exception):
    """Raised when a replay fetch fixture cannot be converted safely."""


@dataclass(frozen=True)
class ReplayFetchResult:
    fixture_path: Path
    observation: dict[str, Any]


def load_replay_fixture(path: str | Path) -> dict[str, Any]:
    fixture_path = Path(path)
    try:
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FetchAdapterError(f"replay fixture not found: {fixture_path}") from exc
    except json.JSONDecodeError as exc:
        raise FetchAdapterError(f"replay fixture is invalid JSON: {fixture_path}") from exc
    if not isinstance(data, dict):
        raise FetchAdapterError("replay fixture must be a JSON object")
    validate_replay_fixture(data)
    return data


def replay_fixture_to_observation(path: str | Path, *, source_id: str) -> ReplayFetchResult:
    fixture_path = Path(path)
    fixture = load_replay_fixture(fixture_path)
    if fixture["source_id"] != source_id:
        raise FetchAdapterError("source_id does not match replay fixture")
    observation = _build_observation(fixture)
    return ReplayFetchResult(fixture_path=fixture_path, observation=observation)


def render_observation_json(observation: dict[str, Any]) -> str:
    return json.dumps(observation, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def validate_replay_fixture(data: dict[str, Any]) -> None:
    errors: list[str] = []
    for field in REQUIRED_FIXTURE_FIELDS:
        if field not in data:
            errors.append(f"$.{field} is required")
    if errors:
        raise FetchAdapterError("; ".join(errors))

    _require_equal(data, "fixture_schema_version", REPLAY_FIXTURE_SCHEMA_VERSION, errors)
    _require_non_empty_string(data, "source_id", errors)
    _require_enum(data, "source_type", SOURCE_TYPES, errors)
    _require_non_empty_string(data, "title", errors)
    _require_public_https_url(data, "url", errors)
    _require_timestamp(data, "observed_at", errors)
    _require_optional_timestamp(data, "published_at", errors)
    _require_timestamp(data, "retrieved_at", errors)
    _require_equal(data, "fetch_mode", "replay_fixture", errors)
    _require_non_empty_string(data, "content_type", errors)
    _require_object(data, "reduced_metadata", errors)
    _require_object(data, "entities", errors)
    _require_sha256(data, "content_hash", errors)
    _require_enum(data, "source_confidence", SOURCE_CONFIDENCE, errors)
    _require_string_list(data, "safety_flags", errors)

    if data.get("content_type") == "text/html":
        errors.append("$.content_type must not be text/html in replay fixtures")
    if isinstance(data.get("reduced_metadata"), dict):
        _validate_reduced_metadata(data["reduced_metadata"], errors)
    if isinstance(data.get("entities"), dict):
        _validate_entities(data["entities"], errors)
    errors.extend(_safety_errors(data))

    if errors:
        raise FetchAdapterError("; ".join(errors))


def _build_observation(fixture: dict[str, Any]) -> dict[str, Any]:
    metadata = fixture["reduced_metadata"]
    summary = str(metadata.get("summary", ""))
    observation = {
        "adapter_mode": "replay_fixture",
        "content_hash": fixture["content_hash"],
        "content_type": fixture["content_type"],
        "entities": fixture["entities"],
        "fetch_mode": "replay_fixture",
        "live_fetching": False,
        "metadata_only": True,
        "observation_id": _observation_id(str(fixture["source_id"]), str(fixture["content_hash"])),
        "observed_at": fixture["observed_at"],
        "raw_signal_type": _raw_signal_type(fixture),
        "published_at": fixture.get("published_at"),
        "reduced_metadata": metadata,
        "retrieved_at": fixture["retrieved_at"],
        "review_required": True,
        "safety_flags": _merged_safety_flags(fixture.get("safety_flags", [])),
        "source_confidence": fixture["source_confidence"],
        "source_id": fixture["source_id"],
        "source_type": fixture["source_type"],
        "summary": summary,
        "title": fixture["title"],
        "url": fixture["url"],
    }
    return observation


def _observation_id(source_id: str, content_hash: str) -> str:
    return "replay-" + _slug(source_id) + "-" + content_hash[:12]


def _slug(value: str) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        elif chars and chars[-1] != "-":
            chars.append("-")
    return "".join(chars).strip("-")[:48] or "source"


def _merged_safety_flags(flags: Any) -> list[str]:
    values = [flag for flag in flags if isinstance(flag, str)]
    values.extend(["replay_fixture", "metadata_only", "manual_review_required", "no_live_fetch"])
    return sorted(set(values))


def _raw_signal_type(fixture: dict[str, Any]) -> str:
    metadata = fixture.get("reduced_metadata", {})
    if isinstance(metadata, dict):
        explicit = metadata.get("raw_signal_type")
        if isinstance(explicit, str) and re.fullmatch(r"[a-z0-9_]+", explicit):
            return explicit

    title = str(fixture.get("title", ""))
    summary = str(metadata.get("summary", "")) if isinstance(metadata, dict) else ""
    combined = f"{title} {summary}".lower()
    source_type = str(fixture.get("source_type", "")).lower()
    if "model card" in combined:
        return "model_card"
    if "security" in combined or "advisory" in combined:
        return "security_advisory"
    if "changelog" in combined:
        return "changelog"
    if "release notes" in combined:
        return "release_notes"
    if source_type == "repository":
        return "repository_release"
    if source_type == "paper":
        return "research_paper"
    if source_type == "regulatory":
        return "regulatory_metadata"
    if source_type == "news":
        return "news_metadata"
    return "official_release" if source_type == "official" else "metadata_snapshot"


def _validate_reduced_metadata(metadata: dict[str, Any], errors: list[str]) -> None:
    for key in metadata:
        if str(key).lower() in RAW_CONTENT_KEYS:
            errors.append(f"$.reduced_metadata.{key} is not allowed in replay fixtures")
    if not isinstance(metadata.get("summary"), str) or not metadata.get("summary"):
        errors.append("$.reduced_metadata.summary must be a non-empty string")
    if "title" in metadata and not isinstance(metadata.get("title"), str):
        errors.append("$.reduced_metadata.title must be a string when present")


def _validate_entities(entities: dict[str, Any], errors: list[str]) -> None:
    for field in ("companies", "models", "regions"):
        value = entities.get(field, [])
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            errors.append(f"$.entities.{field} must be an array of strings")


def _require_equal(data: dict[str, Any], field: str, expected: str, errors: list[str]) -> None:
    if data.get(field) != expected:
        errors.append(f"$.{field} must be {expected}")


def _require_non_empty_string(data: dict[str, Any], field: str, errors: list[str]) -> None:
    if not isinstance(data.get(field), str) or not data.get(field):
        errors.append(f"$.{field} must be a non-empty string")


def _require_object(data: dict[str, Any], field: str, errors: list[str]) -> None:
    if not isinstance(data.get(field), dict):
        errors.append(f"$.{field} must be an object")


def _require_enum(data: dict[str, Any], field: str, allowed: set[str], errors: list[str]) -> None:
    if data.get(field) not in allowed:
        errors.append(f"$.{field} must be one of: {', '.join(sorted(allowed))}")


def _require_string_list(data: dict[str, Any], field: str, errors: list[str]) -> None:
    value = data.get(field)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        errors.append(f"$.{field} must be an array of strings")


def _require_timestamp(data: dict[str, Any], field: str, errors: list[str]) -> None:
    value = data.get(field)
    if not isinstance(value, str) or not ISO_WITH_TIMEZONE.match(value):
        errors.append(f"$.{field} must be ISO-8601 with timezone")


def _require_optional_timestamp(data: dict[str, Any], field: str, errors: list[str]) -> None:
    value = data.get(field)
    if value is not None and (not isinstance(value, str) or not ISO_WITH_TIMEZONE.match(value)):
        errors.append(f"$.{field} must be ISO-8601 with timezone or null")


def _require_sha256(data: dict[str, Any], field: str, errors: list[str]) -> None:
    value = data.get(field)
    if not isinstance(value, str) or not SHA256_HEX.match(value):
        errors.append(f"$.{field} must be a lowercase sha256 hex string")


def _require_public_https_url(data: dict[str, Any], field: str, errors: list[str]) -> None:
    value = data.get(field)
    if not isinstance(value, str) or not value:
        errors.append(f"$.{field} must be a non-empty string")
        return
    if not _is_public_https_url(value):
        errors.append(f"$.{field} must be public HTTPS without credentials, query strings, or fragments")


def _is_public_https_url(value: str) -> bool:
    if WINDOWS_PATH.search(value) or any(char.isspace() for char in value) or "\\" in value:
        return False
    prefix = "https://"
    if not value.startswith(prefix):
        return False
    remainder = value[len(prefix) :]
    if not remainder or "?" in remainder or "#" in remainder:
        return False
    authority = remainder.split("/", 1)[0]
    if not authority or "@" in authority:
        return False
    host = authority.split(":", 1)[0].lower()
    if not host or "." not in host:
        return False
    return PRIVATE_HOST.search(host) is None


def _safety_errors(value: Any) -> list[str]:
    errors: list[str] = []
    for path, text in _iter_string_values(value):
        lowered = text.lower()
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            errors.append(f"{path} contains secret-like value")
        if WINDOWS_PATH.search(text) or "/users/" in lowered:
            errors.append(f"{path} contains private path")
        if PRIVATE_AI_MARKER in text:
            errors.append(f"{path} contains private source marker")
        if CHAT_MARKER in lowered:
            errors.append(f"{path} contains unsafe configuration marker")
        if MISTAKEN_PROMPT_MARKER in lowered:
            errors.append(f"{path} contains mistaken prompt marker")
        if any(marker in lowered for marker in LEGACY_MARKERS):
            errors.append(f"{path} contains legacy builder marker")
        if any(marker in lowered for marker in EXPORT_MARKERS):
            errors.append(f"{path} contains unsupported export marker")
        if any(pattern.search(text) for pattern in RAW_HTML_PATTERNS):
            errors.append(f"{path} contains raw HTML")
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


def deterministic_fixture_hash(payload: dict[str, Any]) -> str:
    reduced = {
        "source_id": payload.get("source_id"),
        "title": payload.get("title"),
        "url": payload.get("url"),
        "observed_at": payload.get("observed_at"),
        "published_at": payload.get("published_at"),
        "retrieved_at": payload.get("retrieved_at"),
        "reduced_metadata": payload.get("reduced_metadata"),
        "entities": payload.get("entities"),
    }
    encoded = json.dumps(reduced, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
