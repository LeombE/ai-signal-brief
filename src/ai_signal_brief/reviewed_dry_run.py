from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import json
import re
from typing import Any

from .archive import ArchiveError, ArchiveBuildResult, build_archive
from .public_readiness import PublicReadinessResult, audit_public_readiness
from .quality_gate import QualityGateResult, run_quality_gate
from .site import SiteBuildError, SiteBuildResult, build_site
from .validation import (
    DATE_ONLY,
    find_public_safety_issues,
    find_secret_like_values,
    validate_report_path,
    validate_run_path,
    validate_sources_path,
)


WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
CJK_TEXT = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


class ReviewedDryRunError(RuntimeError):
    """Raised when a reviewed report dry-run cannot complete safely."""


@dataclass(frozen=True)
class ReviewedDryRunResult:
    report_path: Path
    run_path: Path
    review_path: Path
    sources_path: Path
    archive_result: ArchiveBuildResult
    site_result: SiteBuildResult | None
    quality_gate_result: QualityGateResult
    public_readiness_result: PublicReadinessResult


@dataclass(frozen=True)
class ReviewedDryRunPaths:
    report_path: Path
    run_path: Path
    review_path: Path
    sources_path: Path
    archive_out: Path
    site_out: Path


def dry_run_reviewed_report(
    *,
    date: str,
    report_path: str | Path | None = None,
    run_path: str | Path | None = None,
    sources_path: str | Path | None = None,
    archive_out: str | Path | None = None,
    site_out: str | Path | None = None,
    strict: bool = False,
    no_site: bool = False,
    repo_root: str | Path | None = None,
) -> ReviewedDryRunResult:
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    root = root.resolve()
    paths = resolve_reviewed_dry_run_paths(
        date=date,
        report_path=report_path,
        run_path=run_path,
        sources_path=sources_path,
        archive_out=archive_out,
        site_out=site_out,
        repo_root=root,
    )

    _ensure_existing_file(paths.report_path, "report.json")
    _ensure_existing_file(paths.run_path, "run.json")
    _ensure_existing_file(paths.review_path, "review.md")
    _ensure_existing_file(paths.sources_path, "source registry")

    report = _load_json_object(paths.report_path, "report.json")
    run = _load_json_object(paths.run_path, "run.json")
    sources = _load_json_object(paths.sources_path, "source registry")
    review_text = paths.review_path.read_text(encoding="utf-8")

    _reject_unsafe_values(
        {"report_path": _relative_or_text(paths.report_path, root)},
        {"run_path": _relative_or_text(paths.run_path, root)},
        {"review_path": _relative_or_text(paths.review_path, root)},
        {"sources_path": _relative_or_text(paths.sources_path, root)},
        {"review": review_text},
        report,
        run,
        sources,
    )
    _require_english_canonical_report(report)
    _validate_review_notes(review_text, strict=strict)

    report_validation = validate_report_path(paths.report_path)
    if not report_validation.ok:
        raise ReviewedDryRunError("invalid report JSON: " + "; ".join(report_validation.errors))

    run_validation = validate_run_path(paths.run_path)
    if not run_validation.ok:
        raise ReviewedDryRunError("invalid run JSON: " + "; ".join(run_validation.errors))

    sources_validation = validate_sources_path(paths.sources_path)
    if not sources_validation.ok:
        raise ReviewedDryRunError("invalid sources JSON: " + "; ".join(sources_validation.errors))

    quality_gate_result = run_quality_gate(paths.report_path, paths.run_path, paths.sources_path, repo_root=root)
    if not quality_gate_result.ok:
        raise ReviewedDryRunError("quality gate failed: " + ", ".join(quality_gate_result.failed_checks))

    archive_out_arg = _relative_repo_path(paths.archive_out, root)
    site_out_arg = _relative_repo_path(paths.site_out, root)
    archive_result = build_archive(paths.report_path, paths.run_path, paths.sources_path, archive_out_arg, repo_root=root)
    site_result = None
    if not no_site:
        site_result = build_site(archive_out_arg, site_out_arg, repo_root=root)

    public_readiness_result = audit_public_readiness(root)
    if not public_readiness_result.ok:
        failed = ", ".join(f"{item.check_name}:{item.path}" for item in public_readiness_result.findings)
        raise ReviewedDryRunError("public readiness failed: " + failed)

    return ReviewedDryRunResult(
        report_path=paths.report_path,
        run_path=paths.run_path,
        review_path=paths.review_path,
        sources_path=paths.sources_path,
        archive_result=archive_result,
        site_result=site_result,
        quality_gate_result=quality_gate_result,
        public_readiness_result=public_readiness_result,
    )


def resolve_reviewed_dry_run_paths(
    *,
    date: str,
    report_path: str | Path | None,
    run_path: str | Path | None,
    sources_path: str | Path | None,
    archive_out: str | Path | None,
    site_out: str | Path | None,
    repo_root: Path,
) -> ReviewedDryRunPaths:
    if not isinstance(date, str) or not DATE_ONLY.match(date):
        raise ReviewedDryRunError("--date must be YYYY-MM-DD")
    year, month, day = date.split("-")
    default_reviewed_dir = repo_root / "reports-reviewed" / year / month / day

    resolved_report = _resolve_input_path(report_path, default_reviewed_dir / "report.json", repo_root, "report path")
    resolved_run = _resolve_input_path(run_path, default_reviewed_dir / "run.json", repo_root, "run path")
    if report_path is not None:
        resolved_review = resolved_report.parent / "review.md"
        _ensure_inside_repo(resolved_review, repo_root, "review path")
    else:
        resolved_review = default_reviewed_dir / "review.md"
    resolved_sources = _resolve_input_path(sources_path, repo_root / "config" / "sources.example.json", repo_root, "sources path")

    default_archive_out = repo_root / "outputs" / "reviewed-dry-run" / year / month / day
    default_site_out = repo_root / "outputs" / "reviewed-site-dry-run" / year / month / day
    resolved_archive_out = _resolve_output_path(archive_out, default_archive_out, repo_root, "archive output path")
    resolved_site_out = _resolve_output_path(site_out, default_site_out, repo_root, "site output path")

    return ReviewedDryRunPaths(
        report_path=resolved_report,
        run_path=resolved_run,
        review_path=resolved_review,
        sources_path=resolved_sources,
        archive_out=resolved_archive_out,
        site_out=resolved_site_out,
    )


def _resolve_input_path(value: str | Path | None, default: Path, repo_root: Path, label: str) -> Path:
    raw_value = str(value) if value is not None else str(default)
    _reject_unsafe_path_text(raw_value, label)
    candidate = Path(value) if value is not None else default
    if not candidate.is_absolute():
        candidate = repo_root / _pure_relative_path(raw_value, label)
    resolved = candidate.resolve()
    _ensure_inside_repo(resolved, repo_root, label)
    return resolved


def _resolve_output_path(value: str | Path | None, default: Path, repo_root: Path, label: str) -> Path:
    raw_value = str(value) if value is not None else str(default)
    _reject_unsafe_path_text(raw_value, label)
    candidate = Path(value) if value is not None else default
    if not candidate.is_absolute():
        candidate = repo_root / _pure_relative_path(raw_value, label)
    resolved = candidate.resolve()
    _ensure_inside_repo(resolved, repo_root, label)
    relative = resolved.relative_to(repo_root)
    if not relative.parts or relative.parts[0] != "outputs":
        raise ReviewedDryRunError(f"unsafe {label}: output must stay under outputs/")
    return resolved


def _pure_relative_path(value: str, label: str) -> Path:
    normalized = value.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if any(part in {"", ".."} for part in pure.parts):
        raise ReviewedDryRunError(f"unsafe {label}")
    return Path(*pure.parts)


def _ensure_inside_repo(path: Path, repo_root: Path, label: str) -> None:
    try:
        path.resolve().relative_to(repo_root)
    except ValueError as exc:
        raise ReviewedDryRunError(f"{label} must stay inside repository") from exc


def _reject_unsafe_path_text(value: str, label: str) -> None:
    if not value or "://" in value or value.startswith(("~", "\\")):
        raise ReviewedDryRunError(f"unsafe {label}")
    if Path(value).is_absolute() and WINDOWS_DRIVE_PATH.match(value) is None and value.startswith("/"):
        raise ReviewedDryRunError(f"unsafe {label}")
    if find_secret_like_values({label: value}):
        raise ReviewedDryRunError(f"unsafe {label}")
    lowered = value.lower()
    if ("chat" + "_id") in lowered or ".env" in lowered or ("ai" + "\u65e5\u62a5") in lowered:
        raise ReviewedDryRunError(f"unsafe {label}")
    if _value_has_forbidden_marker({label: value}) or _looks_like_forbidden_export(lowered):
        raise ReviewedDryRunError(f"unsafe {label}")


def _ensure_existing_file(path: Path, label: str) -> None:
    if not path.exists() or not path.is_file():
        raise ReviewedDryRunError(f"missing {label}: {path}")


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReviewedDryRunError(f"invalid {label}: {exc}") from exc
    if not isinstance(data, dict):
        raise ReviewedDryRunError(f"invalid {label}: JSON object required")
    return data


def _validate_review_notes(review_text: str, *, strict: bool) -> None:
    if not review_text.strip():
        raise ReviewedDryRunError("review.md is empty")
    required_phrases = ("Manual Review Checklist", "Source Review", "Claim Review")
    missing = [phrase for phrase in required_phrases if phrase.lower() not in review_text.lower()]
    if missing:
        raise ReviewedDryRunError("review.md missing required section: " + ", ".join(missing))
    if strict and "- [ ]" in review_text:
        raise ReviewedDryRunError("review.md contains unchecked required items in strict mode")


def _require_english_canonical_report(report: dict[str, Any]) -> None:
    if report.get("language") != "en":
        raise ReviewedDryRunError("report language must be en")
    for path, value in _iter_string_values(report):
        if CJK_TEXT.search(value):
            raise ReviewedDryRunError(f"report contains non-English or raw historical text at {path}")


def _reject_unsafe_values(*values: Any) -> None:
    for value in values:
        if _value_has_forbidden_marker(value):
            raise ReviewedDryRunError("unsafe value rejected")
        if find_secret_like_values(value) or find_public_safety_issues(value):
            raise ReviewedDryRunError("unsafe value rejected")
        for _, text in _iter_string_values(value):
            lowered = text.lower()
            if ("chat" + "_id") in lowered or ".env" in lowered:
                raise ReviewedDryRunError("unsafe value rejected")
            if _looks_like_forbidden_export(lowered):
                raise ReviewedDryRunError("unsupported export material rejected")


def _value_has_forbidden_marker(value: Any) -> bool:
    markers = (
        "AI" + "\u65e5\u62a5",
        "github" + "-daily" + "-intelligence",
        "00_MASTER" + "_PROMPT.md",
        "C:" + "\\Projects\\" + "github" + "-daily" + "-intelligence",
        "feat/public" + "-" + "github" + "-daily" + "-intelligence",
        "build" + "_report_",
        "send" + "-telegram" + "-report",
        "build" + "_ai_daily" + "_docx",
        "generate" + "_ai_word" + "_report",
        "render" + "-md" + "-to" + "-html",
    )
    lowered_markers = tuple(marker.lower() for marker in markers)
    return any(any(marker in text.lower() for marker in lowered_markers) for _, text in _iter_string_values(value))


def _looks_like_forbidden_export(lowered: str) -> bool:
    if lowered.startswith(("https://", "http://")):
        return False
    export_markers = (
        ".docx",
        ".htm",
        "telegram_export",
        "telegram-export",
        "raw_migration",
        "raw-historical-export",
    )
    return any(marker in lowered for marker in export_markers)


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


def _relative_repo_path(path: Path, repo_root: Path) -> Path:
    return Path(path.resolve().relative_to(repo_root.resolve()))


def _relative_or_text(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return str(path)