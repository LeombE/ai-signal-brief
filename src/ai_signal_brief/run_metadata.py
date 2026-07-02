from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .validation import (
    find_public_safety_issues,
    find_secret_like_values,
    validate_report_path,
    validate_run,
)


ARTIFACT_KIND = re.compile(r"^[a-z][a-z0-9_]*$")
WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
SCHEMA_VERSION = "1.0.0"
DEFAULT_TIMEZONE = "Asia/Kuala_Lumpur"
TIMEZONE_FALLBACKS = {
    DEFAULT_TIMEZONE: timezone(timedelta(hours=8)),
}


class RunMetadataError(RuntimeError):
    """Raised when offline run metadata cannot be generated safely."""


def load_valid_report(path: str | Path) -> dict[str, Any]:
    report_path = Path(path)
    validation = validate_report_path(report_path)
    if not validation.ok:
        raise RunMetadataError("invalid report JSON: " + "; ".join(validation.errors))

    with report_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise RunMetadataError("report JSON must be an object")
    return data


def create_run_record(
    report_path: str | Path,
    artifact_args: list[str] | None = None,
    *,
    started_at: str | None = None,
    ended_at: str | None = None,
    timezone_name: str = DEFAULT_TIMEZONE,
) -> dict[str, Any]:
    report = load_valid_report(report_path)
    started_at_value, ended_at_value = _resolve_timestamps(started_at, ended_at, timezone_name)

    artifacts = [_parse_artifact_arg(value) for value in artifact_args or []]
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": _run_id_from_started_at(started_at_value),
        "started_at": started_at_value,
        "ended_at": ended_at_value,
        "timezone": timezone_name,
        "status": "success",
        "mode": "manual",
        "environment": "local",
        "report_id": str(report.get("report_id", "")),
        "report_date": str(report.get("report_date", "")),
        "artifacts": artifacts,
        "delivery": {
            "telegram": {
                "enabled": False,
                "status": "skipped",
            }
        },
        "warnings": [],
        "errors": [],
    }

    errors = validate_run(record)
    errors.extend(find_secret_like_values(record))
    errors.extend(find_public_safety_issues(record))
    if errors:
        raise RunMetadataError("generated run metadata failed validation: " + "; ".join(errors))
    return record


def write_run_record(record: dict[str, Any], output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    safety_errors = find_secret_like_values(content)
    if safety_errors:
        raise RunMetadataError("refusing to write run metadata with secret-like values")
    output.write_text(content, encoding="utf-8")
    return output


def _resolve_timestamps(
    started_at: str | None,
    ended_at: str | None,
    timezone_name: str,
) -> tuple[str, str]:
    if started_at and ended_at:
        return started_at, ended_at

    timezone_info = _load_timezone(timezone_name)
    now = datetime.now(timezone_info).replace(microsecond=0)
    started_at_value = started_at or now.isoformat()
    ended_at_value = ended_at or now.isoformat()
    return started_at_value, ended_at_value


def _load_timezone(timezone_name: str):
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        fallback = TIMEZONE_FALLBACKS.get(timezone_name)
        if fallback is not None:
            return fallback
        raise RunMetadataError(f"unknown timezone: {timezone_name}") from exc


def _run_id_from_started_at(started_at: str) -> str:
    return started_at.replace(":", "-")


def _parse_artifact_arg(value: str) -> dict[str, str]:
    if "=" not in value:
        raise RunMetadataError("artifact must use kind=relative/path format")
    kind, raw_path = value.split("=", 1)
    kind = kind.strip()
    raw_path = raw_path.strip()

    if not ARTIFACT_KIND.match(kind):
        raise RunMetadataError(f"invalid artifact kind: {kind}")
    safe_path = _normalize_safe_relative_path(raw_path)

    candidate = {"kind": kind, "path": safe_path}
    safety_errors = find_secret_like_values(candidate)
    safety_errors.extend(find_public_safety_issues(candidate))
    if safety_errors:
        raise RunMetadataError("artifact contains unsafe value: " + "; ".join(safety_errors))
    return candidate


def _normalize_safe_relative_path(raw_path: str) -> str:
    if not raw_path:
        raise RunMetadataError("artifact path must be non-empty")
    if raw_path.startswith(("/", "\\", "~")) or WINDOWS_DRIVE_PATH.match(raw_path):
        raise RunMetadataError("artifact path must be relative")
    if "://" in raw_path:
        raise RunMetadataError("artifact path must not be a URL")

    normalized = raw_path.replace("\\", "/")
    path = PurePosixPath(normalized)
    if any(part in {"..", ""} for part in path.parts):
        raise RunMetadataError("artifact path must not contain empty or parent-directory segments")
    return path.as_posix()