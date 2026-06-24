import unittest
from pathlib import Path

from ai_signal_brief.cli import main
from ai_signal_brief.validation import validate_report_path, validate_run_path


ROOT = Path(__file__).resolve().parents[1]


class ValidationCliTests(unittest.TestCase):
    def test_valid_report_passes(self) -> None:
        result = validate_report_path(ROOT / "examples" / "report.example.json")
        self.assertEqual(result.errors, ())
        self.assertEqual(main(["validate-report", str(ROOT / "examples" / "report.example.json")]), 0)

    def test_valid_run_passes(self) -> None:
        result = validate_run_path(ROOT / "examples" / "run.example.json")
        self.assertEqual(result.errors, ())
        self.assertEqual(main(["validate-run", str(ROOT / "examples" / "run.example.json")]), 0)

    def test_report_missing_required_fails(self) -> None:
        result = validate_report_path(ROOT / "tests" / "fixtures" / "report.missing-required.json")
        self.assertTrue(any("$.stories is required" in error for error in result.errors))
        self.assertEqual(main(["validate-report", str(ROOT / "tests" / "fixtures" / "report.missing-required.json")]), 1)

    def test_invalid_report_fails_with_references_duplicates_timestamps_and_secret_marker(self) -> None:
        result = validate_report_path(ROOT / "tests" / "fixtures" / "report.invalid.json")
        joined = "\n".join(result.errors)
        self.assertIn("$.language must be 'en'", joined)
        self.assertIn("duplicates source id", joined)
        self.assertIn("duplicates story id", joined)
        self.assertIn("duplicates claim id", joined)
        self.assertIn("references unknown source id", joined)
        self.assertIn("must be ISO-8601 with timezone", joined)
        self.assertIn("contains secret-like value", joined)
        self.assertEqual(main(["validate-report", str(ROOT / "tests" / "fixtures" / "report.invalid.json")]), 1)

    def test_invalid_run_fails_with_timestamps_enums_arrays_and_secret_marker(self) -> None:
        result = validate_run_path(ROOT / "tests" / "fixtures" / "run.invalid.json")
        joined = "\n".join(result.errors)
        self.assertIn("$.started_at must be ISO-8601 with timezone", joined)
        self.assertIn("$.ended_at must be ISO-8601 with timezone", joined)
        self.assertIn("$.status must be one of", joined)
        self.assertIn("$.warnings must be an array", joined)
        self.assertIn("$.artifacts[0].path is required", joined)
        self.assertIn("contains secret-like value", joined)
        self.assertEqual(main(["validate-run", str(ROOT / "tests" / "fixtures" / "run.invalid.json")]), 1)


if __name__ == "__main__":
    unittest.main()