import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_signal_brief.cli import main
from ai_signal_brief.public_readiness import PublicReadinessFinding, PublicReadinessResult, audit_public_readiness


ROOT = Path(__file__).resolve().parents[1]


class PublicReadinessTests(unittest.TestCase):
    def test_public_readiness_passes_on_current_clean_repo(self) -> None:
        result = audit_public_readiness(ROOT)

        self.assertTrue(result.ok, result.findings)

    def test_secret_like_tracked_fixture_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, tracked = _create_minimal_ready_tree(Path(directory))
            _write(root, "tests/fixtures/readiness-secret.txt", ("TO" + "KEN=" + "secret" + "-like" + "-value" + "-for" + "-test" + "\n"))
            tracked.append("tests/fixtures/readiness-secret.txt")

            result = audit_public_readiness(root, tracked_files=tracked)

        self.assertFalse(result.ok)
        self.assertTrue(any(item.check_name in {"secret_assignment", "secret_like"} for item in result.findings))

    def test_mistaken_prompt_reference_fixture_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, tracked = _create_minimal_ready_tree(Path(directory))
            project = "github" + "-daily" + "-intelligence"
            _write(root, "tests/fixtures/readiness-mistaken.txt", project + "\n")
            tracked.append("tests/fixtures/readiness-mistaken.txt")

            result = audit_public_readiness(root, tracked_files=tracked)

        self.assertFalse(result.ok)
        self.assertTrue(any(item.check_name == "mistaken_prompt" for item in result.findings))

    def test_private_path_fixture_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, tracked = _create_minimal_ready_tree(Path(directory))
            private_path = "C:" + "\\" + "Users" + "\\" + "Admin" + "\\" + "OneDrive" + "\\" + "Documents" + "\\" + "AI" + "\u65e5\u62a5"
            _write(root, "tests/fixtures/readiness-private-path.txt", private_path + "\n")
            tracked.append("tests/fixtures/readiness-private-path.txt")

            result = audit_public_readiness(root, tracked_files=tracked)

        self.assertFalse(result.ok)
        self.assertTrue(any(item.check_name in {"local_path", "private_ai_source"} for item in result.findings))

    def test_generated_output_path_fixture_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, tracked = _create_minimal_ready_tree(Path(directory))
            _write(root, "outputs/readiness/report.json", "{}\n")
            tracked.append("outputs/readiness/report.json")

            result = audit_public_readiness(root, tracked_files=tracked)

        self.assertFalse(result.ok)
        self.assertTrue(any(item.check_name == "generated_output_tracked" for item in result.findings))

    def test_missing_required_doc_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, tracked = _create_minimal_ready_tree(Path(directory))
            tracked.remove("SECURITY.md")

            result = audit_public_readiness(root, tracked_files=tracked)

        self.assertFalse(result.ok)
        self.assertIn(("required_public_doc", "SECURITY.md"), {(item.check_name, item.path) for item in result.findings})

    def test_github_actions_secret_context_names_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, tracked = _create_minimal_ready_tree(Path(directory))
            _write(
                root,
                ".github/workflows/daily-ai-report.yml",
                "env:\n"
                "  TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}\n"
                "  TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}\n",
            )
            tracked.append(".github/workflows/daily-ai-report.yml")

            result = audit_public_readiness(root, tracked_files=tracked)

        self.assertTrue(result.ok, result.findings)
    def test_cli_returns_nonzero_on_failure(self) -> None:
        failed_result = PublicReadinessResult(
            checked_file_count=1,
            findings=(PublicReadinessFinding("secret_assignment", "example.txt"),),
        )
        with patch("ai_signal_brief.cli.audit_public_readiness", return_value=failed_result):
            self.assertEqual(main(["public-readiness"]), 1)


def _create_minimal_ready_tree(root: Path) -> tuple[Path, list[str]]:
    tracked = [
        "README.md",
        "LICENSE",
        "CONTENT-LICENSE.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "docs/report-schema.md",
        "docs/run-schema.md",
        "docs/source-registry.md",
        "docs/offline-rendering.md",
        "docs/run-metadata.md",
        "docs/quality-gates.md",
        "docs/archive-builder.md",
        "docs/static-site-builder.md",
        "schemas/report.schema.json",
        "schemas/run.schema.json",
        "examples/report.example.json",
        "examples/run.example.json",
    ]
    docs_text = "\n".join(
        [
            "validate-report",
            "validate-run",
            "validate-sources",
            "validate-topic-sources",
            "validate-topics",
            "rank-topics",
            "discover-topics",
            "fetch-source-replay",
            "quality-gate",
            "archive-report",
            "build-site",
            "render-markdown",
            "render-telegram",
            "create-run-record",
            "public-readiness",
        ]
    )
    for path in tracked:
        content = docs_text if path == "README.md" else "placeholder\n"
        _write(root, path, content)
    return root, tracked


def _write(root: Path, relative_path: str, content: str) -> None:
    path = root / Path(*relative_path.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()