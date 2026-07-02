from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

from .validation import (
    find_public_safety_issues,
    find_secret_like_values,
    validate_report_path,
    validate_run_path,
    validate_sources_path,
)


WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
LOCAL_PATH_FRAGMENT = re.compile(r"[A-Za-z]:[\\/]|(?:^|[\\/])Users[\\/]")


@dataclass(frozen=True)
class QualityGateResult:
    failed_checks: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.failed_checks


def run_quality_gate(
    report_path: str | Path,
    run_path: str | Path,
    sources_path: str | Path,
    *,
    repo_root: str | Path | None = None,
) -> QualityGateResult:
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    failed: set[str] = set()

    report_validation = validate_report_path(report_path)
    run_validation = validate_run_path(run_path)
    sources_validation = validate_sources_path(sources_path)

    if not report_validation.ok:
        failed.add("report_validation")
    if not run_validation.ok:
        failed.add("run_validation")
    if not sources_validation.ok:
        failed.add("sources_validation")

    report = _load_json_object(report_path, failed, "report_load")
    run = _load_json_object(run_path, failed, "run_load")
    sources = _load_json_object(sources_path, failed, "sources_load")

    if report and run and not _report_run_identity_matches(report, run):
        failed.add("report_run_identity")

    if report and not _report_source_references_are_valid(report):
        failed.add("report_source_references")

    if report and sources and not _report_source_types_are_allowed(report, sources):
        failed.add("source_type_compatibility")

    if run and not _artifact_paths_are_safe(run, root):
        failed.add("artifact_paths")

    if _has_secret_or_private_values(report, run, sources):
        failed.add("unsafe_values")

    if _has_marker(report, run, sources, _mistaken_prompt_markers()):
        failed.add("mistaken_prompt_references")

    if _has_marker(report, run, sources, _legacy_builder_markers()):
        failed.add("legacy_builder_references")

    return QualityGateResult(tuple(sorted(failed)))


def _load_json_object(path: str | Path, failed: set[str], check_name: str) -> dict[str, Any] | None:
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        failed.add(check_name)
        return None
    if not isinstance(data, dict):
        failed.add(check_name)
        return None
    return data


def _report_run_identity_matches(report: dict[str, Any], run: dict[str, Any]) -> bool:
    run_report_id = run.get("report_id")
    run_report_date = run.get("report_date")
    if run_report_id is not None and run_report_id != report.get("report_id"):
        return False
    if run_report_date is not None and run_report_date != report.get("report_date"):
        return False
    return True


def _report_source_references_are_valid(report: dict[str, Any]) -> bool:
    sources = report.get("sources")
    if not isinstance(sources, list):
        return False
    valid_source_ids = {source.get("id") for source in sources if isinstance(source, dict) and isinstance(source.get("id"), str)}
    stories = report.get("stories")
    if not isinstance(stories, list):
        return False

    for story in stories:
        if not isinstance(story, dict):
            return False
        if not _ids_exist(story.get("source_ids"), valid_source_ids):
            return False
        claims = story.get("claims")
        if not isinstance(claims, list):
            return False
        for claim in claims:
            if not isinstance(claim, dict) or not _ids_exist(claim.get("source_ids"), valid_source_ids):
                return False
    return True


def _ids_exist(values: Any, valid_ids: set[str]) -> bool:
    return isinstance(values, list) and all(isinstance(value, str) and value in valid_ids for value in values)


def _report_source_types_are_allowed(report: dict[str, Any], sources_registry: dict[str, Any]) -> bool:
    allowed_values = sources_registry.get("allowed_source_types")
    if not isinstance(allowed_values, list):
        return False
    allowed_types = {value for value in allowed_values if isinstance(value, str)}
    report_sources = report.get("sources")
    if not isinstance(report_sources, list):
        return False
    for source in report_sources:
        if not isinstance(source, dict) or source.get("source_type") not in allowed_types:
            return False
    return True


def _artifact_paths_are_safe(run: dict[str, Any], repo_root: Path) -> bool:
    artifacts = run.get("artifacts")
    if not isinstance(artifacts, list):
        return False
    root = repo_root.resolve()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            return False
        path_value = artifact.get("path")
        if not isinstance(path_value, str) or not _is_safe_relative_artifact_path(path_value, root):
            return False
    return True


def _is_safe_relative_artifact_path(path_value: str, repo_root: Path) -> bool:
    if not path_value:
        return False
    if path_value.startswith(("/", "\\", "~")) or WINDOWS_DRIVE_PATH.match(path_value):
        return False
    if "://" in path_value:
        return False

    normalized = path_value.replace("\\", "/")
    pure_path = PurePosixPath(normalized)
    if any(part in {"", ".."} for part in pure_path.parts):
        return False

    resolved = (repo_root / Path(*pure_path.parts)).resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError:
        return False
    return True


def _has_secret_or_private_values(*values: dict[str, Any] | None) -> bool:
    for value in values:
        if value is None:
            continue
        if find_secret_like_values(value) or find_public_safety_issues(value):
            return True
        for _, text in _iter_string_values(value):
            lowered = text.lower()
            if ("chat" + "_id") in lowered or ".env" in lowered or ("://" not in text and LOCAL_PATH_FRAGMENT.search(text)):
                return True
    return False


def _has_marker(*values_and_markers: Any) -> bool:
    *values, markers = values_and_markers
    lowered_markers = [marker.lower() for marker in markers]
    for value in values:
        if value is None:
            continue
        for _, text in _iter_string_values(value):
            lowered_text = text.lower()
            if any(marker in lowered_text for marker in lowered_markers):
                return True
    return False


def _mistaken_prompt_markers() -> tuple[str, ...]:
    project = "github" + "-daily" + "-intelligence"
    return (
        project,
        "00_MASTER" + "_PROMPT.md",
        "C:" + "\\Projects\\" + project,
        "feat/public" + "-" + project,
    )


def _legacy_builder_markers() -> tuple[str, ...]:
    return (
        "build" + "_report_",
        "send" + "-telegram" + "-report",
        "build" + "_ai_daily" + "_docx",
        "generate" + "_ai_word" + "_report",
        "render" + "-md" + "-to" + "-html",
    )


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