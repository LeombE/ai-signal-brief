import contextlib
import copy
import io
import json
import shutil
import socket
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_signal_brief.cli import main
from ai_signal_brief.topic_ranking import TopicRankingError, rank_topics_from_path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
OUTPUT_ROOT = ROOT / "outputs" / "test-topic-ranking"


class TopicRankingTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(OUTPUT_ROOT, ignore_errors=True)
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, OUTPUT_ROOT, ignore_errors=True)

    def test_rank_topics_passes_on_example(self) -> None:
        result = rank_topics_from_path(ROOT / "examples" / "topic-candidates.example.json")

        self.assertEqual(result.ranked["schema_version"], "1.0.0")
        self.assertGreaterEqual(len(result.topics), 1)
        self.assertEqual(result.ranked["provenance"]["live_fetching"], False)

    def test_ranking_output_is_deterministic(self) -> None:
        path = ROOT / "examples" / "topic-candidates.example.json"
        first = rank_topics_from_path(path).ranked
        second = rank_topics_from_path(path).ranked

        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_higher_score_topic_ranks_above_lower_score_topic(self) -> None:
        path = _write_candidate("higher-score.json", _candidate_with_high_and_low_topics())

        result = rank_topics_from_path(path)

        self.assertEqual(result.topics[0]["topic_id"], "topic-high-score")
        self.assertGreater(result.topics[0]["ranking_score"], result.topics[1]["ranking_score"])

    def test_unresolved_topic_receives_uncertainty_penalty(self) -> None:
        result = rank_topics_from_path(ROOT / "examples" / "topic-candidates.example.json", include_unresolved=True)
        unresolved = next(topic for topic in result.topics if topic["candidate_status"] == "unresolved")

        explanation = unresolved["ranking_explanation"]
        self.assertGreater(explanation["uncertainty_penalty"], 0)
        self.assertGreater(explanation["status_penalty"], 0)

    def test_duplicate_dedup_key_groups_are_detected(self) -> None:
        path = _write_candidate("duplicate-dedup-key.json", _candidate_with_duplicate_dedup_key())

        result = rank_topics_from_path(path, include_unresolved=True)

        duplicate_groups = [entry for entry in result.ranked["dedup_audit"] if entry["dedup_key"] == "shared-dedup-key"]
        self.assertEqual(len(duplicate_groups), 1)
        self.assertEqual(duplicate_groups[0]["action"], "mark_duplicate_or_related_for_review")
        self.assertTrue(any(topic["dedup_status"] == "duplicate_or_related" for topic in result.topics))

    def test_related_topic_ids_are_preserved(self) -> None:
        path = _write_candidate("related-topics.json", _candidate_with_related_topics())

        result = rank_topics_from_path(path, include_unresolved=True)

        high_topic = next(topic for topic in result.topics if topic["topic_id"] == "topic-high-score")
        self.assertEqual(high_topic["related_topic_ids"], ["topic-low-score"])
        self.assertTrue(any(entry["dedup_key"].startswith("related:") for entry in result.ranked["dedup_audit"]))

    def test_top_n_limits_output(self) -> None:
        path = _write_candidate("top-n.json", _candidate_with_high_and_low_topics())
        out_relative = "outputs/test-topic-ranking/ranked-top-one.json"
        out_path = ROOT / out_relative

        exit_code = _run_cli(["rank-topics", str(path), "--top-n", "1", "--out", out_relative])

        self.assertEqual(exit_code, 0)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(data["returned_topics"], 1)
        self.assertEqual(len(data["ranked_topics"]), 1)

    def test_out_writes_only_under_outputs(self) -> None:
        out_relative = "outputs/test-topic-ranking/ranked.json"
        out_path = ROOT / out_relative

        exit_code = _run_cli([
            "rank-topics",
            str(ROOT / "examples" / "topic-candidates.example.json"),
            "--out",
            out_relative,
        ])

        self.assertEqual(exit_code, 0)
        self.assertTrue(out_path.exists())
        self.assertEqual(json.loads(out_path.read_text(encoding="utf-8"))["provenance"]["live_fetching"], False)

    def test_unsafe_out_path_is_rejected(self) -> None:
        exit_code = _run_cli([
            "rank-topics",
            str(ROOT / "examples" / "topic-candidates.example.json"),
            "--out",
            "..\ranked.json",
        ])

        self.assertNotEqual(exit_code, 0)

    def test_invalid_input_fails(self) -> None:
        with self.assertRaises(TopicRankingError):
            rank_topics_from_path(FIXTURES / "topic-candidates.invalid.json")

    def test_secret_private_path_input_fails_through_validation_first(self) -> None:
        self.assertNotEqual(_run_cli(["rank-topics", str(FIXTURES / "topic-candidates.secret-like.json")]), 0)
        self.assertNotEqual(_run_cli(["rank-topics", str(FIXTURES / "topic-candidates.private-path.json")]), 0)

    def test_no_network_call_is_made(self) -> None:
        def fail_network(*args: object, **kwargs: object) -> None:
            raise AssertionError("network call attempted")

        with patch.object(socket, "create_connection", side_effect=fail_network):
            result = rank_topics_from_path(ROOT / "examples" / "topic-candidates.example.json")

        self.assertGreaterEqual(len(result.topics), 1)


def _candidate_with_high_and_low_topics() -> dict[str, object]:
    data = _load_example()
    base = copy.deepcopy(data["topics"][0])
    high = copy.deepcopy(base)
    high.update(
        {
            "topic_id": "topic-high-score",
            "topic_title": "High score resolved candidate",
            "candidate_status": "new",
            "material_update_score": 5,
            "importance_score": 5,
            "novelty_score": 4,
            "source_quality_score": 5,
            "confidence": "high",
            "uncertainty_notes": [],
            "safety_flags": [],
            "dedup_key": "high-score-candidate",
            "related_topic_ids": [],
        }
    )
    low = copy.deepcopy(base)
    low.update(
        {
            "topic_id": "topic-low-score",
            "topic_title": "Low score resolved candidate",
            "candidate_status": "new",
            "material_update_score": 1,
            "importance_score": 1,
            "novelty_score": 1,
            "source_quality_score": 2,
            "confidence": "medium",
            "uncertainty_notes": [],
            "safety_flags": [],
            "dedup_key": "low-score-candidate",
            "related_topic_ids": [],
        }
    )
    data["topics"] = [low, high]
    data["dedup_groups"] = []
    data["unresolved_items"] = []
    return data


def _candidate_with_duplicate_dedup_key() -> dict[str, object]:
    data = _candidate_with_high_and_low_topics()
    data["topics"][0]["dedup_key"] = "shared-dedup-key"
    data["topics"][1]["dedup_key"] = "shared-dedup-key"
    return data


def _candidate_with_related_topics() -> dict[str, object]:
    data = _candidate_with_high_and_low_topics()
    data["topics"][1]["related_topic_ids"] = ["topic-low-score"]
    return data


def _load_example() -> dict[str, object]:
    return json.loads((ROOT / "examples" / "topic-candidates.example.json").read_text(encoding="utf-8"))


def _write_candidate(name: str, data: dict[str, object]) -> Path:
    path = OUTPUT_ROOT / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _run_cli(argv: list[str]) -> int:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        return main(argv)


if __name__ == "__main__":
    unittest.main()
