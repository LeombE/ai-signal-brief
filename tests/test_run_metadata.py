import json
import tempfile
import unittest
from pathlib import Path

from ai_signal_brief.cli import main
from ai_signal_brief.run_metadata import RunMetadataError, create_run_record, write_run_record
from ai_signal_brief.validation import find_secret_like_values, validate_run_path


ROOT = Path(__file__).resolve().parents[1]
REPORT_EXAMPLE = ROOT / "examples" / "report.example.json"
INVALID_REPORT = ROOT / "tests" / "fixtures" / "report.invalid.json"
STARTED_AT = "2026-06-24T04:00:00+08:00"
ENDED_AT = "2026-06-24T04:01:00+08:00"
TIMEZONE = "Asia/Kuala_Lumpur"


class RunMetadataTests(unittest.TestCase):
    def test_successful_run_record_generation(self) -> None:
        record = create_run_record(
            REPORT_EXAMPLE,
            ["markdown=outputs/report.example.md"],
            started_at=STARTED_AT,
            ended_at=ENDED_AT,
            timezone_name=TIMEZONE,
        )

        self.assertEqual(record["schema_version"], "1.0.0")
        self.assertEqual(record["report_id"], "2026-06-24")
        self.assertEqual(record["report_date"], "2026-06-24")
        self.assertFalse(record["delivery"]["telegram"]["enabled"])
        self.assertEqual(record["delivery"]["telegram"]["status"], "skipped")

    def test_generated_run_record_validates(self) -> None:
        record = create_run_record(
            REPORT_EXAMPLE,
            ["markdown=outputs/report.example.md"],
            started_at=STARTED_AT,
            ended_at=ENDED_AT,
            timezone_name=TIMEZONE,
        )
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "run.generated.json"
            write_run_record(record, output_path)
            result = validate_run_path(output_path)

        self.assertEqual(result.errors, ())

    def test_artifact_paths_are_recorded_safely(self) -> None:
        record = create_run_record(
            REPORT_EXAMPLE,
            [
                "markdown=outputs\\report.example.md",
                "telegram_preview=outputs/telegram.example.txt",
            ],
            started_at=STARTED_AT,
            ended_at=ENDED_AT,
            timezone_name=TIMEZONE,
        )

        artifacts = record["artifacts"]
        self.assertEqual(artifacts[0], {"kind": "markdown", "path": "outputs/report.example.md"})
        self.assertEqual(artifacts[1], {"kind": "telegram_preview", "path": "outputs/telegram.example.txt"})
        for artifact in artifacts:
            path = artifact["path"]
            self.assertFalse(Path(path).is_absolute())
            self.assertNotIn("..", Path(path).parts)
            self.assertNotIn(":", path)

    def test_invalid_report_input_is_rejected(self) -> None:
        with self.assertRaises(RunMetadataError):
            create_run_record(
                INVALID_REPORT,
                started_at=STARTED_AT,
                ended_at=ENDED_AT,
                timezone_name=TIMEZONE,
            )

        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "run.generated.json"
            code = main(
                [
                    "create-run-record",
                    "--report",
                    str(INVALID_REPORT),
                    "--out",
                    str(output_path),
                    "--started-at",
                    STARTED_AT,
                    "--ended-at",
                    ENDED_AT,
                    "--timezone",
                    TIMEZONE,
                ]
            )
            self.assertEqual(code, 1)
            self.assertFalse(output_path.exists())

    def test_generated_run_metadata_has_no_secret_like_values(self) -> None:
        record = create_run_record(
            REPORT_EXAMPLE,
            ["markdown=outputs/report.example.md"],
            started_at=STARTED_AT,
            ended_at=ENDED_AT,
            timezone_name=TIMEZONE,
        )
        serialized = json.dumps(record, ensure_ascii=False)

        self.assertEqual(find_secret_like_values(record), [])
        self.assertNotIn("chat_id", serialized.lower())
        self.assertNotIn("telegram_bot_token", serialized.lower())
        self.assertNotIn("openai_api_key", serialized.lower())

    def test_deterministic_timestamp_behavior(self) -> None:
        first = create_run_record(
            REPORT_EXAMPLE,
            started_at=STARTED_AT,
            ended_at=ENDED_AT,
            timezone_name=TIMEZONE,
        )
        second = create_run_record(
            REPORT_EXAMPLE,
            started_at=STARTED_AT,
            ended_at=ENDED_AT,
            timezone_name=TIMEZONE,
        )

        self.assertEqual(first["run_id"], "2026-06-24T04-00-00+08-00")
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertEqual(first["started_at"], STARTED_AT)
        self.assertEqual(first["ended_at"], ENDED_AT)


if __name__ == "__main__":
    unittest.main()