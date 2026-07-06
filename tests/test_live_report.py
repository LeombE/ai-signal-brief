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
from ai_signal_brief.live_report import LiveReportError, _no_mojibake, build_daily_ai_report


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

    def test_live_source_config_supports_priority_labels_and_reputable_news(self) -> None:
        config = load_live_sources_config(ROOT / "config" / "live_ai_sources.example.json")

        labels = {source.get("source_priority_label") for source in config["sources"]}
        categories = {source.get("source_category") for source in config["sources"]}
        ids = {source["id"] for source in config["sources"]}

        self.assertIn("official", labels)
        self.assertIn("reputable_news", labels)
        self.assertIn("backup", labels)
        self.assertIn("official_release", categories)
        self.assertIn("ai_news", categories)
        self.assertIn("techcrunch-ai", ids)
        self.assertIn("venturebeat-ai", ids)
        self.assertIn("the-decoder-ai", ids)
        self.assertIn("mit-tech-review-ai", ids)
        self.assertIn("the-verge-ai", ids)

    def test_non_https_source_is_rejected(self) -> None:
        config_path = _write_source_config("non-https", url="http://example.com/feed.xml")

        with self.assertRaises(LiveFetchError):
            load_live_sources_config(config_path)

    def test_source_with_blocked_access_marker_is_rejected(self) -> None:
        config_path = _write_source_config("blocked-marker", extra={"access_note": "paywall"})

        with self.assertRaises(LiveFetchError):
            load_live_sources_config(config_path)

    def test_reputable_news_feed_preserves_priority_and_category(self) -> None:
        config_path = _write_source_config(
            "reputable-news",
            url="https://example.com/news.xml",
            extra={
                "source_type": "news",
                "priority": 3,
                "reliability_tier": "reputable_news",
                "source_confidence": "medium",
                "source_priority_label": "reputable_news",
                "source_category": "ai_news",
                "max_items": 5,
            },
        )

        result = fetch_live_observations(
            sources_path=config_path,
            report_date="2026-07-06",
            timezone_name="Asia/Kuala_Lumpur",
            max_items=5,
            lookback_hours=48,
            reader=_reputable_news_reader,
            retrieved_at="2026-07-06T12:00:00+08:00",
        )

        self.assertEqual(len(result.observations), 2)
        self.assertTrue(all(item["source_priority_label"] == "reputable_news" for item in result.observations))
        self.assertTrue(all(item["source_category"] == "ai_news" for item in result.observations))
        self.assertTrue(all(item["signal_level"] == "article" for item in result.observations))

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


    def test_feed_discovery_prefers_article_entries_over_homepage_metadata(self) -> None:
        config_path = _write_source_config(
            "feed-discovery",
            url="https://example.com/news",
            extra={"fetch_mode": "html_metadata", "max_items": 5},
        )

        result = fetch_live_observations(
            sources_path=config_path,
            report_date="2026-07-05",
            timezone_name="Asia/Kuala_Lumpur",
            max_items=5,
            lookback_hours=72,
            reader=_feed_discovery_reader,
            retrieved_at="2026-07-05T12:00:00+08:00",
        )

        self.assertEqual(len(result.observations), 2)
        self.assertTrue(all(item["signal_level"] == "article" for item in result.observations))
        self.assertNotIn("Example AI News", [item["title"] for item in result.observations])
        self.assertTrue(all(item.get("published_at") for item in result.observations))

    def test_html_article_cards_are_used_when_feed_missing(self) -> None:
        config_path = _write_source_config(
            "article-cards",
            url="https://example.com/news",
            extra={"fetch_mode": "html_metadata", "max_items": 5},
        )

        result = fetch_live_observations(
            sources_path=config_path,
            report_date="2026-07-05",
            timezone_name="Asia/Kuala_Lumpur",
            max_items=5,
            lookback_hours=72,
            reader=_article_cards_reader,
            retrieved_at="2026-07-05T12:00:00+08:00",
        )

        titles = [item["title"] for item in result.observations]
        self.assertIn("Anthropic releases Claude agent tooling for developers", titles)
        self.assertIn("Google updates Gemini API availability for enterprise teams", titles)
        self.assertNotIn("Pricing", titles)
        self.assertTrue(all(item["signal_level"] == "article" for item in result.observations))

    def test_atom_date_parsing_preserves_published_and_updated(self) -> None:
        config_path = _write_source_config("atom-date", url="https://example.com/atom.xml", extra={"fetch_mode": "atom"})

        result = fetch_live_observations(
            sources_path=config_path,
            report_date="2026-07-05",
            timezone_name="Asia/Kuala_Lumpur",
            max_items=5,
            lookback_hours=72,
            reader=_atom_feed_reader,
            retrieved_at="2026-07-05T12:00:00+08:00",
        )

        self.assertEqual(len(result.observations), 1)
        self.assertEqual(result.observations[0]["published_at"], "2026-07-05T05:30:00+00:00")
        self.assertEqual(result.observations[0]["updated_at"], "2026-07-05T06:00:00+00:00")
        self.assertFalse(result.observations[0]["date_missing"])

    def test_html_article_meta_date_parsing(self) -> None:
        config_path = _write_source_config(
            "html-meta-date",
            url="https://example.com/news",
            extra={"fetch_mode": "html_metadata", "max_items": 5},
        )

        result = fetch_live_observations(
            sources_path=config_path,
            report_date="2026-07-05",
            timezone_name="Asia/Kuala_Lumpur",
            max_items=5,
            lookback_hours=72,
            reader=_article_cards_reader,
            retrieved_at="2026-07-05T12:00:00+08:00",
        )

        item = next(item for item in result.observations if "Anthropic" in item["title"])
        self.assertEqual(item["published_at"], "2026-07-05T03:00:00+00:00")
        self.assertEqual(item["updated_at"], "2026-07-05T04:00:00+00:00")
        self.assertFalse(item["date_missing"])

    def test_json_ld_date_parsing(self) -> None:
        config_path = _write_source_config(
            "jsonld-date",
            url="https://example.com/news",
            extra={"fetch_mode": "html_metadata", "max_items": 5},
        )

        result = fetch_live_observations(
            sources_path=config_path,
            report_date="2026-07-05",
            timezone_name="Asia/Kuala_Lumpur",
            max_items=5,
            lookback_hours=72,
            reader=_article_cards_reader,
            retrieved_at="2026-07-05T12:00:00+08:00",
        )

        item = next(item for item in result.observations if "Google" in item["title"])
        self.assertEqual(item["published_at"], "2026-07-05T01:30:00+00:00")
        self.assertEqual(item["updated_at"], "2026-07-05T02:00:00+00:00")
        self.assertFalse(item["date_missing"])

    def test_stale_items_are_excluded_from_ranked_updates_by_default(self) -> None:
        config_path = _write_source_config("stale-default")

        result = build_daily_ai_report(
            report_date="2026-07-05",
            timezone_name="Asia/Kuala_Lumpur",
            output_dir="outputs/test-live-report/stale-default",
            formats="json",
            sources_path=config_path,
            max_items=5,
            lookback_hours=72,
            english_only=True,
            no_openai=True,
            repo_root=ROOT,
            fetch_reader=_stale_feed_reader,
        )

        self.assertEqual(result.report["ranked_updates"], [])
        self.assertEqual(len(result.report["watchlist_updates"]), 1)
        self.assertEqual(result.report["watchlist_updates"][0]["freshness_status"], "stale")
        self.assertFalse(result.report["metadata"]["telegram_ready"])
        self.assertEqual(result.report["metadata"]["stale_items"], 1)
        self.assertIn("Not enough fresh article-level AI updates found", result.report["metadata"]["telegram_readiness_reason"])

    def test_date_missing_items_are_downranked_into_watchlist(self) -> None:
        config_path = _write_source_config(
            "date-missing",
            url="https://example.com/news",
            extra={"fetch_mode": "html_metadata", "max_items": 5},
        )

        result = build_daily_ai_report(
            report_date="2026-07-05",
            timezone_name="Asia/Kuala_Lumpur",
            output_dir="outputs/test-live-report/date-missing",
            formats="json",
            sources_path=config_path,
            max_items=5,
            lookback_hours=72,
            english_only=True,
            no_openai=True,
            repo_root=ROOT,
            fetch_reader=_article_cards_missing_date_reader,
        )

        self.assertEqual(result.report["ranked_updates"], [])
        self.assertGreaterEqual(len(result.report["watchlist_updates"]), 1)
        self.assertTrue(all(item["freshness_status"] == "date_missing" for item in result.report["watchlist_updates"]))
        self.assertTrue(all(item["fresh_enough_for_daily"] is False for item in result.report["watchlist_updates"]))
        self.assertTrue(all(item["importance_score"] <= 2 for item in result.report["watchlist_updates"]))
        self.assertFalse(result.report["metadata"]["telegram_ready"])

    def test_allow_stale_does_not_make_stale_items_main_updates(self) -> None:
        config_path = _write_source_config("stale-allowed")

        result = build_daily_ai_report(
            report_date="2026-07-05",
            timezone_name="Asia/Kuala_Lumpur",
            output_dir="outputs/test-live-report/stale-allowed",
            formats="json",
            sources_path=config_path,
            max_items=5,
            lookback_hours=72,
            allow_stale=True,
            english_only=True,
            no_openai=True,
            repo_root=ROOT,
            fetch_reader=_stale_feed_reader,
        )

        self.assertEqual(result.report["ranked_updates"], [])
        self.assertEqual(len(result.report["watchlist_updates"]), 1)
        self.assertEqual(result.report["watchlist_updates"][0]["freshness_status"], "stale")
        self.assertFalse(result.report["watchlist_updates"][0]["fresh_enough_for_daily"])
        self.assertFalse(result.report["metadata"]["telegram_ready"])

    def test_min_fresh_items_controls_telegram_readiness(self) -> None:
        config_path = _write_source_config("min-fresh")

        not_ready = build_daily_ai_report(
            report_date="2026-07-05",
            timezone_name="Asia/Kuala_Lumpur",
            output_dir="outputs/test-live-report/min-fresh/not-ready",
            formats="json",
            sources_path=config_path,
            max_items=5,
            lookback_hours=72,
            min_fresh_items=3,
            english_only=True,
            no_openai=True,
            repo_root=ROOT,
            fetch_reader=_fixture_reader,
        )
        ready = build_daily_ai_report(
            report_date="2026-07-05",
            timezone_name="Asia/Kuala_Lumpur",
            output_dir="outputs/test-live-report/min-fresh/ready",
            formats="json",
            sources_path=config_path,
            max_items=5,
            lookback_hours=72,
            min_fresh_items=2,
            english_only=True,
            no_openai=True,
            repo_root=ROOT,
            fetch_reader=_fixture_reader,
        )

        self.assertEqual(not_ready.report["metadata"]["fresh_article_level_items"], 2)
        self.assertFalse(not_ready.report["metadata"]["telegram_ready"])
        self.assertTrue(ready.report["metadata"]["telegram_ready"])
        self.assertEqual(ready.report["metadata"]["telegram_readiness_reason"], "ready")

    def test_mojibake_gate_allows_normal_question_marks(self) -> None:
        self.assertTrue(_no_mojibake([{"title": "What if developers use AI safely?"}]))
        self.assertFalse(_no_mojibake([{"title": "Broken replacement marker �"}]))

    def test_mojibake_homepage_fallback_is_repaired_and_low_confidence(self) -> None:
        config_path = _write_source_config(
            "mojibake",
            url="https://example.com/news",
            extra={"fetch_mode": "html_metadata"},
        )

        result = fetch_live_observations(
            sources_path=config_path,
            report_date="2026-07-05",
            timezone_name="Asia/Kuala_Lumpur",
            max_items=5,
            lookback_hours=72,
            reader=_mojibake_reader,
            retrieved_at="2026-07-05T12:00:00+08:00",
        )

        self.assertEqual(len(result.observations), 1)
        item = result.observations[0]
        self.assertEqual(item["signal_level"], "source_homepage_fallback")
        self.assertEqual(item["source_confidence"], "low")
        self.assertNotIn(chr(0x00C3), item["title"])
        self.assertNotIn(chr(0x00E2), item["title"])
        self.assertIn("Google DeepMind", item["title"])

    def test_homepage_fallback_is_downranked_and_limited_coverage_reported(self) -> None:
        config_path = _write_source_config(
            "fallback-report",
            url="https://example.com/news",
            extra={"fetch_mode": "html_metadata"},
        )

        result = build_daily_ai_report(
            report_date="2026-07-05",
            timezone_name="Asia/Kuala_Lumpur",
            output_dir="outputs/test-live-report/fallback-report",
            formats="json",
            sources_path=config_path,
            max_items=5,
            lookback_hours=72,
            english_only=True,
            no_openai=True,
            repo_root=ROOT,
            fetch_reader=_mojibake_reader,
        )

        self.assertEqual(result.report["ranked_updates"], [])
        item = result.report["watchlist_updates"][0]
        self.assertTrue(item["is_homepage_fallback"])
        self.assertEqual(item["freshness_status"], "date_missing")
        self.assertEqual(item["confidence"], "low")
        self.assertLessEqual(item["importance_score"], 2)
        self.assertFalse(result.report["metadata"]["telegram_ready"])
        self.assertIn("Not enough fresh, source-backed, editorially relevant", " ".join(result.report["executive_summary"]))

    def test_duplicate_feed_items_are_deduped_by_url_and_title(self) -> None:
        config_path = _write_source_config("duplicate-feed")

        result = fetch_live_observations(
            sources_path=config_path,
            report_date="2026-07-05",
            timezone_name="Asia/Kuala_Lumpur",
            max_items=5,
            lookback_hours=72,
            reader=_duplicate_feed_reader,
            retrieved_at="2026-07-05T12:00:00+08:00",
        )

        titles = [item["title"] for item in result.observations]
        self.assertEqual(titles.count("OpenAI releases model routing controls for API developers"), 1)
        self.assertIn("Old OpenAI research note outside lookback", titles)

    def test_official_and_tooling_items_rank_above_funding_news(self) -> None:
        config_path = _write_multi_source_config("priority-ranking")

        result = build_daily_ai_report(
            report_date="2026-07-06",
            timezone_name="Asia/Kuala_Lumpur",
            output_dir="outputs/test-live-report/priority-ranking",
            formats="json",
            sources_path=config_path,
            max_items=5,
            lookback_hours=48,
            min_fresh_items=3,
            english_only=True,
            no_openai=True,
            repo_root=ROOT,
            fetch_reader=_priority_reader,
        )

        titles = [item["title"] for item in result.report["ranked_updates"]]
        self.assertEqual(len(titles), 3)
        self.assertTrue(result.report["metadata"]["telegram_ready"])
        self.assertEqual(result.report["metadata"]["editorial_ready_items"], 3)
        self.assertEqual(result.report["ranked_updates"][0]["source_priority_label"], "official")
        self.assertIn("VentureBeat reports Mistral releases new API tooling", titles)
        self.assertTrue(all(item["telegram_editorial_ready"] for item in result.report["ranked_updates"]))
        self.assertTrue(all(item["editorial_relevance_score"] >= 3 for item in result.report["ranked_updates"]))
        downgraded_titles = [item["title"] for item in result.report["downgraded_updates"]]
        self.assertIn("AI infrastructure startup raises Series B funding", downgraded_titles)
        funding_item = next(item for item in result.report["downgraded_updates"] if "funding" in item["title"].lower())
        self.assertEqual(funding_item["topic_type"], "funding")
        self.assertFalse(funding_item["telegram_editorial_ready"])
        self.assertLess(funding_item["editorial_relevance_score"], 3)

    def test_weak_ai_adjacent_fresh_items_do_not_make_telegram_ready(self) -> None:
        config_path = _write_source_config(
            "weak-ai-adjacent",
            url="https://example.com/weak.xml",
            extra={
                "source_type": "news",
                "priority": 3,
                "reliability_tier": "reputable_news",
                "source_confidence": "medium",
                "source_priority_label": "reputable_news",
                "source_category": "ai_news",
                "max_items": 5,
            },
        )

        result = build_daily_ai_report(
            report_date="2026-07-06",
            timezone_name="Asia/Kuala_Lumpur",
            output_dir="outputs/test-live-report/weak-ai-adjacent",
            formats="json",
            sources_path=config_path,
            max_items=5,
            lookback_hours=48,
            min_fresh_items=3,
            english_only=True,
            no_openai=True,
            repo_root=ROOT,
            fetch_reader=_weak_ai_adjacent_reader,
        )

        self.assertEqual(result.report["ranked_updates"], [])
        self.assertEqual(result.report["metadata"]["fresh_article_level_items"], 3)
        self.assertEqual(result.report["metadata"]["editorial_ready_items"], 0)
        self.assertEqual(len(result.report["downgraded_updates"]), 3)
        self.assertFalse(result.report["metadata"]["telegram_ready"])
        self.assertIn("not enough were editorially relevant", result.report["metadata"]["telegram_readiness_reason"])
        self.assertTrue(all(not item["telegram_editorial_ready"] for item in result.report["downgraded_updates"]))

    def test_report_contains_editorial_relevance_fields(self) -> None:
        config_path = _write_multi_source_config("editorial-fields")

        result = build_daily_ai_report(
            report_date="2026-07-06",
            timezone_name="Asia/Kuala_Lumpur",
            output_dir="outputs/test-live-report/editorial-fields",
            formats="json,markdown",
            sources_path=config_path,
            max_items=5,
            lookback_hours=48,
            min_fresh_items=3,
            english_only=True,
            no_openai=True,
            repo_root=ROOT,
            fetch_reader=_priority_reader,
        )

        item = result.report["ranked_updates"][0]
        self.assertIn("editorial_category", item)
        self.assertIn("editorial_relevance_score", item)
        self.assertIn("telegram_editorial_ready", item)
        self.assertIn("editorial_reason", item)
        markdown = (ROOT / "outputs/test-live-report/editorial-fields/report.md").read_text(encoding="utf-8")
        self.assertIn("Top AI Model / Tooling Updates", markdown)
        self.assertIn("Downgraded or Excluded Items", markdown)
        self.assertIn("Telegram-ready means fresh + source-backed + editorially relevant", markdown)

    def test_report_output_must_stay_under_outputs(self) -> None:
        config_path = _write_source_config("unsafe-output")

        with self.assertRaises(LiveReportError):
            build_daily_ai_report(
                report_date="2026-07-05",
                timezone_name="Asia/Kuala_Lumpur",
                output_dir="../unsafe-live-report",
                formats="json",
                sources_path=config_path,
                max_items=5,
                lookback_hours=48,
                english_only=True,
                no_openai=True,
                repo_root=ROOT,
                fetch_reader=_fixture_reader,
            )

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



def _feed_discovery_reader(url: str, timeout_seconds: int) -> bytes:
    if url == "https://example.com/feed.xml":
        return (FIXTURES / "official_feed.xml").read_bytes()
    return (FIXTURES / "source_with_feed.fixture").read_bytes()


def _article_cards_reader(url: str, timeout_seconds: int) -> bytes:
    if url.endswith("/news/2026/07/05/claude-agent-release"):
        return (FIXTURES / "article_page_anthropic_meta.fixture").read_bytes()
    if url.endswith("/blog/2026/07/05/gemini-api-update"):
        return (FIXTURES / "article_page_google_jsonld.fixture").read_bytes()
    return (FIXTURES / "article_cards.fixture").read_bytes()


def _article_cards_missing_date_reader(url: str, timeout_seconds: int) -> bytes:
    if url.endswith("/news/2026/07/05/claude-agent-release") or url.endswith("/blog/2026/07/05/gemini-api-update"):
        return (FIXTURES / "article_page_no_date.fixture").read_bytes()
    return (FIXTURES / "article_cards.fixture").read_bytes()


def _atom_feed_reader(url: str, timeout_seconds: int) -> bytes:
    return (FIXTURES / "atom_feed.xml").read_bytes()


def _stale_feed_reader(url: str, timeout_seconds: int) -> bytes:
    return (FIXTURES / "stale_feed.xml").read_bytes()


def _mojibake_reader(url: str, timeout_seconds: int) -> bytes:
    return (FIXTURES / "homepage_mojibake.fixture").read_bytes()


def _duplicate_feed_reader(url: str, timeout_seconds: int) -> bytes:
    return (FIXTURES / "duplicate_feed.xml").read_bytes()

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
        "source_priority_label": "official",
        "source_category": "official_release",
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



def _write_multi_source_config(name: str) -> Path:
    data = {
        "schema_version": "1.0.0",
        "source_policy": "official_or_high_signal_public_https_only",
        "sources": [
            {
                "id": "fixture-official",
                "name": "Fixture Official Feed",
                "publisher": "OpenAI",
                "url": "https://example.com/official.xml",
                "source_type": "official",
                "priority": 1,
                "reliability_tier": "primary",
                "fetch_mode": "rss",
                "enabled": True,
                "max_items": 3,
                "timeout_seconds": 5,
                "source_confidence": "high",
                "source_priority_label": "official",
                "source_category": "official_release",
                "attribution_required": True,
                "manual_review_required": True,
            },
            {
                "id": "fixture-news",
                "name": "Fixture Reputable News Feed",
                "publisher": "VentureBeat",
                "url": "https://example.com/news.xml",
                "source_type": "news",
                "priority": 3,
                "reliability_tier": "reputable_news",
                "fetch_mode": "rss",
                "enabled": True,
                "max_items": 5,
                "timeout_seconds": 5,
                "source_confidence": "medium",
                "source_priority_label": "reputable_news",
                "source_category": "ai_news",
                "attribution_required": True,
                "manual_review_required": True,
            },
        ],
    }
    path = OUTPUT_ROOT / "configs" / name / "live_ai_sources.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _reputable_news_reader(url: str, timeout_seconds: int) -> bytes:
    return (FIXTURES / "reputable_news_feed.xml").read_bytes()


def _priority_reader(url: str, timeout_seconds: int) -> bytes:
    if url == "https://example.com/official.xml":
        return (FIXTURES / "official_priority_feed.xml").read_bytes()
    if url == "https://example.com/news.xml":
        return (FIXTURES / "reputable_news_feed.xml").read_bytes()
    raise AssertionError(f"unexpected URL: {url}")


def _weak_ai_adjacent_reader(url: str, timeout_seconds: int) -> bytes:
    return b'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Weak AI Adjacent Feed</title>
<item><title>New Google commercial imagines a Declaration of Independence written with help from AI</title><link>https://example.com/news/google-ai-commercial</link><pubDate>Mon, 06 Jul 2026 03:00:00 GMT</pubDate><description>A culture and advertising item about a commercial using generic AI references.</description></item>
<item><title>AI private schools sell wealthy US families on personalized learning</title><link>https://example.com/news/ai-private-schools</link><pubDate>Mon, 06 Jul 2026 02:00:00 GMT</pubDate><description>Education market story about tuition and families, not a model or tooling release.</description></item>
<item><title>Amazon will stop accepting new customers for Mechanical Turk</title><link>https://example.com/news/mechanical-turk</link><pubDate>Mon, 06 Jul 2026 01:00:00 GMT</pubDate><description>Labor platform migration context with no AI model, API, research, or tooling update.</description></item>
</channel></rss>
'''

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