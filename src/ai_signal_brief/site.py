from __future__ import annotations

from dataclasses import dataclass
from html import escape
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

from .quality_gate import (
    _has_marker,
    _has_secret_or_private_values,
    _legacy_builder_markers,
    _mistaken_prompt_markers,
)
from .validation import find_secret_like_values, validate_report_path, validate_run_path


SITE_SCHEMA_VERSION = "1.0.0"
WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")


class SiteBuildError(RuntimeError):
    """Raised when the offline static site cannot be built safely."""


@dataclass(frozen=True)
class SiteBuildResult:
    site_root: Path
    homepage_path: Path
    stylesheet_path: Path
    manifest_path: Path
    report_pages: tuple[Path, ...]


def build_site(
    archive_path: str | Path,
    output_path: str | Path,
    *,
    repo_root: str | Path | None = None,
) -> SiteBuildResult:
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    archive_root = _resolve_safe_existing_archive_path(archive_path, root)
    site_root = _resolve_safe_output_path(output_path, root)

    archive_index_path = archive_root / "index.json"
    if not archive_index_path.exists():
        raise SiteBuildError("archive index is required")

    archive_index = _load_json_object(archive_index_path, "archive index")
    _reject_unsafe_values(archive_index)
    entries = _sorted_archive_entries(archive_index)

    loaded_reports = [_load_archive_entry(archive_root, entry) for entry in entries]
    for loaded in loaded_reports:
        _reject_unsafe_values(loaded["entry"], loaded["report"], loaded["run"], {"markdown": loaded.get("markdown", "")})

    assets_dir = site_root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    stylesheet_path = assets_dir / "style.css"
    stylesheet_path.write_text(_stylesheet(), encoding="utf-8")

    report_pages: list[Path] = []
    for loaded in loaded_reports:
        page_path = site_root / _report_page_relative_path(loaded["report"])
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(_render_report_page(loaded), encoding="utf-8")
        report_pages.append(page_path)

    homepage_path = site_root / "index.html"
    homepage_path.write_text(_render_homepage(loaded_reports), encoding="utf-8")

    manifest_path = site_root / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest(loaded_reports), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _scan_generated_site(site_root)
    return SiteBuildResult(
        site_root=site_root,
        homepage_path=homepage_path,
        stylesheet_path=stylesheet_path,
        manifest_path=manifest_path,
        report_pages=tuple(report_pages),
    )


def _resolve_safe_existing_archive_path(path: str | Path, repo_root: Path) -> Path:
    resolved = _resolve_inside_repo(path, repo_root, "archive path")
    if not resolved.exists() or not resolved.is_dir():
        raise SiteBuildError("archive directory is required")
    return resolved


def _resolve_safe_output_path(path: str | Path, repo_root: Path) -> Path:
    return _resolve_inside_repo(path, repo_root, "output path")


def _resolve_inside_repo(path: str | Path, repo_root: Path, label: str) -> Path:
    raw_path = str(path)
    if not raw_path or "://" in raw_path or raw_path.startswith(("~", "\\")):
        raise SiteBuildError(f"unsafe {label} rejected")
    _reject_unsafe_path_text(raw_path, label)

    root = repo_root.resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        normalized = raw_path.replace("\\", "/")
        pure_path = PurePosixPath(normalized)
        if any(part in {"", ".."} for part in pure_path.parts):
            raise SiteBuildError(f"unsafe {label} rejected")
        candidate = root / Path(*pure_path.parts)
    elif WINDOWS_DRIVE_PATH.match(raw_path) is None and raw_path.startswith("/"):
        raise SiteBuildError(f"unsafe {label} rejected")

    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SiteBuildError(f"{label} must stay inside repository") from exc
    return resolved


def _reject_unsafe_path_text(raw_path: str, label: str) -> None:
    value = {label: raw_path}
    if find_secret_like_values(value):
        raise SiteBuildError(f"unsafe {label} rejected")
    lowered = raw_path.lower()
    if ("chat" + "_id") in lowered or ".env" in lowered or ("ai" + "\u65e5\u62a5") in lowered:
        raise SiteBuildError(f"unsafe {label} rejected")
    if _has_marker(value, _mistaken_prompt_markers()) or _has_marker(value, _legacy_builder_markers()):
        raise SiteBuildError(f"unsafe {label} rejected")


def _load_archive_entry(archive_root: Path, entry: dict[str, Any]) -> dict[str, Any]:
    paths = entry.get("paths")
    if not isinstance(paths, dict):
        raise SiteBuildError("archive entry paths are required")

    report_path = _safe_archive_child(archive_root, paths.get("report"), "report path")
    run_path = _safe_archive_child(archive_root, paths.get("run"), "run path")
    markdown_path = _safe_archive_child(archive_root, paths.get("markdown"), "markdown path", required=False)

    if not validate_report_path(report_path).ok:
        raise SiteBuildError("archive report failed validation")
    if not validate_run_path(run_path).ok:
        raise SiteBuildError("archive run failed validation")

    report = _load_json_object(report_path, "archive report")
    run = _load_json_object(run_path, "archive run")
    markdown = markdown_path.read_text(encoding="utf-8") if markdown_path and markdown_path.exists() else ""
    return {"entry": entry, "report": report, "run": run, "markdown": markdown}


def _safe_archive_child(archive_root: Path, value: Any, label: str, *, required: bool = True) -> Path | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value:
        raise SiteBuildError(f"{label} is required")
    if value.startswith(("/", "\\", "~")) or "://" in value or WINDOWS_DRIVE_PATH.match(value):
        raise SiteBuildError(f"unsafe {label} rejected")
    normalized = value.replace("\\", "/")
    pure_path = PurePosixPath(normalized)
    if any(part in {"", ".."} for part in pure_path.parts):
        raise SiteBuildError(f"unsafe {label} rejected")
    resolved = (archive_root / Path(*pure_path.parts)).resolve()
    try:
        resolved.relative_to(archive_root.resolve())
    except ValueError as exc:
        raise SiteBuildError(f"{label} must stay inside archive") from exc
    if required and not resolved.exists():
        raise SiteBuildError(f"{label} does not exist")
    return resolved


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SiteBuildError(f"{label} is invalid") from exc
    if not isinstance(data, dict):
        raise SiteBuildError(f"{label} must be an object")
    return data


def _sorted_archive_entries(index: dict[str, Any]) -> list[dict[str, Any]]:
    reports = index.get("reports")
    if not isinstance(reports, list):
        raise SiteBuildError("archive reports list is required")
    entries = [entry for entry in reports if isinstance(entry, dict)]
    if len(entries) != len(reports):
        raise SiteBuildError("archive report entries must be objects")
    return sorted(entries, key=lambda entry: (str(entry.get("report_date", "")), str(entry.get("generated_at", ""))), reverse=True)


def _render_homepage(loaded_reports: list[dict[str, Any]]) -> str:
    items = []
    for loaded in loaded_reports:
        report = loaded["report"]
        href = _report_page_relative_path(report).as_posix()
        items.append(
            "\n".join(
                [
                    '<li class="report-card">',
                    f'  <a href="{_e(href)}">{_e(_string(report, "title"))}</a>',
                    f'  <span>{_e(_string(report, "report_date"))}</span>',
                    f'  <small>{_e(_string(report, "generated_at"))}</small>',
                    "</li>",
                ]
            )
        )
    return _html_document(
        "AI Signal Brief",
        "\n".join(
            [
                "<main>",
                "<h1>AI Signal Brief</h1>",
                '<p class="disclosure">Offline-generated static preview from canonical archive data. No external scripts, CSS, or remote images are used.</p>',
                f'<p class="summary">Archive summary: {_e(str(len(loaded_reports)))} report(s), sorted by report date descending.</p>',
                '<ol class="report-list">',
                *items,
                "</ol>",
                "</main>",
            ]
        ),
        stylesheet_href="assets/style.css",
    )


def _render_report_page(loaded: dict[str, Any]) -> str:
    report = loaded["report"]
    markdown = loaded.get("markdown", "")
    body = [
        "<main>",
        '<p><a href="../../../index.html">Back to archive</a></p>',
        f"<h1>{_e(_string(report, 'title'))}</h1>",
        '<dl class="metadata">',
        f"<dt>Report date</dt><dd>{_e(_string(report, 'report_date'))}</dd>",
        f"<dt>Generated at</dt><dd>{_e(_string(report, 'generated_at'))}</dd>",
        f"<dt>Timezone</dt><dd>{_e(_string(report, 'timezone'))}</dd>",
        "</dl>",
        '<p class="disclosure">Offline-generated static report page from canonical archive data.</p>',
        _top_story_summary(report),
        _ranked_stories(report),
        _source_list(report),
        _provenance(report),
    ]
    if markdown:
        body.extend(["<section>", "<h2>Archive Note</h2>", f"<pre>{_e(markdown)}</pre>", "</section>"])
    body.append("</main>")
    return _html_document(_string(report, "title"), "\n".join(body), stylesheet_href="../../../assets/style.css")


def _top_story_summary(report: dict[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    top_stories = summary.get("top_stories") if isinstance(summary, dict) else []
    items: list[str] = []
    if isinstance(top_stories, list):
        for item in top_stories:
            if not isinstance(item, dict):
                continue
            headline = _e(str(item.get("headline", "")))
            why = _e(str(item.get("why_it_matters", "")))
            rank = _e(str(item.get("rank", "")))
            items.append(f"<li><strong>{rank}. {headline}</strong><p>{why}</p></li>")
    return "\n".join(["<section>", "<h2>Top Story Summary</h2>", "<ol>", *items, "</ol>", "</section>"])


def _ranked_stories(report: dict[str, Any]) -> str:
    stories = report.get("stories") if isinstance(report.get("stories"), list) else []
    story_blocks: list[str] = []
    for story in sorted([story for story in stories if isinstance(story, dict)], key=lambda item: item.get("rank", 9999)):
        importance = story.get("importance") if isinstance(story.get("importance"), dict) else {}
        claims = story.get("claims") if isinstance(story.get("claims"), list) else []
        claim_items: list[str] = []
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            source_ids = ", ".join(str(value) for value in claim.get("source_ids", []) if isinstance(value, str))
            claim_items.append(
                f"<li>{_e(str(claim.get('text', '')))} <span class=\"source-ref\">Sources: {_e(source_ids)}</span></li>"
            )
        story_blocks.append(
            "\n".join(
                [
                    "<article>",
                    f"<h3>{_e(str(story.get('rank', '')))}. {_e(str(story.get('title', '')))}</h3>",
                    f"<p>Status: {_e(str(story.get('status', '')))}</p>",
                    f"<p>Importance: {_e(str(importance.get('score', '')))} - {_e(str(importance.get('rationale', '')))}</p>",
                    f"<p>{_e(str(story.get('analysis', '')))}</p>",
                    "<h4>Claims</h4>",
                    "<ul>",
                    *claim_items,
                    "</ul>",
                    "</article>",
                ]
            )
        )
    return "\n".join(["<section>", "<h2>Ranked Stories</h2>", *story_blocks, "</section>"])


def _source_list(report: dict[str, Any]) -> str:
    sources = report.get("sources") if isinstance(report.get("sources"), list) else []
    items: list[str] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        items.append(
            "\n".join(
                [
                    "<li>",
                    f"<strong>{_e(str(source.get('id', '')))}</strong>: {_e(str(source.get('title', '')))}",
                    f"<br>Publisher: {_e(str(source.get('publisher', '')))}",
                    f"<br>Type: {_e(str(source.get('source_type', '')))}",
                    f"<br>URL: {_e(str(source.get('url', '')))}",
                    "</li>",
                ]
            )
        )
    return "\n".join(["<section>", "<h2>Sources</h2>", "<ul>", *items, "</ul>", "</section>"])


def _provenance(report: dict[str, Any]) -> str:
    provenance = report.get("provenance")
    text = json.dumps(provenance if isinstance(provenance, dict) else {}, ensure_ascii=False, sort_keys=True)
    return "\n".join(["<section>", "<h2>Provenance</h2>", f"<p>{_e(text)}</p>", "</section>"])


def _html_document(title: str, body: str, *, stylesheet_href: str) -> str:
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{_e(title)}</title>",
            f'<link rel="stylesheet" href="{_e(stylesheet_href)}">',
            "</head>",
            "<body>",
            body,
            "</body>",
            "</html>",
            "",
        ]
    )


def _stylesheet() -> str:
    return """body { font-family: Arial, sans-serif; margin: 0; color: #18202a; background: #f7f8fb; }
main { max-width: 980px; margin: 0 auto; padding: 32px 20px 56px; }
a { color: #0f5fb8; }
.disclosure, .summary { color: #4e5a66; }
.report-list { padding-left: 24px; }
.report-card { margin: 14px 0; padding: 14px; background: #ffffff; border: 1px solid #d9e0ea; border-radius: 6px; }
.report-card a { display: block; font-weight: 700; }
.report-card span, .report-card small { display: block; margin-top: 4px; }
.metadata { display: grid; grid-template-columns: max-content 1fr; gap: 8px 16px; }
section, article { margin-top: 28px; }
article { padding: 16px; background: #ffffff; border: 1px solid #d9e0ea; border-radius: 6px; }
.source-ref { color: #4e5a66; display: block; margin-top: 4px; }
pre { white-space: pre-wrap; background: #ffffff; border: 1px solid #d9e0ea; padding: 14px; border-radius: 6px; }
"""


def _manifest(loaded_reports: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": SITE_SCHEMA_VERSION,
        "generated_by": "ai_signal_brief.build_site",
        "report_count": len(loaded_reports),
        "reports": [
            {
                "report_id": _string(loaded["report"], "report_id"),
                "report_date": _string(loaded["report"], "report_date"),
                "path": _report_page_relative_path(loaded["report"]).as_posix(),
            }
            for loaded in loaded_reports
        ],
    }


def _report_page_relative_path(report: dict[str, Any]) -> Path:
    year, month, day = _string(report, "report_date").split("-")
    return Path(year) / month / day / "index.html"


def _scan_generated_site(site_root: Path) -> None:
    for path in site_root.rglob("*"):
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        value = {"path": path.relative_to(site_root).as_posix(), "content": content}
        _reject_unsafe_values(value)
        if find_secret_like_values(content):
            raise SiteBuildError("generated site contains secret-like values")


def _reject_unsafe_values(*values: dict[str, Any]) -> None:
    for value in values:
        if _has_secret_or_private_values(value):
            raise SiteBuildError("unsafe value rejected")
        if _has_marker(value, _mistaken_prompt_markers()):
            raise SiteBuildError("mistaken prompt reference rejected")
        if _has_marker(value, _legacy_builder_markers()):
            raise SiteBuildError("legacy builder reference rejected")


def _string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    return value if isinstance(value, str) else ""


def _e(value: str) -> str:
    return escape(value, quote=True)