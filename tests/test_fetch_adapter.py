import builtins
import contextlib
import io
import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_signal_brief.cli import main
from ai_signal_brief.fetch_adapter import FetchAdapterError, load_replay_fixture, replay_fixture_to_observation, render_observation_json


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "fetch_replay"
WORKFLOW = ROOT / ".github" / "workflows" / "topic-scan-preview.yml"
NETWORK_MODULE_NAMES = {"socket", "urllib", "urllib.request", "http.client", "requests", "aiohttp", "httpx"}


class FetchAdapterReplayTests(unittest.TestCase):
    def test_valid_replay_fixture_loads(self) -> None:
        fixture = load_replay_fixture(FIXTURES / "example_official_release.json")

        self.assertEqual(fixture["fixture_schema_version"], "1.0.0")
        self.assertEqual(fixture["fetch_mode"], "replay_fixture")
        self.assertEqual(fixture["source_id"], "openai-news")

    def test_valid_replay_fixture_converts_to_source_observation(self) -> None:
        result = replay_fixture_to_observation(FIXTURES / "example_official_release.json", source_id="openai-news")
        observation = result.observation

        self.assertEqual(observation["source_id"], "openai-news")
        self.assertEqual(observation["adapter_mode"], "replay_fixture")
        self.assertIs(observation["live_fetching"], False)
        self.assertIs(observation["metadata_only"], True)
        self.assertIn("no_live_fetch", observation["safety_flags"])
        self.assertEqual(observation["url"], "https://example.com/ai/announcements/example-release")

    def test_output_is_deterministic(self) -> None:
        first = replay_fixture_to_observation(FIXTURES / "example_official_release.json", source_id="openai-news").observation
        second = replay_fixture_to_observation(FIXTURES / "example_official_release.json", source_id="openai-news").observation

        self.assertEqual(render_observation_json(first), render_observation_json(second))

    def test_invalid_private_path_fixture_fails(self) -> None:
        with self.assertRaises(FetchAdapterError):
            load_replay_fixture(FIXTURES / "invalid_private_path.json")

    def test_invalid_secret_like_fixture_fails(self) -> None:
        with self.assertRaises(FetchAdapterError):
            load_replay_fixture(FIXTURES / "invalid_secret_like.json")

    def test_invalid_raw_html_fixture_fails(self) -> None:
        with self.assertRaises(FetchAdapterError):
            load_replay_fixture(FIXTURES / "invalid_raw_html.json")

    def test_missing_required_fields_fail(self) -> None:
        path = _write_temp_fixture("missing-required", {"fixture_schema_version": "1.0.0"})
        self.addCleanup(shutil.rmtree, path.parent, ignore_errors=True)

        with self.assertRaises(FetchAdapterError):
            load_replay_fixture(path)

    def test_non_https_url_fails(self) -> None:
        path = _write_modified_fixture("non-https", {"url": "http://example.com/ai"})
        self.addCleanup(shutil.rmtree, path.parent, ignore_errors=True)

        with self.assertRaises(FetchAdapterError):
            load_replay_fixture(path)

    def test_fetch_mode_other_than_replay_fixture_fails(self) -> None:
        path = _write_modified_fixture("wrong-fetch-mode", {"fetch_mode": "live_http_page_metadata"})
        self.addCleanup(shutil.rmtree, path.parent, ignore_errors=True)

        with self.assertRaises(FetchAdapterError):
            load_replay_fixture(path)

    def test_source_id_mismatch_fails(self) -> None:
        with self.assertRaises(FetchAdapterError):
            replay_fixture_to_observation(FIXTURES / "example_official_release.json", source_id="different-source")

    def test_no_network_module_import_is_made(self) -> None:
        original_import = builtins.__import__
        blocked: list[str] = []

        def guarded_import(name: str, *args: object, **kwargs: object) -> object:
            if name in NETWORK_MODULE_NAMES or name.split(".", 1)[0] in NETWORK_MODULE_NAMES:
                blocked.append(name)
                raise AssertionError(f"network module import attempted: {name}")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=guarded_import):
            result = replay_fixture_to_observation(FIXTURES / "example_official_release.json", source_id="openai-news")

        self.assertEqual(blocked, [])
        self.assertEqual(result.observation["adapter_mode"], "replay_fixture")

    def test_fetch_adapter_source_does_not_reference_network_modules(self) -> None:
        content = (ROOT / "src" / "ai_signal_brief" / "fetch_adapter.py").read_text(encoding="utf-8")
        forbidden = ("urllib", "requests", "http.client", "socket", "aiohttp", "httpx", "urlopen")

        for marker in forbidden:
            self.assertNotIn(marker, content)

    def test_cli_returns_zero_for_valid_replay_fixture(self) -> None:
        exit_code, stdout = _run_cli(
            [
                "fetch-source-replay",
                "--source-id",
                "openai-news",
                "--fixture",
                str(FIXTURES / "example_official_release.json"),
            ]
        )

        self.assertEqual(exit_code, 0)
        data = json.loads(stdout)
        self.assertEqual(data["source_id"], "openai-news")
        self.assertEqual(data["adapter_mode"], "replay_fixture")

    def test_cli_returns_nonzero_for_invalid_replay_fixture(self) -> None:
        exit_code, stdout = _run_cli(
            [
                "fetch-source-replay",
                "--source-id",
                "openai-news",
                "--fixture",
                str(FIXTURES / "invalid_secret_like.json"),
            ]
        )

        self.assertNotEqual(exit_code, 0)
        self.assertIn("Fetch replay failed", stdout)

    def test_topic_scan_preview_workflow_remains_manual_only(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotRegex(workflow, r"(?m)^\s*schedule\s*:")
        self.assertNotRegex(workflow, r"(?m)^\s*push\s*:")
        self.assertNotRegex(workflow, r"(?m)^\s*pull_request\s*:")


def _run_cli(argv: list[str]) -> tuple[int, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = main(argv)
    return exit_code, stdout.getvalue()


def _write_modified_fixture(name: str, updates: dict[str, object]) -> Path:
    fixture = json.loads((FIXTURES / "example_official_release.json").read_text(encoding="utf-8"))
    fixture.update(updates)
    return _write_temp_fixture(name, fixture)


def _write_temp_fixture(name: str, data: dict[str, object]) -> Path:
    root = ROOT / "outputs" / "test-fetch-adapter" / name
    root.mkdir(parents=True, exist_ok=True)
    path = root / "fixture.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    unittest.main()
