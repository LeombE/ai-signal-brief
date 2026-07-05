import contextlib
import io
import json
import shutil
import socket
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from ai_signal_brief.cli import main
from ai_signal_brief.live_fetch import LiveFetchError, fetch_live_observations, load_live_sources_config
from ai_signal_brief.live_report import LiveReportError, build_daily_ai_report


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "outputs" / "test-live-report"
FIXTURES = ROOT / "tests" / "fixtures" / "live_sources"
WORKFLOW = ROOT / ".github" / "workflows" / "topic-scan-preview.yml"


class LiveReportTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(OUTPUT_ROOT, ignore_errors=True)
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, OUTPUT_ROOT, ignore_errors=True)

    def test_live_source_config_loads(self) -> None:
        config = load_live_sources_config(ROOT / "config" / "live_ai_sources.example.json")

        self.assertGreaterEqual(len(config["sources"]), 5)
        self.assertTrue(all(source["url"].startswith("https://") for source in config["sources"]))

    def test_non_https_source_is_rejected(self) -> None:
        config_path = _write_source_config("non-https", url="http://example.com/feed.xml")

        with self.assertRaises(LiveFetchError):
            load_live_sources_config(config_path)

    def test_source_with_blocked_access_marker_is_rejected(self) -> None:
        config_path = _write_source_config("blocked-marker", extra={"access_note": "paywall"})

        with self.assertRaises(LiveFetchError):
            load_live_sources_config(config_path)

    def test_fetcher_parses_fixture_observations(self) -> None:
        config_path = _write_source_config("parse")
        result = fetch_live_observations(
            sources_path=config_path,
            report_date="2026-07-05",
            timezone_name="Asia/Kuala_Lumpur",
            max_items=5,
            lookback_hours=48,
            reader=_fixture_reader,
            retrieved_at="2026-07-05T12:00:00+08:00",
        )

        self.assertEqual(len(result.observations), 2)
        first = result.observations[0]
        self.assertEqual(first["source_id"], "fixture-openai")
        self.assertEqual(first["source_name"], "Fixture OpenAI Feed")
        self.assertEqual(first["source_type"], "official")
        self.assertIn("OpenAI", first["company_entities"])
        self.assertEqual(first["source_confidence"], "high")
        self.assertRegex(first["content_hash"], r"^[a-f0-9]{64}$")

    def test_daily_brief_writes_json_markdown_and_docx(self) -> None:
        config_path = _write_source_config("write-report")
        result = build_daily_ai_report(
            report_date="2026-07-05",
            timezone_name="Asia/Kuala_Lumpur",
            output_dir="outputs/test-live-report/write-report",
            formats="markdown,json,docx",
            sources_path=config_path,
            max_items=5,
            lookback_hours=48,
            english_only=True,
            no_openai=True,
            repo_root=ROOT,
            fetch_reader=_fixture_reader,
        )

        self.assertFalse(result.telegram_sent)
        self.assertFalse(result.openai_used)
        self.assertIn("json", result.written_paths)
        self.assertIn("markdown", result.written_paths)
        self.assertIn("docx", result.written_paths)
        self.assertTrue(Path(result.written_paths["json"]).exists())
        self.assertTrue(Path(result.written_paths["markdown"]).exists())
        self.assertTrue(Path(result.written_paths["docx"]).exists())
        report = json.loads(Path(result.written_paths["json"]).read_text(encoding="utf-8"))
        self.assertEqual(report["title"], "AI Daily Brief - Global and Major Model Updates")
        self.assertGreater(len(report["ranked_updates"]), 0)

    def test_cli_build_daily_ai_report_uses_mocked_public_fetch(self) -> None:
        config_path = _write_source_config("cli")
        out_dir = "outputs/test-live-report/cli-report"
        with patch("ai_signal_brief.live_fetch._read_url", side_effect=_fixture_reader):
            exit_code, stdout = _run_cli(
                [
                    "build-daily-ai-report",
                    "--date",
                    "2026-07-05",
                    "--timezone",
                    "Asia/Kuala_Lumpur",
                    "--out",
                    out_dir,
                    "--format",
                    "markdown,json,docx",
                    "--sources",
                    str(config_path.relative_to(ROOT)),
                    "--english-only",
                    "--no-openai",
                ]
            )

        self.assertEqual(exit_code, 0, stdout)
        self.assertIn("Live AI daily report PASS", stdout)
        self.assertTrue((ROOT / out_dir / "report.json").exists())
        self.assertTrue((ROOT / out_dir / "report.md").exists())
        self.assertTrue((ROOT / out_dir / "report.docx").exists())

    def test_ranking_is_deterministic(self) -> None:
        config_path = _write_source_config("deterministic")
        kwargs = {
            "report_date": "2026-07-05",
            "timezone_name": "Asia/Kuala_Lumpur",
            "formats": "json",
            "sources_path": config_path,
            "max_items": 5,
            "lookback_hours": 48,
            "english_only": True,
            "no_openai": True,
            "repo_root": ROOT,
            "fetch_reader": _fixture_reader,
        }

        first = build_daily_ai_report(output_dir="outputs/test-live-report/deterministic/first", **kwargs).report
        second = build_daily_ai_report(output_dir="outputs/test-live-report/deterministic/second", **kwargs).report

        self.assertEqual(
            [item["topic_id"] for item in first["ranked_updates"]],
            [item["topic_id"] for item in second["ranked_updates"]],
        )

    def test_telegram_not_called_without_explicit_flag(self) -> None:
        sender = Mock()
        config_path = _write_source_config("no-telegram")

        result = build_daily_ai_report(
            report_date="2026-07-05",
            timezone_name="Asia/Kuala_Lumpur",
            output_dir="outputs/test-live-report/no-telegram",
            formats="json",
            sources_path=config_path,
            repo_root=ROOT,
            fetch_reader=_fixture_reader,
            telegram_sender=sender,
        )

        self.assertFalse(result.telegram_sent)
        sender.assert_not_called()

    def test_telegram_requires_explicit_flag_and_values(self) -> None:
        config_path = _write_source_config("telegram-missing")

        with self.assertRaises(LiveReportError):
            build_daily_ai_report(
                report_date="2026-07-05",
                timezone_name="Asia/Kuala_Lumpur",
                output_dir="outputs/test-live-report/telegram-missing",
                formats="json",
                sources_path=config_path,
                repo_root=ROOT,
                fetch_reader=_fixture_reader,
                send_telegram=True,
            )

    def test_openai_not_called_by_default_and_explicit_option_fails_closed(self) -> None:
        config_path = _write_source_config("openai-default")
        result = build_daily_ai_report(
            report_date="2026-07-05",
            timezone_name="Asia/Kuala_Lumpur",
            output_dir="outputs/test-live-report/openai-default",
            formats="json",
            sources_path=config_path,
            repo_root=ROOT,
            fetch_reader=_fixture_reader,
        )
        self.assertFalse(result.openai_used)

        with self.assertRaises(LiveReportError):
            build_daily_ai_report(
                report_date="2026-07-05",
                timezone_name="Asia/Kuala_Lumpur",
                output_dir="outputs/test-live-report/openai-explicit",
                formats="json",
                sources_path=config_path,
                repo_root=ROOT,
                fetch_reader=_fixture_reader,
                no_openai=False,
                openai_summary=True,
            )

    def test_dry_run_and_replay_modules_remain_no_network(self) -> None:
        allowed = {"src/ai_signal_brief/live_fetch.py", "src/ai_signal_brief/live_report.py"}
        forbidden_markers = ("import urllib", "from urllib", "import requests", "from requests", "import http.client", "from http.client", "import aiohttp", "from aiohttp", "import httpx", "from httpx", "urlopen")
        offenders = []
        for path in (ROOT / "src" / "ai_signal_brief").glob("*.py"):
            relative = path.relative_to(ROOT).as_posix()
            if relative in allowed:
                continue
            content = path.read_text(encoding="utf-8")
            for marker in forbidden_markers:
                if marker in content:
                    offenders.append(f"{relative}:{marker}")
        self.assertEqual(offenders, [])

    def test_dry_run_command_still_makes_no_network_call(self) -> None:
        def fail_network(*args: object, **kwargs: object) -> None:
            raise AssertionError("network call attempted")

        with patch.object(socket, "create_connection", side_effect=fail_network):
            exit_code, stdout = _run_cli(
                [
                    "discover-topics-live-dry-run",
                    "--date",
                    "2026-06-24",
                    "--sources",
                    "config/topic_sources.live.example.json",
                    "--out",
                    "outputs/test-live-report/no-network/topics.json",
                    "--artifact-only",
                    "--metadata-only",
                ]
            )
        self.assertEqual(exit_code, 0, stdout)

    def test_workflow_is_not_modified_for_live_report(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotRegex(workflow, r"(?m)^\s*schedule\s*:")
        self.assertNotRegex(workflow, r"(?m)^\s*push\s*:")
        self.assertNotRegex(workflow, r"(?m)^\s*pull_request\s*:")


def _write_source_config(name: str, *, url: str = "https://example.com/openai.xml", extra: dict[str, object] | None = None) -> Path:
    source = {
        "id": "fixture-openai",
        "name": "Fixture OpenAI Feed",
        "publisher": "OpenAI",
        "url": url,
        "source_type": "official",
        "priority": 1,
        "reliability_tier": "primary",
        "fetch_mode": "rss",
        "enabled": True,
        "max_items": 3,
        "timeout_seconds": 5,
        "source_confidence": "high",
        "attribution_required": True,
        "manual_review_required": True,
    }
    if extra:
        source.update(extra)
    data = {
        "schema_version": "1.0.0",
        "source_policy": "official_or_high_signal_public_https_only",
        "sources": [source],
    }
    path = OUTPUT_ROOT / "configs" / name / "live_ai_sources.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _fixture_reader(url: str, timeout_seconds: int) -> bytes:
    self_check = (url, timeout_seconds)
    if not self_check[0].startswith("https://"):
        raise AssertionError("non-HTTPS URL reached reader")
    return (FIXTURES / "official_feed.xml").read_bytes()


def _run_cli(argv: list[str]) -> tuple[int, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = main(argv)
    return exit_code, stdout.getvalue() + stderr.getvalue()


if __name__ == "__main__":
    unittest.main()