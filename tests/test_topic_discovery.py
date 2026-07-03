import contextlib
import io
import json
import shutil
import socket
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_signal_brief.cli import main
from ai_signal_brief.topic_discovery import TopicDiscoveryError, discover_topics_from_mock
from ai_signal_brief.topic_ranking import rank_topics_from_path
from ai_signal_brief.topic_validation import validate_topics_path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
OUTPUT_ROOT = ROOT / "outputs" / "test-topic-discovery"


class TopicDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(OUTPUT_ROOT, ignore_errors=True)
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, OUTPUT_ROOT, ignore_errors=True)

    def test_discover_topics_succeeds_with_valid_mock_observations(self) -> None:
        out_relative = "outputs/test-topic-discovery/valid.json"
        exit_code = _run_cli(_discover_args(out_relative))

        self.assertEqual(exit_code, 0)
        output_path = ROOT / out_relative
        self.assertTrue(output_path.exists())
        data = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(data["scan_date"], "2026-06-24")
        self.assertEqual(len(data["topics"]), 2)
        self.assertEqual(data["provenance"]["live_fetching"], False)

    def test_generated_topic_candidate_json_passes_validate_topics(self) -> None:
        out_relative = "outputs/test-topic-discovery/validates.json"
        self.assertEqual(_run_cli(_discover_args(out_relative)), 0)

        result = validate_topics_path(ROOT / out_relative)

        self.assertTrue(result.ok, result.errors)

    def test_rank_produces_deterministic_result(self) -> None:
        first_relative = "outputs/test-topic-discovery/ranked-first.json"
        second_relative = "outputs/test-topic-discovery/ranked-second.json"
        self.assertEqual(_run_cli(_discover_args(first_relative, rank=True)), 0)
        self.assertEqual(_run_cli(_discover_args(second_relative, rank=True)), 0)

        first_ranked = rank_topics_from_path(ROOT / first_relative).ranked
        second_ranked = rank_topics_from_path(ROOT / second_relative).ranked

        self.assertEqual(json.dumps(first_ranked, sort_keys=True), json.dumps(second_ranked, sort_keys=True))

    def test_quiet_day_observations_are_accepted_when_quiet_ok_is_used(self) -> None:
        out_relative = "outputs/test-topic-discovery/quiet-day.json"
        exit_code = _run_cli(
            _discover_args(
                out_relative,
                observations="tests/fixtures/topic_observations.quiet_day.json",
                quiet_ok=True,
            )
        )

        self.assertEqual(exit_code, 0)
        data = json.loads((ROOT / out_relative).read_text(encoding="utf-8"))
        self.assertEqual(data["topics"][0]["candidate_status"], "quiet_day_note")
        self.assertTrue(validate_topics_path(ROOT / out_relative).ok)

    def test_quiet_day_observations_fail_without_quiet_ok(self) -> None:
        exit_code = _run_cli(
            _discover_args(
                "outputs/test-topic-discovery/quiet-day-fail.json",
                observations="tests/fixtures/topic_observations.quiet_day.json",
            )
        )

        self.assertNotEqual(exit_code, 0)

    def test_invalid_observations_fail(self) -> None:
        exit_code = _run_cli(
            _discover_args(
                "outputs/test-topic-discovery/invalid.json",
                observations="tests/fixtures/topic_observations.invalid.json",
            )
        )

        self.assertNotEqual(exit_code, 0)

    def test_private_path_observations_fail(self) -> None:
        exit_code = _run_cli(
            _discover_args(
                "outputs/test-topic-discovery/private-path.json",
                observations="tests/fixtures/topic_observations.private_path.json",
            )
        )

        self.assertNotEqual(exit_code, 0)

    def test_secret_like_observations_fail(self) -> None:
        exit_code = _run_cli(
            _discover_args(
                "outputs/test-topic-discovery/secret-like.json",
                observations="tests/fixtures/topic_observations.secret_like.json",
            )
        )

        self.assertNotEqual(exit_code, 0)

    def test_unsafe_out_path_is_rejected(self) -> None:
        exit_code = _run_cli(_discover_args("../topic-candidates.json"))

        self.assertNotEqual(exit_code, 0)

    def test_output_is_written_only_under_outputs(self) -> None:
        out_relative = "outputs/test-topic-discovery/safe-output.json"
        result = discover_topics_from_mock(
            scan_date="2026-06-24",
            sources_path=ROOT / "config" / "topic_sources.example.json",
            mock_observations_path=FIXTURES / "topic_observations.valid.json",
            output_path=out_relative,
            repo_root=ROOT,
        )

        self.assertTrue(result.output_path.exists())
        self.assertTrue(result.output_path.resolve().is_relative_to((ROOT / "outputs").resolve()))

    def test_direct_unsafe_out_path_is_rejected(self) -> None:
        with self.assertRaises(TopicDiscoveryError):
            discover_topics_from_mock(
                scan_date="2026-06-24",
                sources_path=ROOT / "config" / "topic_sources.example.json",
                mock_observations_path=FIXTURES / "topic_observations.valid.json",
                output_path="outside-topic-candidates.json",
                repo_root=ROOT,
            )

    def test_no_network_call_is_made(self) -> None:
        def fail_network(*args: object, **kwargs: object) -> None:
            raise AssertionError("network call attempted")

        with patch.object(socket, "create_connection", side_effect=fail_network):
            result = discover_topics_from_mock(
                scan_date="2026-06-24",
                sources_path=ROOT / "config" / "topic_sources.example.json",
                mock_observations_path=FIXTURES / "topic_observations.valid.json",
                output_path="outputs/test-topic-discovery/no-network.json",
                repo_root=ROOT,
                rank=True,
            )

        self.assertIsNotNone(result.ranked_summary)


def _discover_args(
    out_relative: str,
    *,
    observations: str = "tests/fixtures/topic_observations.valid.json",
    rank: bool = False,
    quiet_ok: bool = False,
) -> list[str]:
    args = [
        "discover-topics",
        "--date",
        "2026-06-24",
        "--sources",
        "config/topic_sources.example.json",
        "--mock-observations",
        observations,
        "--out",
        out_relative,
    ]
    if rank:
        args.append("--rank")
    if quiet_ok:
        args.append("--quiet-ok")
    return args


def _run_cli(argv: list[str]) -> int:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        return main(argv)


if __name__ == "__main__":
    unittest.main()
