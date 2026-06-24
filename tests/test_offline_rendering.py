import json
import tempfile
import unittest
from pathlib import Path

from ai_signal_brief.cli import main
from ai_signal_brief.rendering import RenderError, render_markdown_from_path, render_telegram_from_path
from ai_signal_brief.validation import find_secret_like_values


ROOT = Path(__file__).resolve().parents[1]
VALID_REPORT = ROOT / "examples" / "report.example.json"
INVALID_REPORT = ROOT / "tests" / "fixtures" / "report.invalid.json"


class OfflineRenderingTests(unittest.TestCase):
    def test_markdown_rendering_success(self) -> None:
        rendered = render_markdown_from_path(VALID_REPORT)
        self.assertIn("# AI Signal Brief - 2026-06-24", rendered)
        self.assertIn("Report date: 2026-06-24", rendered)
        self.assertIn("Generated at: 2026-06-24T04:00:00+08:00", rendered)
        self.assertIn("Timezone: Asia/Kuala_Lumpur", rendered)
        self.assertIn("## Top Story Summary", rendered)
        self.assertIn("## Ranked Stories", rendered)
        self.assertIn("Status: new", rendered)
        self.assertIn("Importance: 4/5", rendered)
        self.assertIn("## Sources", rendered)
        self.assertIn("source-001", rendered)
        self.assertIn("claim-001", rendered)
        self.assertIn("## Provenance", rendered)
        self.assertEqual(find_secret_like_values(rendered), [])

    def test_telegram_rendering_success(self) -> None:
        rendered = render_telegram_from_path(VALID_REPORT)
        self.assertIn("AI Signal Brief - 2026-06-24", rendered)
        self.assertIn("Generated: 2026-06-24T04:00:00+08:00", rendered)
        self.assertIn("Offline generated preview", rendered)
        self.assertIn("Top stories:", rendered)
        self.assertIn("Example model platform update", rendered)
        self.assertNotIn("api.telegram.org", rendered)
        self.assertEqual(find_secret_like_values(rendered), [])

    def test_renderer_refuses_invalid_report_json(self) -> None:
        with self.assertRaises(RenderError):
            render_markdown_from_path(INVALID_REPORT)
        with self.assertRaises(RenderError):
            render_telegram_from_path(INVALID_REPORT)

    def test_cli_writes_temp_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            markdown_path = tmp_path / "report.md"
            telegram_path = tmp_path / "telegram.txt"
            self.assertEqual(main(["render-markdown", str(VALID_REPORT), "--out", str(markdown_path)]), 0)
            self.assertEqual(main(["render-telegram", str(VALID_REPORT), "--out", str(telegram_path)]), 0)
            self.assertTrue(markdown_path.exists())
            self.assertTrue(telegram_path.exists())
            self.assertIn("source-001", markdown_path.read_text(encoding="utf-8"))
            self.assertIn("offline", telegram_path.read_text(encoding="utf-8").lower())

    def test_markdown_includes_generated_content_disclosure_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            data = json.loads(VALID_REPORT.read_text(encoding="utf-8"))
            data["provenance"]["generated_content_disclosure"] = "Generated with AI assistance and reviewed before publication."
            report_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            rendered = render_markdown_from_path(report_path)
            self.assertIn("AI/generated-content disclosure", rendered)
            self.assertIn("Generated with AI assistance", rendered)


if __name__ == "__main__":
    unittest.main()