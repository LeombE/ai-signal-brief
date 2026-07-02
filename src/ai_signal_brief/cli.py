from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path

from . import __version__
from .archive import ArchiveError, build_archive
from .public_readiness import PublicReadinessResult, audit_public_readiness
from .quality_gate import QualityGateResult, run_quality_gate
from .rendering import RenderError, render_markdown_from_path, render_telegram_from_path, write_text_output
from .run_metadata import RunMetadataError, create_run_record, write_run_record
from .site import SiteBuildError, build_site
from .validation import (
    ValidationResult,
    load_source_registry,
    source_priorities,
    validate_report_path,
    validate_run_path,
    validate_sources_path,
)


REQUIRED_PROJECT_FILES = (
    "schemas/report.schema.json",
    "schemas/run.schema.json",
    "examples/report.example.json",
    "examples/run.example.json",
    "config/sources.example.json",
)


def project_root() -> Path:
    """Return the repository root for an editable source-tree execution."""
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def run_doctor(root: Path | None = None) -> int:
    root = root or project_root()
    print(f"AI Signal Brief {__version__}")
    print(f"Python {platform.python_version()}")
    print(f"Project root: {root}")

    missing: list[str] = []
    invalid_json: list[str] = []

    for relative in REQUIRED_PROJECT_FILES:
        path = root / relative
        if not path.exists():
            missing.append(relative)
            continue
        try:
            load_json(path)
        except json.JSONDecodeError:
            invalid_json.append(relative)

    if missing:
        print("Missing files:")
        for item in missing:
            print(f"- {item}")
    if invalid_json:
        print("Invalid JSON files:")
        for item in invalid_json:
            print(f"- {item}")

    if missing or invalid_json:
        return 1

    print("Doctor checks passed.")
    return 0


def print_validation_result(label: str, result: ValidationResult) -> int:
    if result.ok:
        print(f"{label} validation passed: {result.path}")
        return 0

    print(f"{label} validation failed: {result.path}")
    for error in result.errors:
        print(f"- {error}")
    return 1


def list_source_priorities(path: str | Path | None = None) -> int:
    registry_path = Path(path) if path else project_root() / "config" / "sources.example.json"
    validation_result = validate_sources_path(registry_path)
    if not validation_result.ok:
        return print_validation_result("Source registry", validation_result)

    registry = load_source_registry(registry_path)
    print(f"Source priorities: {registry_path}")
    for category in source_priorities(registry):
        print(f"{category['priority']}. {category['id']} - {category['description']}")
    return 0


def print_quality_gate_result(result: QualityGateResult) -> int:
    if result.ok:
        print("Quality gate PASS")
        return 0

    print("Quality gate FAIL")
    print("Failed checks:")
    for check_name in result.failed_checks:
        print(f"- {check_name}")
    return 1


def print_public_readiness_result(result: PublicReadinessResult) -> int:
    if result.ok:
        print("Public readiness PASS")
        print(f"Tracked files checked: {result.checked_file_count}")
        return 0

    print("Public readiness FAIL")
    print(f"Tracked files checked: {result.checked_file_count}")
    print("Failed checks:")
    for finding in result.findings:
        print(f"- {finding.check_name}: {finding.path}")
    return 1


def quality_gate_command(report_path: str, run_path: str, sources_path: str) -> int:
    result = run_quality_gate(report_path, run_path, sources_path, repo_root=project_root())
    return print_quality_gate_result(result)


def public_readiness_command() -> int:
    result = audit_public_readiness(project_root())
    return print_public_readiness_result(result)


def archive_report_command(report_path: str, run_path: str, sources_path: str, output_path: str) -> int:
    try:
        result = build_archive(report_path, run_path, sources_path, output_path, repo_root=project_root())
    except ArchiveError as exc:
        print(f"Archive build failed: {exc}")
        return 1

    print("Archive build PASS")
    print(f"Archive root: {result.archive_root}")
    print(f"Report: {result.report_path}")
    print(f"Run: {result.run_path}")
    print(f"Markdown index: {result.markdown_path}")
    print(f"Archive index: {result.index_path}")
    return 0


def build_site_command(archive_path: str, output_path: str) -> int:
    try:
        result = build_site(archive_path, output_path, repo_root=project_root())
    except SiteBuildError as exc:
        print(f"Site build failed: {exc}")
        return 1

    print("Site build PASS")
    print(f"Site root: {result.site_root}")
    print(f"Homepage: {result.homepage_path}")
    print(f"Stylesheet: {result.stylesheet_path}")
    print(f"Manifest: {result.manifest_path}")
    print(f"Report pages: {len(result.report_pages)}")
    return 0


def render_markdown_command(path: str, output_path: str) -> int:
    try:
        rendered = render_markdown_from_path(path)
        written = write_text_output(rendered, output_path)
    except RenderError as exc:
        print(f"Markdown render failed: {exc}")
        return 1
    print(f"Markdown render written: {written}")
    return 0


def render_telegram_command(path: str, output_path: str) -> int:
    try:
        rendered = render_telegram_from_path(path)
        written = write_text_output(rendered, output_path)
    except RenderError as exc:
        print(f"Telegram preview render failed: {exc}")
        return 1
    print(f"Telegram preview written: {written}")
    return 0


def create_run_record_command(
    report_path: str,
    output_path: str,
    artifacts: list[str] | None,
    started_at: str | None,
    ended_at: str | None,
    timezone_name: str,
) -> int:
    try:
        record = create_run_record(
            report_path,
            artifacts,
            started_at=started_at,
            ended_at=ended_at,
            timezone_name=timezone_name,
        )
        written = write_run_record(record, output_path)
    except RunMetadataError as exc:
        print(f"Run metadata generation failed: {exc}")
        return 1
    print(f"Run metadata written: {written}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-signal-brief",
        description="Source-backed AI briefing pipeline skeleton.",
    )
    parser.add_argument("--version", action="store_true", help="Print package version and exit.")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("doctor", help="Run local skeleton checks without network access.")
    subparsers.add_parser("public-readiness", help="Audit tracked files for public repository readiness.")

    report_parser = subparsers.add_parser("validate-report", help="Validate a report.json file.")
    report_parser.add_argument("path", help="Path to report JSON.")

    run_parser = subparsers.add_parser("validate-run", help="Validate a run.json file.")
    run_parser.add_argument("path", help="Path to run metadata JSON.")

    sources_parser = subparsers.add_parser("validate-sources", help="Validate a source registry JSON file.")
    sources_parser.add_argument("path", help="Path to source registry JSON.")

    priorities_parser = subparsers.add_parser("list-source-priorities", help="List source category priorities.")
    priorities_parser.add_argument(
        "--path",
        default=None,
        help="Optional source registry path. Defaults to config/sources.example.json.",
    )

    site_parser = subparsers.add_parser("build-site", help="Build an offline static site from an archive.")
    site_parser.add_argument("--archive", required=True, help="Archive directory containing index.json.")
    site_parser.add_argument("--out", required=True, help="Static site output directory.")

    archive_parser = subparsers.add_parser("archive-report", help="Build an offline public report archive entry.")
    archive_parser.add_argument("--report", required=True, help="Path to report JSON.")
    archive_parser.add_argument("--run", required=True, help="Path to run metadata JSON.")
    archive_parser.add_argument("--sources", required=True, help="Path to source registry JSON.")
    archive_parser.add_argument("--out", required=True, help="Archive output directory.")

    quality_gate_parser = subparsers.add_parser("quality-gate", help="Run offline report/run/source quality gates.")
    quality_gate_parser.add_argument("--report", required=True, help="Path to report JSON.")
    quality_gate_parser.add_argument("--run", required=True, help="Path to run metadata JSON.")
    quality_gate_parser.add_argument("--sources", required=True, help="Path to source registry JSON.")

    create_run_parser = subparsers.add_parser(
        "create-run-record",
        help="Create offline run metadata from a validated report JSON.",
    )
    create_run_parser.add_argument("--report", required=True, help="Path to report JSON.")
    create_run_parser.add_argument("--out", required=True, help="Output run metadata JSON path.")
    create_run_parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        help="Optional artifact in kind=relative/path format. May be repeated.",
    )
    create_run_parser.add_argument("--started-at", default=None, help="Deterministic started_at timestamp.")
    create_run_parser.add_argument("--ended-at", default=None, help="Deterministic ended_at timestamp.")
    create_run_parser.add_argument("--timezone", default="Asia/Kuala_Lumpur", help="IANA timezone name.")

    markdown_parser = subparsers.add_parser("render-markdown", help="Render a validated report JSON to Markdown.")
    markdown_parser.add_argument("path", help="Path to report JSON.")
    markdown_parser.add_argument("--out", required=True, help="Output Markdown path.")

    telegram_parser = subparsers.add_parser("render-telegram", help="Render a Telegram text preview without sending it.")
    telegram_parser.add_argument("path", help="Path to report JSON.")
    telegram_parser.add_argument("--out", required=True, help="Output text path.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    if args.command == "doctor":
        return run_doctor()

    if args.command == "public-readiness":
        return public_readiness_command()

    if args.command == "validate-report":
        return print_validation_result("Report", validate_report_path(args.path))

    if args.command == "validate-run":
        return print_validation_result("Run", validate_run_path(args.path))

    if args.command == "validate-sources":
        return print_validation_result("Source registry", validate_sources_path(args.path))

    if args.command == "list-source-priorities":
        return list_source_priorities(args.path)

    if args.command == "build-site":
        return build_site_command(args.archive, args.out)

    if args.command == "archive-report":
        return archive_report_command(args.report, args.run, args.sources, args.out)

    if args.command == "quality-gate":
        return quality_gate_command(args.report, args.run, args.sources)

    if args.command == "create-run-record":
        return create_run_record_command(
            args.report,
            args.out,
            args.artifact,
            args.started_at,
            args.ended_at,
            args.timezone,
        )

    if args.command == "render-markdown":
        return render_markdown_command(args.path, args.out)

    if args.command == "render-telegram":
        return render_telegram_command(args.path, args.out)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())