import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "daily-ai-report.yml"


class DailyAIReportWorkflowTests(unittest.TestCase):
    def test_workflow_schedule_runtime_and_permissions(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn('cron: "30 0 * * *"', workflow)
        self.assertIn("runs-on: ubuntu-latest", workflow)
        self.assertIn('python-version: "3.11"', workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertNotIn("pages: write", workflow)
        self.assertNotIn("deploy-pages", workflow)

    def test_workflow_uses_github_secrets_context_only(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        secret_refs = sorted(set(re.findall(r"secrets\.([A-Z0-9_]+)", workflow)))
        self.assertEqual(secret_refs, ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"])
        self.assertNotRegex(workflow, r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b")
        self.assertNotIn("OPENAI_API_KEY", workflow)
        self.assertIn("Missing required GitHub secret TELEGRAM_BOT_TOKEN", workflow)
        self.assertIn("Missing required GitHub secret TELEGRAM_CHAT_ID", workflow)

    def test_workflow_command_shape_and_artifacts(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        normalized = re.sub(r"\s+", " ", workflow)

        self.assertIn("python -m compileall src", workflow)
        self.assertIn("python -m unittest discover -s tests", workflow)
        self.assertIn("python -m ai_signal_brief public-readiness", workflow)
        self.assertIn("python -m ai_signal_brief build-daily-ai-report", workflow)
        for expected in (
            '--date "$REPORT_DATE"',
            "--timezone Asia/Kuala_Lumpur",
            '--out "$REPORT_OUT"',
            "--format markdown,json,docx",
            "--english-only",
            "--no-openai",
            "--max-items 10",
            "--lookback-hours 48",
            "--min-fresh-items 3",
            "--send-telegram",
        ):
            self.assertIn(expected, workflow)
        self.assertIn("daily-ai-report-telegram-send-attempted", workflow)
        self.assertIn("actions/upload-artifact@v4", workflow)
        self.assertIn("outputs/daily-reports/*-live/report.json", workflow)
        self.assertIn("outputs/daily-reports/*-live/report.md", workflow)
        self.assertIn("outputs/daily-reports/*-live/report.docx", workflow)
        self.assertNotIn("git add", normalized)
        self.assertNotIn("git commit", normalized)
        self.assertNotIn("git push", normalized)


if __name__ == "__main__":
    unittest.main()