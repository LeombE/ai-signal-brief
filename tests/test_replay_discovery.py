import contextlib
import io
import json
import shutil
import socket
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_signal_brief.cli import main
from ai_signal_brief.replay_discovery import ReplayDiscoveryError, discover_topics_from_replay
from ai_signal_brief.topic_ranking import rank_topics_from_path
from ai_signal_brief.topic_validation import validate_topics_path


ROOT = Path(__file__).resolve().parents[1]
REPLAY_FIXTURES = ROOT / "tests" / "fixtures" / "fetch_replay"
OUTPUT_ROOT = ROOT / "outputs" / "test-replay-discovery"
WORKFLOW = ROOT / ".github" / "workflows" / "topic-scan-preview.yml"


class ReplayDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(OUTPUT_ROOT, ignore_errors=True)
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, OUTPUT_ROOT, ignore_errors=True)

    def test_cli_generates_valid_topic_candidates_from_replay(self) -> None:
        replay_dir = _valid_replay_dir("cli-valid")
        out_relative = "outputs/test-replay-discovery/cli-valid/topics.json"

        exit_code, stdout = _run_cli(_replay_args(replay_dir, out_relative, rank=True))

        self.assertEqual(exit_code, 0, stdout)
        self.assertIn("Topic discovery PASS", stdout)
        output_path = ROOT / out_relative
        data = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(data["provenance"]["generation_mode"], "replay_fixture_observations_only")
        self.assertIs(data["provenance"]["live_fetching"], False)
        self.assertEqual(len(data["topics"]), 1)
        self.assertEqual(data["topics"][0]["candidate_status"], "unresolved")
        self.assertTrue(data["topics"][0]["review_required"])
        self.assertEqual(validate_topics_path(output_path).ok, True)

    def test_replay_source_observation_fields_are_preserved(self) -> None:
        replay_dir = _valid_replay_dir("preserve-fields")
        out_relative = "outputs/test-replay-discovery/preserve/topics.json"
        self.assertEqual(_run_cli(_replay_args(replay_dir, out_relative))[0], 0)

        data = json.loads((ROOT / out_relative).read_text(encoding="utf-8"))
        observation = data["source_observations"][0]

        self.assertEqual(observation["source_id"], "example-model-card-hub")
        self.assertEqual(observation["url"], "https://example.com/models/example-model-card")
        self.assertEqual(observation["observed_at"], "2026-06-24T04:05:00+08:00")
        self.assertEqual(observation["published_at"], "2026-06-23T12:00:00+00:00")
        self.assertEqual(observation["retrieved_at"], "2026-06-24T04:05:10+08:00")
        self.assertEqual(observation["source_type"], "repository")
        self.assertEqual(observation["raw_signal_type"], "model_card")
        self.assertEqual(observation["content_hash"], "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
        self.assertEqual(observation["source_confidence"], "medium")

    def test_topic_ids_and_dedup_keys_are_deterministic(self) -> None:
        replay_dir = _valid_replay_dir("deterministic")
        first = "outputs/test-replay-discovery/deterministic/first.json"
        second = "outputs/test-replay-discovery/deterministic/second.json"
        self.assertEqual(_run_cli(_replay_args(replay_dir, first))[0], 0)
        self.assertEqual(_run_cli(_replay_args(replay_dir, second))[0], 0)

        first_data = json.loads((ROOT / first).read_text(encoding="utf-8"))
        second_data = json.loads((ROOT / second).read_text(encoding="utf-8"))

        self.assertEqual(first_data["topics"][0]["topic_id"], second_data["topics"][0]["topic_id"])
        self.assertEqual(first_data["topics"][0]["dedup_key"], second_data["topics"][0]["dedup_key"])

    def test_rank_integration_works(self) -> None:
        replay_dir = _valid_replay_dir("rank")
        out_relative = "outputs/test-replay-discovery/rank/topics.json"
        result = discover_topics_from_replay(
            scan_date="2026-06-24",
            sources_path=ROOT / "config" / "topic_sources.live.example.json",
            replay_dir=replay_dir,
            output_path=out_relative,
            repo_root=ROOT,
            rank=True,
        )

        self.assertIsNotNone(result.ranked_summary)
        ranked = rank_topics_from_path(ROOT / out_relative).ranked
        self.assertEqual(len(ranked["ranked_topics"]), 1)

    def test_directory_with_intentional_invalid_fixtures_fails(self) -> None:
        exit_code, stdout = _run_cli(_replay_args(REPLAY_FIXTURES, "outputs/test-replay-discovery/full-dir/topics.json"))

        self.assertNotEqual(exit_code, 0)
        self.assertIn("Replay topic discovery failed", stdout)

    def test_private_path_fixture_fails(self) -> None:
        replay_dir = _single_fixture_dir("private-path", "invalid_private_path.json")
        exit_code, _stdout = _run_cli(_replay_args(replay_dir, "outputs/test-replay-discovery/private/topics.json"))

        self.assertNotEqual(exit_code, 0)

    def test_secret_like_fixture_fails(self) -> None:
        replay_dir = _single_fixture_dir("secret-like", "invalid_secret_like.json")
        exit_code, _stdout = _run_cli(_replay_args(replay_dir, "outputs/test-replay-discovery/secret/topics.json"))

        self.assertNotEqual(exit_code, 0)

    def test_raw_html_fixture_fails(self) -> None:
        replay_dir = _single_fixture_dir("raw-html", "invalid_raw_html.json")
        exit_code, _stdout = _run_cli(_replay_args(replay_dir, "outputs/test-replay-discovery/raw/topics.json"))

        self.assertNotEqual(exit_code, 0)

    def test_unknown_source_id_fails(self) -> None:
        replay_dir = _single_fixture_dir("unknown-source", "example_official_release.json")
        exit_code, stdout = _run_cli(_replay_args(replay_dir, "outputs/test-replay-discovery/unknown/topics.json"))

        self.assertNotEqual(exit_code, 0)
        self.assertIn("unknown topic source", stdout)

    def test_duplicate_observation_id_fails(self) -> None:
        replay_dir = OUTPUT_ROOT / "replay" / "duplicate"
        replay_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPLAY_FIXTURES / "example_model_card.json", replay_dir / "a.json")
        shutil.copy2(REPLAY_FIXTURES / "example_model_card.json", replay_dir / "b.json")

        exit_code, stdout = _run_cli(_replay_args(replay_dir, "outputs/test-replay-discovery/duplicate/topics.json"))

        self.assertNotEqual(exit_code, 0)
        self.assertIn("duplicates observation id", stdout)

    def test_unsafe_output_path_is_rejected(self) -> None:
        replay_dir = _valid_replay_dir("unsafe-output")

        with self.assertRaises(ReplayDiscoveryError):
            discover_topics_from_replay(
                scan_date="2026-06-24",
                sources_path=ROOT / "config" / "topic_sources.live.example.json",
                replay_dir=replay_dir,
                output_path="../topic-candidates.json",
                repo_root=ROOT,
            )

    def test_no_network_call_is_made(self) -> None:
        replay_dir = _valid_replay_dir("no-network")

        def fail_network(*args: object, **kwargs: object) -> None:
            raise AssertionError("network call attempted")

        with patch.object(socket, "create_connection", side_effect=fail_network):
            result = discover_topics_from_replay(
                scan_date="2026-06-24",
                sources_path=ROOT / "config" / "topic_sources.live.example.json",
                replay_dir=replay_dir,
                output_path="outputs/test-replay-discovery/no-network/topics.json",
                repo_root=ROOT,
            )

        self.assertEqual(len(result.candidates["topics"]), 1)

    def test_workflow_remains_manual_only_and_no_live_cli_exists(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        cli_source = (ROOT / "src" / "ai_signal_brief" / "cli.py").read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotRegex(workflow, r"(?m)^\s*schedule\s*:")
        self.assertNotRegex(workflow, r"(?m)^\s*push\s*:")
        self.assertNotRegex(workflow, r"(?m)^\s*pull_request\s*:")
        self.assertNotIn('"discover-topics-live"', cli_source)


def _valid_replay_dir(name: str) -> Path:
    return _single_fixture_dir(name, "example_model_card.json")


def _single_fixture_dir(name: str, fixture_name: str) -> Path:
    replay_dir = OUTPUT_ROOT / "replay" / name
    replay_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPLAY_FIXTURES / fixture_name, replay_dir / fixture_name)
    return replay_dir


def _replay_args(replay_dir: Path, out_relative: str, *, rank: bool = False) -> list[str]:
    args = [
        "discover-topics-from-replay",
        "--date",
        "2026-06-24",
        "--sources",
        "config/topic_sources.live.example.json",
        "--replay-dir",
        str(replay_dir.relative_to(ROOT)),
        "--out",
        out_relative,
    ]
    if rank:
        args.append("--rank")
    return args


def _run_cli(argv: list[str]) -> tuple[int, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = main(argv)
    return exit_code, stdout.getvalue()


if __name__ == "__main__":
    unittest.main()