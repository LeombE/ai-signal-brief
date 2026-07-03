from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from typing import Iterable


REQUIRED_PUBLIC_DOCS = (
    "README.md",
    "LICENSE",
    "CONTENT-LICENSE.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
)
REQUIRED_TECHNICAL_DOCS = (
    "docs/report-schema.md",
    "docs/run-schema.md",
    "docs/source-registry.md",
    "docs/offline-rendering.md",
    "docs/run-metadata.md",
    "docs/quality-gates.md",
    "docs/archive-builder.md",
    "docs/static-site-builder.md",
)
REQUIRED_SCHEMAS = (
    "schemas/report.schema.json",
    "schemas/run.schema.json",
)
REQUIRED_EXAMPLES = (
    "examples/report.example.json",
    "examples/run.example.json",
)
CORE_COMMANDS = (
    "validate-report",
    "validate-run",
    "validate-sources",
    "validate-topic-sources",
    "validate-topics",
    "rank-topics",
    "discover-topics",
    "quality-gate",
    "archive-report",
    "build-site",
    "render-markdown",
    "render-telegram",
    "create-run-record",
    "public-readiness",
)
GENERATED_PATH_PREFIXES = ("outputs/", "reports/")
GENERATED_PATH_PARTS = ("archive" + "-example", "site" + "-example")
PRIVATE_MIGRATION_MARKERS = (
    "private" + "-migration",
    ".codex" + "-remote" + "-attachments",
    ".skill" + "-build",
)
ALLOWLIST_BY_FILE: dict[str, set[str]] = {
    "tests/fixtures/report.invalid.json": {"secret_like", "secret_assignment"},
    "tests/fixtures/run.invalid.json": {"secret_like", "secret_assignment", "chat_reference"},
    "tests/fixtures/sources.invalid.json": {"secret_like", "secret_assignment", "local_path"},
    "tests/fixtures/run.secret-like.json": {"secret_like", "secret_assignment", "chat_reference"},
    "tests/fixtures/report.mistaken-prompt.json": {"mistaken_prompt"},
    "tests/fixtures/topic-candidates.secret-like.json": {"secret_like", "secret_assignment"},
    "tests/fixtures/topic-candidates.private-path.json": {"local_path"},
    "tests/fixtures/topic_observations.private_path.json": {"local_path"},
    "tests/fixtures/topic_observations.secret_like.json": {"secret_like", "secret_assignment"},
    "tests/fixtures/topic_sources_live_secret_like_invalid.json": {"secret_like"},
}


@dataclass(frozen=True)
class PublicReadinessFinding:
    check_name: str
    path: str


@dataclass(frozen=True)
class PublicReadinessResult:
    checked_file_count: int
    findings: tuple[PublicReadinessFinding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings


def audit_public_readiness(
    repo_root: str | Path | None = None,
    *,
    tracked_files: Iterable[str] | None = None,
) -> PublicReadinessResult:
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    normalized_files = tuple(_normalize_path(path) for path in (tracked_files if tracked_files is not None else _git_tracked_files(root)))
    tracked_set = set(normalized_files)
    findings: list[PublicReadinessFinding] = []

    _check_required_paths(tracked_set, findings)
    _check_generated_outputs_not_tracked(normalized_files, findings)
    _check_tracked_file_contents(root, normalized_files, findings)
    _check_core_commands_documented(root, tracked_set, findings)

    unique_findings = tuple(sorted(set(findings), key=lambda item: (item.check_name, item.path)))
    return PublicReadinessResult(checked_file_count=len(normalized_files), findings=unique_findings)


def _git_tracked_files(root: Path) -> tuple[str, ...]:
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(line.strip() for line in completed.stdout.splitlines() if line.strip())


def _check_required_paths(tracked_set: set[str], findings: list[PublicReadinessFinding]) -> None:
    required_groups = (
        ("required_public_doc", REQUIRED_PUBLIC_DOCS),
        ("required_technical_doc", REQUIRED_TECHNICAL_DOCS),
        ("required_schema", REQUIRED_SCHEMAS),
        ("required_example", REQUIRED_EXAMPLES),
    )
    for check_name, paths in required_groups:
        for path in paths:
            if path not in tracked_set:
                findings.append(PublicReadinessFinding(check_name, path))


def _check_generated_outputs_not_tracked(files: tuple[str, ...], findings: list[PublicReadinessFinding]) -> None:
    for path in files:
        if path.startswith(GENERATED_PATH_PREFIXES) or any(part in path.split("/") for part in GENERATED_PATH_PARTS):
            findings.append(PublicReadinessFinding("generated_output_tracked", path))


def _check_tracked_file_contents(root: Path, files: tuple[str, ...], findings: list[PublicReadinessFinding]) -> None:
    for path in files:
        absolute_path = root / Path(*path.split("/"))
        if not absolute_path.exists() or not absolute_path.is_file():
            continue
        try:
            content = absolute_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        checks = _content_checks(content)
        checks.extend(_path_checks(path))
        for check_name in checks:
            if _is_allowlisted(path, check_name):
                continue
            findings.append(PublicReadinessFinding(check_name, path))


def _content_checks(content: str) -> list[str]:
    checks: list[str] = []
    if _telegram_token_pattern().search(content):
        checks.append("telegram_token")
    if _openai_key_pattern().search(content):
        checks.append("openai_key")
    if _chat_reference_pattern().search(content):
        checks.append("chat_reference")
    if _secret_assignment_pattern().search(content):
        checks.append("secret_assignment")
    if _test_secret_marker_pattern().search(content):
        checks.append("secret_like")
    if _local_path_pattern().search(content):
        checks.append("local_path")
    if ("AI" + "\u65e5\u62a5") in content:
        checks.append("private_ai_source")
    if _has_marker(content, _private_source_markers()):
        checks.append("private_ai_source")
    if _has_marker(content, _mistaken_prompt_markers()):
        checks.append("mistaken_prompt")
    if _has_marker(content, _legacy_builder_markers()):
        checks.append("legacy_builder")
    if _has_marker(content, PRIVATE_MIGRATION_MARKERS):
        checks.append("private_migration_content")
    return checks


def _path_checks(path: str) -> list[str]:
    checks: list[str] = []
    if path.endswith((".env", ".token", ".secret", ".key")) or "/.env" in path:
        checks.append("secret_file_tracked")
    if _has_marker(path, _private_source_markers()) or ("AI" + "\u65e5\u62a5") in path:
        checks.append("private_ai_source")
    if _has_marker(path, PRIVATE_MIGRATION_MARKERS):
        checks.append("private_migration_content")
    return checks


def _check_core_commands_documented(root: Path, tracked_set: set[str], findings: list[PublicReadinessFinding]) -> None:
    doc_paths = [path for path in ("README.md", *REQUIRED_TECHNICAL_DOCS, "docs/public-readiness.md") if path in tracked_set]
    combined = "\n".join((root / Path(*path.split("/"))).read_text(encoding="utf-8") for path in doc_paths if (root / Path(*path.split("/"))).exists())
    for command in CORE_COMMANDS:
        if command not in combined:
            findings.append(PublicReadinessFinding("command_not_documented", command))


def _is_allowlisted(path: str, check_name: str) -> bool:
    return check_name in ALLOWLIST_BY_FILE.get(path, set())


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def _has_marker(content: str, markers: tuple[str, ...]) -> bool:
    lowered = content.lower()
    return any(marker.lower() in lowered for marker in markers)


def _telegram_token_pattern() -> re.Pattern[str]:
    return re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b")


def _openai_key_pattern() -> re.Pattern[str]:
    return re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")


def _chat_reference_pattern() -> re.Pattern[str]:
    return re.compile("(?i)\\b" + "chat" + r"[_-]?id\b")


def _secret_assignment_pattern() -> re.Pattern[str]:
    names = (
        "OPENAI" + "_API" + "_KEY",
        "TELEGRAM" + "_BOT" + "_TOKEN",
        "BOT" + "_TOKEN",
        "api[_-]?key",
        "token",
        "secret",
        "chat" + r"[_-]?id",
    )
    return re.compile(r"(?i)\b(?:" + "|".join(names) + r")\s*[:=]\s*[^<\s]+")


def _test_secret_marker_pattern() -> re.Pattern[str]:
    return re.compile("secret" + "-like" + "-value" + "-for" + "-test")


def _local_path_pattern() -> re.Pattern[str]:
    return re.compile(r"\b[A-Za-z]:\\|(?:^|[\\/])Users[\\/]")


def _private_source_markers() -> tuple[str, ...]:
    return (
        "C:" + "\\" + "Us" + "ers" + "\\" + "Admin" + "\\" + "OneDrive" + "\\" + "Documents" + "\\" + "AI" + "\u65e5\u62a5",
    )


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
        "generate" + "_ai_word" + "_report",
    )
