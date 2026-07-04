import contextlib
import io
import json
import shutil
import socket
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_signal_brief.cli import main
from ai_signal_brief.live_dry_run import LiveDryRunError, discover_topics_live_dry_run
from ai_signal_brief.topic_validation import validate_topics_path


ROOT = Path(__file__).resolve().parents[1]
LIVE_SOURCES = ROOT / "config" / "topic_sources.live.example.json"
OUTPUT_ROOT = ROOT / "outputs" / "test-live-dry-run"
WORKFLOW = ROOT / ".github" / "workflows" / "topic-scan-preview.yml"


class LiveDryRunTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(OUTPUT_ROOT, ignore_errors=True)
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, OUTPUT_ROOT, ignore_errors=True)

    def test_cli_generates_metadata_only_topic_candidates(self) -> None:
        out_relative = "outputs/test-live-dry-run/success/topics.json"

        exit_code, stdout = _run_cli(_live_dry_run_args(out_relative))

        self.assertEqual(exit_code, 0, stdout)
        self.assertIn("Topic discovery PASS", stdout)
        output_path = ROOT / out_relative
        data = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(data["provenance"]["generation_mode"], "live_dry_run_metadata_only")
        self.assertIs(data["provenance"]["live_fetching"], False)
        self.assertEqual(data["provenance"]["publication_status"], "not_published")
        self.assertEqual(data["provenance"]["telegram_delivery"], "not_connected")
        self.assertEqual(data["provenance"]["openai_api_usage"], "not_configured")
        self.assertEqual(data["provenance"]["image_generation"], "not_configured")
        self.assertEqual(data["provenance"]["docx_generation"], "not_configured")
        self.assertEqual(data["provenance"]["production_pages_deploy"], "not_configured")
        self.assertGreater(len(data["topics"]), 0)
        self.assertEqual(validate_topics_path(output_path).ok, True)

    def test_all_generated_topics_are_unresolved_and_review_required(self) -> None:
        out_relative = "outputs/test-live-dry-run/review-required/topics.json"
        self.assertEqual(_run_cli(_live_dry_run_args(out_relative))[0], 0)

        data = json.loads((ROOT / out_relative).read_text(encoding="utf-8"))
        required_flags = {"live_dry_run", "metadata_only", "manual_review_required", "no_live_fetch", "no_publication_candidate"}
        for topic in data["topics"]:
            self.assertEqual(topic["candidate_status"], "unresolved")
            self.assertTrue(topic["review_required"])
            self.assertEqual(topic["review_recommendation"], "needs_source_review")
            self.assertTrue(required_flags.issubset(set(topic["safety_flags"])))

    def test_missing_artifact_only_flag_fails(self) -> None:
        args = _live_dry_run_args("outputs/test-live-dry-run/missing-artifact/topics.json")
        args.remove("--artifact-only")

        exit_code, stdout = _run_cli(args)

        self.assertNotEqual(exit_code, 0)
        self.assertIn("--artifact-only is required", stdout)

    def test_missing_metadata_only_flag_fails(self) -> None:
        args = _live_dry_run_args("outputs/test-live-dry-run/missing-metadata/topics.json")
        args.remove("--metadata-only")

        exit_code, stdout = _run_cli(args)

        self.assertNotEqual(exit_code, 0)
        self.assertIn("--metadata-only is required", stdout)

    def test_enabled_true_registry_fails(self) -> None:
        registry = _registry_with(lambda source: source.update({"enabled": True}))

        exit_code, stdout = _run_cli(_live_dry_run_args("outputs/test-live-dry-run/enabled/topics.json", sources=registry))

        self.assertNotEqual(exit_code, 0)
        self.assertIn("enabled", stdout)

    def test_fetch_mode_not_disabled_fails(self) -> None:
        registry = _registry_with(lambda source: source.update({"fetch_mode": "official_feed"}))

        exit_code, stdout = _run_cli(_live_dry_run_args("outputs/test-live-dry-run/fetch-mode/topics.json", sources=registry))

        self.assertNotEqual(exit_code, 0)
        self.assertIn("fetch_mode", stdout)

    def test_missing_rate_limit_metadata_fails(self) -> None:
        registry = _registry_with(lambda source: source.pop("max_requests_per_run", None))

        exit_code, stdout = _run_cli(_live_dry_run_args("outputs/test-live-dry-run/rate-limit/topics.json", sources=registry))

        self.assertNotEqual(exit_code, 0)
        self.assertIn("max_requests_per_run", stdout)

    def test_missing_timeout_metadata_fails(self) -> None:
        registry = _registry_with(lambda source: source.pop("timeout_seconds", None))

        exit_code, stdout = _run_cli(_live_dry_run_args("outputs/test-live-dry-run/timeout/topics.json", sources=registry))

        self.assertNotEqual(exit_code, 0)
        self.assertIn("timeout_seconds", stdout)

    def test_unsafe_non_https_url_fails(self) -> None:
        registry = _registry_with(lambda source: source.update({"url": "http://localhost/private"}))

        exit_code, stdout = _run_cli(_live_dry_run_args("outputs/test-live-dry-run/url/topics.json", sources=registry))

        self.assertNotEqual(exit_code, 0)
        self.assertIn("public HTTPS", stdout)

    def test_unsafe_output_path_is_rejected(self) -> None:
        with self.assertRaises(LiveDryRunError):
            discover_topics_live_dry_run(
                scan_date="2026-06-24",
                sources_path=LIVE_SOURCES,
                output_path="../topic-candidates.json",
                artifact_only=True,
                metadata_only=True,
                repo_root=ROOT,
            )

    def test_no_network_call_is_made(self) -> None:
        def fail_network(*args: object, **kwargs: object) -> None:
            raise AssertionError("network call attempted")

        with patch.object(socket, "create_connection", side_effect=fail_network):
            result = discover_topics_live_dry_run(
                scan_date="2026-06-24",
                sources_path=LIVE_SOURCES,
                output_path="outputs/test-live-dry-run/no-network/topics.json",
                artifact_only=True,
                metadata_only=True,
                repo_root=ROOT,
            )

        self.assertGreater(len(result.candidates["topics"]), 0)

    def test_no_network_imports_are_added_to_live_dry_run(self) -> None:
        source = (ROOT / "src" / "ai_signal_brief" / "live_dry_run.py").read_text(encoding="utf-8")
        for marker in (
            "import urllib",
            "from urllib",
            "import requests",
            "from requests",
            "import http.client",
            "from http.client",
            "import socket",
            "from socket",
            "import aiohttp",
            "from aiohttp",
            "import httpx",
            "from httpx",
            "urlopen",
            "curl",
            "Invoke-WebRequest",
        ):
            self.assertNotIn(marker, source)

    def test_workflow_remains_manual_only_and_no_live_cli_exists(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        cli_source = (ROOT / "src" / "ai_signal_brief" / "cli.py").read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotRegex(workflow, r"(?m)^\s*schedule\s*:")
        self.assertNotRegex(workflow, r"(?m)^\s*push\s*:")
        self.assertNotRegex(workflow, r"(?m)^\s*pull_request\s*:")
        self.assertNotIn('"discover-topics-live"', cli_source)


def _registry_with(mutator: object) -> str:
    data = json.loads(LIVE_SOURCES.read_text(encoding="utf-8"))
    mutator(data["sources"][0])
    path = OUTPUT_ROOT / "registries" / "topic_sources.live.modified.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path.relative_to(ROOT).as_posix()


def _live_dry_run_args(out_relative: str, *, sources: str | Path = "config/topic_sources.live.example.json") -> list[str]:
    return [
        "discover-topics-live-dry-run",
        "--date",
        "2026-06-24",
        "--sources",
        str(sources),
        "--out",
        out_relative,
        "--artifact-only",
        "--metadata-only",
    ]


def _run_cli(argv: list[str]) -> tuple[int, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = main(argv)
    return exit_code, stdout.getvalue()


if __name__ == "__main__":
    unittest.main()
