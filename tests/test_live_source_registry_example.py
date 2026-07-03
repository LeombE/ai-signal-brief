import json
import socket
import re
import unittest
from pathlib import Path
from typing import Any

from ai_signal_brief.topic_validation import validate_topic_sources_path
from urllib.parse import urlparse
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
LIVE_REGISTRY = ROOT / "config" / "topic_sources.live.example.json"
WORKFLOW = ROOT / ".github" / "workflows" / "topic-scan-preview.yml"
FIXTURES = ROOT / "tests" / "fixtures"
REQUIRED_LIVE_FIELDS = {
    "source_id",
    "title",
    "publisher",
    "source_type",
    "category_id",
    "priority",
    "reliability_tier",
    "url",
    "enabled",
    "fetch_mode",
    "allowed_fetch_mode",
    "expected_update_frequency",
    "max_requests_per_run",
    "min_seconds_between_requests",
    "timeout_seconds",
    "cache_ttl_minutes",
    "attribution_required",
    "manual_review_required",
    "robots_policy_note",
    "rate_limit_note",
    "safety_notes",
    "disallowed_content_rules",
}
EXPECTED_CATEGORIES = {
    "official_company_announcements",
    "model_card_hubs",
    "research_paper_feeds",
    "public_code_repositories",
    "public_release_changelog_pages",
    "benchmark_evaluation_pages",
    "regulatory_policy_sources",
    "public_security_advisories",
    "credible_technical_news",
}


class LiveSourceRegistryExampleTests(unittest.TestCase):
    def test_live_source_registry_example_loads(self) -> None:
        data = _load_json(LIVE_REGISTRY)

        self.assertEqual(data["schema_version"], "1.0.0")
        self.assertEqual(data["registry_status"], "example_disabled_only")
        self.assertEqual(data["source_policy"], "official_sources_first")
        self.assertTrue(data["categories"])
        self.assertTrue(data["sources"])

    def test_live_source_registry_passes_topic_source_validation(self) -> None:
        result = validate_topic_sources_path(LIVE_REGISTRY)

        self.assertTrue(result.ok, result.errors)

    def test_all_expected_categories_are_represented(self) -> None:
        data = _load_json(LIVE_REGISTRY)
        category_ids = {category["id"] for category in data["categories"]}
        source_category_ids = {source["category_id"] for source in data["sources"]}

        self.assertTrue(EXPECTED_CATEGORIES.issubset(category_ids))
        self.assertTrue(EXPECTED_CATEGORIES.issubset(source_category_ids))

    def test_every_source_is_disabled_and_review_required(self) -> None:
        data = _load_json(LIVE_REGISTRY)

        for source in data["sources"]:
            self.assertIs(source["enabled"], False, source["source_id"])
            self.assertIs(source["manual_review_required"], True, source["source_id"])
            self.assertIs(source["attribution_required"], True, source["source_id"])
            self.assertEqual(source["fetch_mode"], "disabled", source["source_id"])

    def test_required_live_fields_exist(self) -> None:
        data = _load_json(LIVE_REGISTRY)

        for source in data["sources"]:
            self.assertTrue(REQUIRED_LIVE_FIELDS.issubset(source.keys()), source["source_id"])
            self.assertIsInstance(source["disallowed_content_rules"], list, source["source_id"])
            self.assertTrue(source["disallowed_content_rules"], source["source_id"])

    def test_urls_are_public_https_examples(self) -> None:
        data = _load_json(LIVE_REGISTRY)

        for source in data["sources"]:
            parsed = urlparse(source["url"])
            self.assertEqual(parsed.scheme, "https", source["source_id"])
            self.assertTrue(parsed.netloc, source["source_id"])
            self.assertFalse(parsed.username, source["source_id"])
            self.assertFalse(parsed.password, source["source_id"])
            self.assertFalse(parsed.query, source["source_id"])

    def test_live_registry_has_no_forbidden_markers(self) -> None:
        content = LIVE_REGISTRY.read_text(encoding="utf-8")
        forbidden = (
            "AI" + "\u65e5" + "\u62a5",
            "C:" + "\\" + "Users" + "\\" + "Admin" + "\\" + "OneDrive",
            "chat" + "_id",
            "telegram" + "_token",
            "OPENAI" + "_API" + "_KEY",
            "github" + "-daily" + "-intelligence",
            "build" + "_report_",
            "send" + "-telegram" + "-report",
        )
        for marker in forbidden:
            self.assertNotIn(marker, content)
        self.assertIsNone(re.search(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b", content))
        self.assertIsNone(re.search(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b", content))
        self.assertIsNone(re.search(r"\b[A-Za-z]:\\", content))

    def test_invalid_live_enabled_fixture_fails(self) -> None:
        result = validate_topic_sources_path(FIXTURES / "topic_sources_live_enabled_invalid.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("enabled" in error and "false" in error for error in result.errors))

    def test_invalid_private_url_fixture_fails(self) -> None:
        result = validate_topic_sources_path(FIXTURES / "topic_sources_live_private_url_invalid.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("query strings" in error or "private" in error for error in result.errors))

    def test_invalid_secret_like_fixture_fails(self) -> None:
        result = validate_topic_sources_path(FIXTURES / "topic_sources_live_secret_like_invalid.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("secret-like" in error.lower() for error in result.errors))

    def test_invalid_missing_rate_limit_fixture_fails(self) -> None:
        result = validate_topic_sources_path(FIXTURES / "topic_sources_live_missing_rate_limit_invalid.json")

        self.assertFalse(result.ok)
        joined = "\n".join(result.errors)
        self.assertIn("max_requests_per_run", joined)
        self.assertIn("timeout_seconds", joined)

    def test_invalid_missing_manual_review_fixture_fails(self) -> None:
        result = validate_topic_sources_path(FIXTURES / "topic_sources_live_missing_manual_review_invalid.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("manual_review_required" in error for error in result.errors))

    def test_validation_does_not_call_network(self) -> None:
        def fail_network(*args: object, **kwargs: object) -> None:
            raise AssertionError("network call attempted")

        with patch.object(socket, "create_connection", side_effect=fail_network):
            self.assertTrue(validate_topic_sources_path(LIVE_REGISTRY).ok)

    def test_topic_scan_preview_workflow_remains_manual_only(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotRegex(workflow, r"(?m)^\s*schedule\s*:")
        self.assertNotRegex(workflow, r"(?m)^\s*push\s*:")
        self.assertNotRegex(workflow, r"(?m)^\s*pull_request\s*:")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
