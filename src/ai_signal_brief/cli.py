from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path

from . import __version__
from .validation import ValidationResult, validate_report_path, validate_run_path


REQUIRED_PROJECT_FILES = (
    "schemas/report.schema.json",
    "schemas/run.schema.json",
    "examples/report.example.json",
    "examples/run.example.json",
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

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())