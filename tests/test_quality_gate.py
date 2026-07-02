import unittest
from pathlib import Path

from ai_signal_brief.cli import main
from ai_signal_brief.quality_gate import run_quality_gate


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "examples" / "report.example.json"
RUN = ROOT / "examples" / "run.example.json"
SOURCES = ROOT / "config" / "sources.example.json"
FIXTURES = ROOT / "tests" / "fixtures"


class QualityGateTests(unittest.TestCase):
    def test_quality_gate_success(self) -> None:
        result = run_quality_gate(REPORT, RUN, SOURCES, repo_root=ROOT)

        self.assertTrue(result.ok)
        self.assertEqual(result.failed_checks, ())
        self.assertEqual(
            main(
                [
                    "quality-gate",
                    "--report",
                    str(REPORT),
                    "--run",
                    str(RUN),
                    "--sources",
                    str(SOURCES),
                ]
            ),
            0,
        )

    def test_mismatched_report_run_rejected(self) -> None:
        result = run_quality_gate(REPORT, FIXTURES / "run.mismatched-report-id.json", SOURCES, repo_root=ROOT)

        self.assertFalse(result.ok)
        self.assertIn("report_run_identity", result.failed_checks)

    def test_unsafe_artifact_rejected(self) -> None:
        result = run_quality_gate(REPORT, FIXTURES / "run.unsafe-artifact.json", SOURCES, repo_root=ROOT)

        self.assertFalse(result.ok)
        self.assertIn("artifact_paths", result.failed_checks)

    def test_secret_like_value_rejected(self) -> None:
        result = run_quality_gate(REPORT, FIXTURES / "run.secret-like.json", SOURCES, repo_root=ROOT)

        self.assertFalse(result.ok)
        self.assertIn("run_validation", result.failed_checks)
        self.assertIn("unsafe_values", result.failed_checks)

    def test_mistaken_prompt_reference_rejected(self) -> None:
        result = run_quality_gate(FIXTURES / "report.mistaken-prompt.json", RUN, SOURCES, repo_root=ROOT)

        self.assertFalse(result.ok)
        self.assertIn("mistaken_prompt_references", result.failed_checks)

    def test_source_registry_compatibility_rejected(self) -> None:
        result = run_quality_gate(REPORT, RUN, FIXTURES / "sources.disallow-official.json", repo_root=ROOT)

        self.assertFalse(result.ok)
        self.assertIn("sources_validation", result.failed_checks)
        self.assertIn("source_type_compatibility", result.failed_checks)


if __name__ == "__main__":
    unittest.main()