import json
import tempfile
import unittest
from pathlib import Path

from ai_signal_brief.archive import ArchiveError, build_archive
from ai_signal_brief.validation import find_secret_like_values, validate_report_path, validate_run_path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "examples" / "report.example.json"
RUN = ROOT / "examples" / "run.example.json"
SOURCES = ROOT / "config" / "sources.example.json"
FIXTURES = ROOT / "tests" / "fixtures"
TEST_OUTPUT_ROOT = ROOT / "outputs" / "test-archive-builder"


class ArchiveBuilderTests(unittest.TestCase):
    def test_successful_archive_creation(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            result = build_archive(REPORT, RUN, SOURCES, _archive_path(workspace), repo_root=ROOT)

            self.assertTrue(result.report_path.exists())
            self.assertTrue(result.run_path.exists())
            self.assertTrue(result.markdown_path.exists())
            self.assertTrue(result.index_path.exists())
            self.assertEqual(result.report_path.parts[-4:], ("2026", "06", "24", "report.json"))

    def test_generated_archive_report_and_run_validate(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            result = build_archive(REPORT, RUN, SOURCES, _archive_path(workspace), repo_root=ROOT)

            self.assertEqual(validate_report_path(result.report_path).errors, ())
            self.assertEqual(validate_run_path(result.run_path).errors, ())

    def test_archive_index_is_created(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            result = build_archive(REPORT, RUN, SOURCES, _archive_path(workspace), repo_root=ROOT)
            index = json.loads(result.index_path.read_text(encoding="utf-8"))

            self.assertEqual(index["schema_version"], "1.0.0")
            self.assertEqual(len(index["reports"]), 1)
            self.assertEqual(index["reports"][0]["report_id"], "2026-06-24")
            self.assertEqual(index["reports"][0]["paths"]["report"], "2026/06/24/report.json")

    def test_archive_index_sorts_dates_descending(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            archive_root = _archive_path(workspace)
            build_archive(REPORT, RUN, SOURCES, archive_root, repo_root=ROOT)

            report_two, run_two = _write_report_and_run_pair(workspace, "2026-06-25")
            result = build_archive(report_two, run_two, SOURCES, archive_root, repo_root=ROOT)
            index = json.loads(result.index_path.read_text(encoding="utf-8"))

            self.assertEqual([entry["report_date"] for entry in index["reports"]], ["2026-06-25", "2026-06-24"])

    def test_duplicate_report_id_is_rejected(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            archive_root = _archive_path(workspace)
            build_archive(REPORT, RUN, SOURCES, archive_root, repo_root=ROOT)

            with self.assertRaises(ArchiveError):
                build_archive(REPORT, RUN, SOURCES, archive_root, repo_root=ROOT)

    def test_unsafe_output_path_is_rejected(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            outside_path = Path("..") / "outside-archive"

            with self.assertRaises(ArchiveError):
                build_archive(REPORT, RUN, SOURCES, outside_path, repo_root=ROOT)
            self.assertFalse((workspace.parent / "outside-archive").exists())

    def test_quality_gate_failure_blocks_archive_writing(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            output_path = _archive_path(workspace)

            with self.assertRaises(ArchiveError):
                build_archive(REPORT, FIXTURES / "run.mismatched-report-id.json", SOURCES, output_path, repo_root=ROOT)
            self.assertFalse((ROOT / output_path).exists())

    def test_no_secret_like_values_in_archive_output(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            result = build_archive(REPORT, RUN, SOURCES, _archive_path(workspace), repo_root=ROOT)

            findings: list[str] = []
            for path in result.archive_root.rglob("*"):
                if path.is_file():
                    findings.extend(find_secret_like_values(path.read_text(encoding="utf-8")))
            self.assertEqual(findings, [])


def _temporary_workspace() -> tempfile.TemporaryDirectory[str]:
    TEST_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix="case-", dir=TEST_OUTPUT_ROOT)


def _repo_relative(path: Path) -> Path:
    return path.resolve().relative_to(ROOT.resolve())


def _archive_path(workspace: Path) -> Path:
    return _repo_relative(workspace / "archive")


def _write_report_and_run_pair(directory: Path, report_date: str) -> tuple[Path, Path]:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    run = json.loads(RUN.read_text(encoding="utf-8"))
    report["report_id"] = report_date
    report["report_date"] = report_date
    report["generated_at"] = f"{report_date}T04:00:00+08:00"
    report["title"] = f"AI Signal Brief - {report_date}"
    run["report_id"] = report_date
    run["report_date"] = report_date
    report_path = directory / f"report-{report_date}.json"
    run_path = directory / f"run-{report_date}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report_path, run_path


if __name__ == "__main__":
    unittest.main()