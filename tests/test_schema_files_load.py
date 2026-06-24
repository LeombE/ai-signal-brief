import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SchemaJsonTests(unittest.TestCase):
    def test_report_schema_loads(self) -> None:
        data = json.loads((ROOT / "schemas" / "report.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(data["title"], "AI Signal Brief Report")
        self.assertIn("stories", data["required"])
        self.assertIn("sources", data["required"])

    def test_run_schema_loads(self) -> None:
        data = json.loads((ROOT / "schemas" / "run.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(data["title"], "AI Signal Brief Run Metadata")
        self.assertIn("delivery", data["required"])
        self.assertIn("errors", data["required"])


if __name__ == "__main__":
    unittest.main()