from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

from .quality_gate import (
    _has_marker,
    _has_secret_or_private_values,
    _legacy_builder_markers,
    _mistaken_prompt_markers,
    run_quality_gate,
)
from .validation import find_secret_like_values, validate_report_path, validate_run_path


ARCHIVE_SCHEMA_VERSION = "1.0.0"
WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")


class ArchiveError(RuntimeError):
    """Raised when an offline archive cannot be built safely."""


@dataclass(frozen=True)
class ArchiveBuildResult:
    archive_root: Path
    report_path: Path
    run_path: Path
    markdown_path: Path
    index_path: Path


def build_archive(
    report_path: str | Path,
    run_path: str | Path,
    sources_path: str | Path,
    output_path: str | Path,
    *,
    repo_root: str | Path | None = None,
) -> ArchiveBuildResult:
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    archive_root = _resolve_safe_output_path(output_path, root)

    gate_result = run_quality_gate(report_path, run_path, sources_path, repo_root=root)
    if not gate_result.ok:
        raise ArchiveError("quality gate failed: " + ", ".join(gate_result.failed_checks))

    report = _load_valid_json(report_path, validate_report_path, "report")
    run = _load_valid_json(run_path, validate_run_path, "run")
    _reject_unsafe_values(report, run, {"archive_root": _relative_to_repo(archive_root, root)})

    report_date = _required_string(report, "report_date")
    report_id = _required_string(report, "report_id")
    year, month, day = _date_parts(report_date)
    report_dir = archive_root / year / month / day
    report_output = report_dir / "report.json"
    run_output = report_dir / "run.json"
    markdown_output = report_dir / "index.md"
    index_output = archive_root / "index.json"

    existing_index = _load_archive_index(index_output)
    if _index_has_report_id(existing_index, report_id):
        raise ArchiveError("duplicate report_id rejected")
    if report_output.exists() or run_output.exists() or markdown_output.exists():
        raise ArchiveError("archive date entry already exists")

    entry = _archive_entry(report, archive_root, report_output, run_output, markdown_output)
    updated_index = _updated_index(existing_index, entry)
    _reject_unsafe_values(updated_index, entry)

    report_dir.mkdir(parents=True, exist_ok=True)
    _write_json(report_output, report)
    _write_json(run_output, run)
    markdown_output.write_text(_render_archive_markdown(report), encoding="utf-8")
    _write_json(index_output, updated_index)

    return ArchiveBuildResult(
        archive_root=archive_root,
        report_path=report_output,
        run_path=run_output,
        markdown_path=markdown_output,
        index_path=index_output,
    )


def _resolve_safe_output_path(output_path: str | Path, repo_root: Path) -> Path:
    raw_output = str(output_path)
    if not raw_output:
        raise ArchiveError("output path is required")
    if "://" in raw_output or raw_output.startswith(("~", "\\")):
        raise ArchiveError("unsafe output path rejected")
    _reject_unsafe_output_path_text(raw_output)

    root = repo_root.resolve()
    candidate = Path(output_path)
    if not candidate.is_absolute():
        normalized = raw_output.replace("\\", "/")
        pure_path = PurePosixPath(normalized)
        if any(part in {"", ".."} for part in pure_path.parts):
            raise ArchiveError("unsafe output path rejected")
        candidate = root / Path(*pure_path.parts)
    elif WINDOWS_DRIVE_PATH.match(raw_output) is None and raw_output.startswith("/"):
        raise ArchiveError("unsafe output path rejected")

    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ArchiveError("output path must stay inside repository") from exc
    return resolved

def _reject_unsafe_output_path_text(raw_output: str) -> None:
    value = {"output_path": raw_output}
    if find_secret_like_values(value):
        raise ArchiveError("unsafe output path rejected")
    lowered = raw_output.lower()
    if "chat_id" in lowered or ".env" in lowered or "ai日报" in lowered:
        raise ArchiveError("unsafe output path rejected")
    if _has_marker(value, _mistaken_prompt_markers()) or _has_marker(value, _legacy_builder_markers()):
        raise ArchiveError("unsafe output path rejected")

def _load_valid_json(path: str | Path, validator, label: str) -> dict[str, Any]:
    validation = validator(path)
    if not validation.ok:
        raise ArchiveError(f"invalid {label} JSON")
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ArchiveError(f"{label} JSON must be an object")
    return data


def _load_archive_index(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": ARCHIVE_SCHEMA_VERSION, "reports": []}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("reports"), list):
        raise ArchiveError("archive index is invalid")
    return data


def _index_has_report_id(index: dict[str, Any], report_id: str) -> bool:
    reports = index.get("reports", [])
    return any(isinstance(entry, dict) and entry.get("report_id") == report_id for entry in reports)


def _archive_entry(
    report: dict[str, Any],
    archive_root: Path,
    report_output: Path,
    run_output: Path,
    markdown_output: Path,
) -> dict[str, Any]:
    return {
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "report_id": _required_string(report, "report_id"),
        "report_date": _required_string(report, "report_date"),
        "generated_at": _required_string(report, "generated_at"),
        "title": _required_string(report, "title"),
        "paths": {
            "report": _relative_to_archive(report_output, archive_root),
            "run": _relative_to_archive(run_output, archive_root),
            "markdown": _relative_to_archive(markdown_output, archive_root),
        },
    }


def _updated_index(existing_index: dict[str, Any], new_entry: dict[str, Any]) -> dict[str, Any]:
    entries = [entry for entry in existing_index.get("reports", []) if isinstance(entry, dict)]
    entries.append(new_entry)
    entries.sort(key=lambda entry: (str(entry.get("report_date", "")), str(entry.get("generated_at", ""))), reverse=True)
    return {
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "reports": entries,
    }


def _render_archive_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {_required_string(report, 'title')}",
            "",
            f"- Report ID: {_required_string(report, 'report_id')}",
            f"- Report date: {_required_string(report, 'report_date')}",
            f"- Generated at: {_required_string(report, 'generated_at')}",
            "- Canonical report: report.json",
            "- Run metadata: run.json",
            "",
        ]
    )


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _required_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ArchiveError(f"{key} is required")
    return value


def _date_parts(report_date: str) -> tuple[str, str, str]:
    parts = report_date.split("-")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise ArchiveError("report_date must be YYYY-MM-DD")
    return parts[0], parts[1], parts[2]


def _relative_to_archive(path: Path, archive_root: Path) -> str:
    return path.relative_to(archive_root).as_posix()


def _relative_to_repo(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _reject_unsafe_values(*values: dict[str, Any]) -> None:
    for value in values:
        if _has_secret_or_private_values(value):
            raise ArchiveError("unsafe value rejected")
        if _has_marker(value, _mistaken_prompt_markers()):
            raise ArchiveError("mistaken prompt reference rejected")
        if _has_marker(value, _legacy_builder_markers()):
            raise ArchiveError("legacy builder reference rejected")
