import contextlib
import io
import socket
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_signal_brief.cli import main
from ai_signal_brief.topic_validation import validate_topic_sources_path, validate_topics_path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class TopicValidationCliTests(unittest.TestCase):
    def test_valid_topic_source_registry_passes(self) -> None:
        result = validate_topic_sources_path(ROOT / "config" / "topic_sources.example.json")

        self.assertTrue(result.ok, result.errors)

    def test_valid_topic_candidates_pass(self) -> None:
        result = validate_topics_path(ROOT / "examples" / "topic-candidates.example.json")

        self.assertTrue(result.ok, result.errors)

    def test_invalid_topic_source_registry_fails(self) -> None:
        result = validate_topic_sources_path(FIXTURES / "topic-sources.invalid.json")

        self.assertFalse(result.ok)
        joined = "\n".join(result.errors)
        self.assertIn("duplicates category id", joined)
        self.assertIn("duplicates source id", joined)
        self.assertIn("must be public HTTPS", joined)
        self.assertIn("positive integer", joined)

    def test_invalid_topic_candidates_fail(self) -> None:
        result = validate_topics_path(FIXTURES / "topic-candidates.invalid.json")

        self.assertFalse(result.ok)
        joined = "\n".join(result.errors)
        self.assertIn("scan_id", joined)
        self.assertIn("scan_date", joined)
        self.assertIn("topics must be an array", joined)

    def test_secret_like_topic_candidate_fails(self) -> None:
        result = validate_topics_path(FIXTURES / "topic-candidates.secret-like.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("secret-like" in error.lower() or "api key" in error.lower() for error in result.errors))

    def test_private_path_topic_candidate_fails(self) -> None:
        result = validate_topics_path(FIXTURES / "topic-candidates.private-path.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("private" in error.lower() or "local" in error.lower() for error in result.errors))

    def test_duplicate_topic_id_fails(self) -> None:
        result = validate_topics_path(FIXTURES / "topic-candidates.duplicate-topic.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("duplicates topic id" in error for error in result.errors))

    def test_invalid_score_fails(self) -> None:
        result = validate_topics_path(FIXTURES / "topic-candidates.invalid-score.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("importance_score" in error and "0 to 5" in error for error in result.errors))

    def test_unresolved_references_fail(self) -> None:
        result = validate_topics_path(FIXTURES / "topic-candidates.unresolved-reference.json")

        self.assertFalse(result.ok)
        joined = "\n".join(result.errors)
        self.assertIn("unknown source observation", joined)
        self.assertIn("unknown source id", joined)
        self.assertIn("unknown topic id", joined)

    def test_cli_returns_zero_for_valid_topic_files(self) -> None:
        self.assertEqual(_run_cli(["validate-topic-sources", str(ROOT / "config" / "topic_sources.example.json")]), 0)
        self.assertEqual(_run_cli(["validate-topics", str(ROOT / "examples" / "topic-candidates.example.json")]), 0)

    def test_cli_returns_nonzero_for_invalid_topic_files(self) -> None:
        self.assertNotEqual(_run_cli(["validate-topic-sources", str(FIXTURES / "topic-sources.invalid.json")]), 0)
        self.assertNotEqual(_run_cli(["validate-topics", str(FIXTURES / "topic-candidates.invalid.json")]), 0)

    def test_validation_does_not_call_network(self) -> None:
        def fail_network(*args: object, **kwargs: object) -> None:
            raise AssertionError("network call attempted")

        with patch.object(socket, "create_connection", side_effect=fail_network):
            self.assertTrue(validate_topic_sources_path(ROOT / "config" / "topic_sources.example.json").ok)
            self.assertTrue(validate_topics_path(ROOT / "examples" / "topic-candidates.example.json").ok)


def _run_cli(argv: list[str]) -> int:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        return main(argv)


if __name__ == "__main__":
    unittest.main()
