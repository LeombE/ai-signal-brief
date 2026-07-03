import json
import tempfile
import unittest
from pathlib import Path

from ai_signal_brief.cli import main
from ai_signal_brief.reviewed_dry_run import ReviewedDryRunError, dry_run_reviewed_report


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "examples" / "reviewed-report-template"
REPORT_TEMPLATE = TEMPLATE_DIR / "report.template.json"
RUN_TEMPLATE = TEMPLATE_DIR / "run.template.json"
SOURCES = ROOT / "config" / "sources.example.json"
RELATIVE_SOURCES = Path("config") / "sources.example.json"
TEST_OUTPUT_ROOT = ROOT / "outputs" / "test-reviewed-dry-run-helper"
WORKFLOWS = ROOT / ".github" / "workflows"


class ReviewedReportDryRunTests(unittest.TestCase):
    def test_successful_dry_run_using_temporary_reviewed_report_files(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            report_path, run_path, _ = _write_candidate(workspace, "2099-01-02")

            result = dry_run_reviewed_report(
                date="2099-01-02",
                report_path=_repo_relative(report_path),
                run_path=_repo_relative(run_path),
                sources_path=RELATIVE_SOURCES,
                archive_out=_repo_relative(workspace / "archive"),
                site_out=_repo_relative(workspace / "site"),
                strict=True,
                repo_root=ROOT,
            )

            self.assertTrue(result.archive_result.index_path.exists())
            self.assertIsNotNone(result.site_result)
            self.assertTrue(result.site_result.homepage_path.exists())
            self.assertTrue(result.public_readiness_result.ok)

    def test_cli_successful_dry_run(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            report_path, run_path, _ = _write_candidate(workspace, "2099-01-03")

            exit_code = main(
                [
                    "dry-run-reviewed-report",
                    "--date",
                    "2099-01-03",
                    "--report",
                    str(_repo_relative(report_path)),
                    "--run",
                    str(_repo_relative(run_path)),
                    "--sources",
                    str(RELATIVE_SOURCES),
                    "--archive-out",
                    str(_repo_relative(workspace / "archive")),
                    "--site-out",
                    str(_repo_relative(workspace / "site")),
                    "--strict",
                ]
            )

            self.assertEqual(exit_code, 0)

    def test_no_site_skips_site_generation_but_archives(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            report_path, run_path, _ = _write_candidate(workspace, "2099-01-04")
            site_out = workspace / "site"

            result = dry_run_reviewed_report(
                date="2099-01-04",
                report_path=_repo_relative(report_path),
                run_path=_repo_relative(run_path),
                sources_path=RELATIVE_SOURCES,
                archive_out=_repo_relative(workspace / "archive"),
                site_out=_repo_relative(site_out),
                no_site=True,
                repo_root=ROOT,
            )

            self.assertTrue(result.archive_result.index_path.exists())
            self.assertIsNone(result.site_result)
            self.assertFalse(site_out.exists())

    def test_missing_report_json_fails(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            report_path, run_path, _ = _write_candidate(workspace, "2099-01-05")
            report_path.unlink()

            with self.assertRaisesRegex(ReviewedDryRunError, "missing report"):
                _run_candidate(workspace, "2099-01-05", report_path, run_path)

    def test_missing_run_json_fails(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            report_path, run_path, _ = _write_candidate(workspace, "2099-01-06")
            run_path.unlink()

            with self.assertRaisesRegex(ReviewedDryRunError, "missing run"):
                _run_candidate(workspace, "2099-01-06", report_path, run_path)

    def test_missing_review_md_fails(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            report_path, run_path, review_path = _write_candidate(workspace, "2099-01-07")
            review_path.unlink()

            with self.assertRaisesRegex(ReviewedDryRunError, "missing review"):
                _run_candidate(workspace, "2099-01-07", report_path, run_path)

    def test_invalid_run_json_fails(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            report_path, run_path, _ = _write_candidate(workspace, "2099-01-08")
            run_path.write_text(json.dumps({"schema_version": "1.0.0"}) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ReviewedDryRunError, "invalid run"):
                _run_candidate(workspace, "2099-01-08", report_path, run_path)

    def test_quality_gate_failure_fails(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            report_path, run_path, _ = _write_candidate(workspace, "2099-01-09")
            run = json.loads(run_path.read_text(encoding="utf-8"))
            run["report_id"] = "mismatched-report-id"
            run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ReviewedDryRunError, "quality gate failed"):
                _run_candidate(workspace, "2099-01-09", report_path, run_path)

    def test_unsafe_output_path_fails(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            report_path, run_path, _ = _write_candidate(workspace, "2099-01-10")

            with self.assertRaisesRegex(ReviewedDryRunError, "unsafe archive output"):
                dry_run_reviewed_report(
                    date="2099-01-10",
                    report_path=_repo_relative(report_path),
                    run_path=_repo_relative(run_path),
                    sources_path=RELATIVE_SOURCES,
                    archive_out="not-outputs/reviewed-dry-run",
                    site_out=_repo_relative(workspace / "site"),
                    repo_root=ROOT,
                )

    def test_private_marker_fails(self) -> None:
        private_label = "AI" + "\u65e5\u62a5"
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            report_path, run_path, _ = _write_candidate(
                workspace,
                "2099-01-11",
                report_mutator=lambda report: _set_analysis(report, "unsafe " + private_label),
            )

            with self.assertRaises(ReviewedDryRunError):
                _run_candidate(workspace, "2099-01-11", report_path, run_path)

    def test_secret_like_marker_fails(self) -> None:
        marker = "secret" + "-like" + "-value" + "-for" + "-test"
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            report_path, run_path, _ = _write_candidate(
                workspace,
                "2099-01-12",
                report_mutator=lambda report: _set_analysis(report, marker),
            )

            with self.assertRaises(ReviewedDryRunError):
                _run_candidate(workspace, "2099-01-12", report_path, run_path)

    def test_no_production_side_effects(self) -> None:
        before = _workflow_contents()
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            report_path, run_path, _ = _write_candidate(workspace, "2099-01-13")

            result = _run_candidate(workspace, "2099-01-13", report_path, run_path)

            self.assertTrue(result.archive_result.archive_root.exists())
            self.assertEqual(_workflow_contents(), before)
            self.assertFalse(any(path.suffix.lower() == ".docx" for path in workspace.rglob("*")))
            self.assertFalse((ROOT / "reports-reviewed" / "2099" / "01" / "13").exists())


def _temporary_workspace() -> tempfile.TemporaryDirectory[str]:
    TEST_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix="case-", dir=TEST_OUTPUT_ROOT)


def _repo_relative(path: Path) -> Path:
    return path.resolve().relative_to(ROOT.resolve())


def _write_candidate(
    workspace: Path,
    report_date: str,
    report_mutator=None,
    run_mutator=None,
) -> tuple[Path, Path, Path]:
    year, month, day = report_date.split("-")
    candidate_dir = workspace / "reviewed" / year / month / day
    candidate_dir.mkdir(parents=True, exist_ok=True)

    report = json.loads(REPORT_TEMPLATE.read_text(encoding="utf-8"))
    run = json.loads(RUN_TEMPLATE.read_text(encoding="utf-8"))
    report_id = f"{report_date}-reviewed-test"
    report["report_id"] = report_id
    report["report_date"] = report_date
    report["generated_at"] = f"{report_date}T04:00:00+08:00"
    report["title"] = f"AI Signal Brief - Reviewed Test {report_date}"
    report["sources"][0]["published_at"] = f"{report_date}T00:00:00+08:00"
    report["sources"][0]["retrieved_at"] = f"{report_date}T04:00:00+08:00"
    run["run_id"] = f"{report_date}T04-00-00+08-00-reviewed-test"
    run["started_at"] = f"{report_date}T04:00:00+08:00"
    run["ended_at"] = f"{report_date}T04:01:00+08:00"
    run["report_id"] = report_id
    run["report_date"] = report_date
    run["artifacts"] = [
        {"kind": "report_json", "path": _repo_relative(candidate_dir / "report.json").as_posix()},
        {"kind": "review_notes", "path": _repo_relative(candidate_dir / "review.md").as_posix()},
    ]
    run["warnings"] = []

    if report_mutator:
        report_mutator(report)
    if run_mutator:
        run_mutator(run)

    report_path = candidate_dir / "report.json"
    run_path = candidate_dir / "run.json"
    review_path = candidate_dir / "review.md"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    review_path.write_text(_completed_review_text(report_date), encoding="utf-8")
    return report_path, run_path, review_path


def _completed_review_text(report_date: str) -> str:
    return f"""# Reviewed Report Manual Review

Report date: {report_date}

## Manual Review Checklist

- [x] English language confirmed.
- [x] No private file paths.
- [x] No secrets.
- [x] No raw migration artifacts.
- [x] Sources are public and attributable.
- [x] Claim/source IDs resolve correctly.
- [x] Story status and importance reviewed.
- [x] Run metadata reviewed.
- [x] Quality gate expected to pass.
- [x] Generated static page will be reviewed.
- [x] Rollback plan known.

## Source Review

The placeholder source is public and attributable for local dry-run testing.

## Claim Review

The placeholder claim resolves to the placeholder source for local dry-run testing.

## Rollback Plan

Remove the local ignored output directory if the dry-run result is not acceptable.
"""


def _run_candidate(workspace: Path, report_date: str, report_path: Path, run_path: Path):
    return dry_run_reviewed_report(
        date=report_date,
        report_path=_repo_relative(report_path),
        run_path=_repo_relative(run_path),
        sources_path=RELATIVE_SOURCES,
        archive_out=_repo_relative(workspace / "archive"),
        site_out=_repo_relative(workspace / "site"),
        strict=True,
        repo_root=ROOT,
    )


def _set_analysis(report: dict, value: str) -> None:
    report["stories"][0]["analysis"] = value


def _workflow_contents() -> dict[str, str]:
    return {path.name: path.read_text(encoding="utf-8") for path in WORKFLOWS.glob("*.yml")}


if __name__ == "__main__":
    unittest.main()
