import json
import tempfile
import unittest
from pathlib import Path

from ai_signal_brief.archive import build_archive
from ai_signal_brief.site import SiteBuildError, build_site
from ai_signal_brief.validation import find_secret_like_values


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "examples" / "report.example.json"
RUN = ROOT / "examples" / "run.example.json"
SOURCES = ROOT / "config" / "sources.example.json"
TEST_OUTPUT_ROOT = ROOT / "outputs" / "test-static-site-builder"


class StaticSiteBuilderTests(unittest.TestCase):
    def test_successful_site_generation_from_valid_archive(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            archive_root = _build_sample_archive(workspace)
            result = build_site(archive_root, _repo_relative(workspace / "site"), repo_root=ROOT)

            self.assertTrue(result.homepage_path.exists())
            self.assertTrue(result.stylesheet_path.exists())
            self.assertTrue(result.manifest_path.exists())
            self.assertEqual(len(result.report_pages), 1)

    def test_homepage_exists(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            archive_root = _build_sample_archive(workspace)
            result = build_site(archive_root, _repo_relative(workspace / "site"), repo_root=ROOT)

            self.assertTrue((result.site_root / "index.html").exists())

    def test_per_report_page_exists(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            archive_root = _build_sample_archive(workspace)
            result = build_site(archive_root, _repo_relative(workspace / "site"), repo_root=ROOT)

            self.assertTrue((result.site_root / "2026" / "06" / "24" / "index.html").exists())

    def test_reports_sorted_descending(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            archive_root = _repo_relative(workspace / "archive")
            build_archive(REPORT, RUN, SOURCES, archive_root, repo_root=ROOT)
            report_two, run_two = _write_report_and_run_pair(workspace, "2026-06-25", "Later report")
            build_archive(report_two, run_two, SOURCES, archive_root, repo_root=ROOT)
            result = build_site(archive_root, _repo_relative(workspace / "site"), repo_root=ROOT)
            homepage = result.homepage_path.read_text(encoding="utf-8")

            self.assertLess(homepage.index("2026-06-25"), homepage.index("2026-06-24"))

    def test_generated_html_escapes_unsafe_content(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            report_path, run_path = _write_report_and_run_pair(workspace, "2026-06-26", "<script>alert(1)</script>")
            archive_root = _repo_relative(workspace / "archive")
            build_archive(report_path, run_path, SOURCES, archive_root, repo_root=ROOT)
            result = build_site(archive_root, _repo_relative(workspace / "site"), repo_root=ROOT)
            page = (result.site_root / "2026" / "06" / "26" / "index.html").read_text(encoding="utf-8")

            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)
            self.assertNotIn("<script>alert(1)</script>", page)

    def test_unsafe_archive_path_is_rejected(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)

            with self.assertRaises(SiteBuildError):
                build_site(Path("..") / "outside-archive", _repo_relative(workspace / "site"), repo_root=ROOT)

    def test_missing_archive_index_is_rejected(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            archive_root = _repo_relative(workspace / "archive")
            (ROOT / archive_root).mkdir(parents=True)

            with self.assertRaises(SiteBuildError):
                build_site(archive_root, _repo_relative(workspace / "site"), repo_root=ROOT)

    def test_generated_site_contains_no_secret_like_values(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            archive_root = _build_sample_archive(workspace)
            result = build_site(archive_root, _repo_relative(workspace / "site"), repo_root=ROOT)

            findings: list[str] = []
            for path in result.site_root.rglob("*"):
                if path.is_file():
                    findings.extend(find_secret_like_values(path.read_text(encoding="utf-8")))
            self.assertEqual(findings, [])

    def test_generated_site_contains_no_mistaken_prompt_references(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            archive_root = _build_sample_archive(workspace)
            result = build_site(archive_root, _repo_relative(workspace / "site"), repo_root=ROOT)
            combined = _read_site(result.site_root).lower()

            mistaken_project = "github" + "-daily" + "-intelligence"
            self.assertNotIn(mistaken_project, combined)
            self.assertNotIn(("00_master" + "_prompt.md"), combined)
            self.assertNotIn(("feat/public-" + mistaken_project), combined)

    def test_generated_site_contains_no_private_ai_source_path(self) -> None:
        with _temporary_workspace() as directory:
            workspace = Path(directory)
            archive_root = _build_sample_archive(workspace)
            result = build_site(archive_root, _repo_relative(workspace / "site"), repo_root=ROOT)
            combined = _read_site(result.site_root)

            self.assertNotIn(("AI" + "\u65e5\u62a5"), combined)
            self.assertNotIn(("C:" + "\\\\" + "Users" + "\\\\" + "Admin" + "\\\\" + "OneDrive" + "\\\\" + "Documents"), combined)


def _temporary_workspace() -> tempfile.TemporaryDirectory[str]:
    TEST_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix="case-", dir=TEST_OUTPUT_ROOT)


def _repo_relative(path: Path) -> Path:
    return path.resolve().relative_to(ROOT.resolve())


def _build_sample_archive(workspace: Path) -> Path:
    archive_root = _repo_relative(workspace / "archive")
    build_archive(REPORT, RUN, SOURCES, archive_root, repo_root=ROOT)
    return archive_root


def _write_report_and_run_pair(directory: Path, report_date: str, title: str) -> tuple[Path, Path]:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    run = json.loads(RUN.read_text(encoding="utf-8"))
    report["report_id"] = report_date
    report["report_date"] = report_date
    report["generated_at"] = f"{report_date}T04:00:00+08:00"
    report["title"] = title
    run["report_id"] = report_date
    run["report_date"] = report_date
    report_path = directory / f"report-{report_date}.json"
    run_path = directory / f"run-{report_date}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report_path, run_path


def _read_site(site_root: Path) -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in site_root.rglob("*") if path.is_file())


if __name__ == "__main__":
    unittest.main()
