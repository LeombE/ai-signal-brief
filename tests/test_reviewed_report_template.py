import json
import re
import unittest
from pathlib import Path

from ai_signal_brief.validation import validate_report_path, validate_run_path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "examples" / "reviewed-report-template"
REPORT_TEMPLATE = TEMPLATE_DIR / "report.template.json"
RUN_TEMPLATE = TEMPLATE_DIR / "run.template.json"
REVIEW_TEMPLATE = TEMPLATE_DIR / "review.template.md"
README = TEMPLATE_DIR / "README.md"
TEMPLATE_FILES = (README, REPORT_TEMPLATE, RUN_TEMPLATE, REVIEW_TEMPLATE)


def forbidden_patterns() -> tuple[tuple[str, re.Pattern[str]], ...]:
    private_label = "AI" + "\u65e5\u62a5"
    private_path = "C:" + "\\" + "Users" + "\\" + "Admin" + "\\" + "OneDrive" + "\\" + "Documents" + "\\" + private_label
    return (
        ("private source label", re.compile(re.escape(private_label))),
        ("private source path", re.compile(re.escape(private_path))),
        ("telegram credential", re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b")),
        ("openai credential", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
        ("chat reference", re.compile(re.escape("chat" + "_id"), re.IGNORECASE)),
        ("legacy report builder", re.compile(re.escape("build" + "_report_"))),
        ("legacy telegram sender", re.compile(re.escape("send" + "-telegram" + "-report"))),
        ("mistaken project", re.compile(re.escape("github" + "-daily" + "-intelligence"), re.IGNORECASE)),
        ("mistaken prompt", re.compile(re.escape("00_MASTER" + "_PROMPT.md"))),
    )


class ReviewedReportTemplateTests(unittest.TestCase):
    def test_template_readme_exists(self) -> None:
        self.assertTrue(README.is_file())

    def test_review_template_exists(self) -> None:
        self.assertTrue(REVIEW_TEMPLATE.is_file())

    def test_report_template_is_valid_json(self) -> None:
        data = json.loads(REPORT_TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(data["language"], "en")
        self.assertTrue(data["stories"])
        self.assertTrue(data["sources"])
        self.assertEqual(data["provenance"]["template_only"], True)

    def test_run_template_is_valid_json(self) -> None:
        data = json.loads(RUN_TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(data["mode"], "manual")
        self.assertFalse(data["delivery"]["telegram"]["enabled"])
        self.assertEqual(data["errors"], [])

    def test_report_template_passes_report_validator(self) -> None:
        result = validate_report_path(REPORT_TEMPLATE)
        self.assertTrue(result.ok, result.errors)

    def test_run_template_passes_run_validator(self) -> None:
        result = validate_run_path(RUN_TEMPLATE)
        self.assertTrue(result.ok, result.errors)

    def test_template_files_contain_no_forbidden_private_markers(self) -> None:
        patterns = forbidden_patterns()
        for path in TEMPLATE_FILES:
            content = path.read_text(encoding="utf-8")
            for label, pattern in patterns:
                with self.subTest(file=path.name, marker=label):
                    self.assertIsNone(pattern.search(content))


if __name__ == "__main__":
    unittest.main()