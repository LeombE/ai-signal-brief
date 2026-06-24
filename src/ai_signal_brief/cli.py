from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path

from . import __version__
from .rendering import RenderError, render_markdown_from_path, render_telegram_from_path, write_text_output
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-signal-brief",
        description="Source-backed AI briefing pipeline skeleton.",
    )
    parser.add_argument("--version", action="store_true", help="Print package version and exit.")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("doctor", help="Run local skeleton checks without network access.")

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

    if args.command == "validate-report":
        return print_validation_result("Report", validate_report_path(args.path))

    if args.command == "validate-run":
        return print_validation_result("Run", validate_run_path(args.path))

    if args.command == "validate-sources":
        return print_validation_result("Source registry", validate_sources_path(args.path))

    if args.command == "list-source-priorities":
        return list_source_priorities(args.path)

    if args.command == "render-markdown":
        return render_markdown_command(args.path, args.out)

    if args.command == "render-telegram":
        return render_telegram_command(args.path, args.out)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())