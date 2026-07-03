import json
import re
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NEW_FILES = (
    ROOT / "config" / "topic_sources.example.json",
    ROOT / "schemas" / "topic-candidates.schema.json",
    ROOT / "examples" / "topic-candidates.example.json",
    ROOT / "docs" / "topic-sources-and-candidates.md",
)


class TopicSourcesAndCandidatesTests(unittest.TestCase):
    def test_topic_sources_example_loads(self) -> None:
        data = _load_json(ROOT / "config" / "topic_sources.example.json")
        self.assertEqual(data["schema_version"], "1.0.0")
        self.assertEqual(data["source_policy"], "official_sources_first")
        self.assertIn("official", data["allowed_source_types"])
        self.assertGreaterEqual(len(data["categories"]), 9)
        self.assertTrue(data["sources"])
        self.assertTrue(all("reliability_tier" in source for source in data["sources"]))
        self.assertTrue(all("allowed_fetch_mode" in source for source in data["sources"]))
        self.assertTrue(all("attribution_requirements" in source for source in data["sources"]))
        self.assertTrue(all("safety_notes" in source for source in data["sources"]))

    def test_topic_candidates_schema_loads(self) -> None:
        data = _load_json(ROOT / "schemas" / "topic-candidates.schema.json")
        self.assertEqual(data["title"], "AI Signal Brief Topic Candidates")
        self.assertIn("topics", data["required"])
        self.assertIn("source_observations", data["required"])
        topic_required = data["$defs"]["topic"]["required"]
        self.assertIn("topic_id", topic_required)
        self.assertIn("review_required", topic_required)
        self.assertIn("dedup_key", topic_required)

    def test_topic_candidates_example_loads(self) -> None:
        data = _load_json(ROOT / "examples" / "topic-candidates.example.json")
        self.assertEqual(data["schema_version"], "1.0.0")
        self.assertEqual(data["timezone"], "Asia/Kuala_Lumpur")
        for field in ("topics", "source_observations", "dedup_groups", "unresolved_items", "provenance"):
            self.assertIn(field, data)
        self.assertTrue(data["topics"])
        self.assertTrue(any(topic["candidate_status"] == "quiet_day_note" for topic in data["topics"]))

    def test_topic_candidates_example_required_topic_fields(self) -> None:
        data = _load_json(ROOT / "examples" / "topic-candidates.example.json")
        required = set(_load_json(ROOT / "schemas" / "topic-candidates.schema.json")["$defs"]["topic"]["required"])
        for topic in data["topics"]:
            self.assertTrue(required.issubset(topic.keys()))

    def test_new_files_have_no_forbidden_markers(self) -> None:
        forbidden = (
            "AI" + "\u65e5" + "\u62a5",
            "C:" + "\\" + "Users" + "\\" + "Admin" + "\\" + "OneDrive" + "\\" + "Documents" + "\\" + "AI" + "\u65e5" + "\u62a5",
            "chat" + "_id",
            "github" + "-daily" + "-intelligence",
            "00_MASTER" + "_PROMPT.md",
            "build" + "_report_",
            "send" + "-telegram" + "-report",
        )
        for path in NEW_FILES:
            content = path.read_text(encoding="utf-8")
            for marker in forbidden:
                self.assertNotIn(marker, content, f"{marker!r} found in {path}")
            self.assertIsNone(re.search(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b", content), str(path))
            self.assertIsNone(re.search(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b", content), str(path))
            self.assertIsNone(re.search(r"\b[A-Za-z]:\\", content), str(path))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
