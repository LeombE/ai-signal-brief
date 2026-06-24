import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExampleJsonTests(unittest.TestCase):
    def test_report_example_loads(self) -> None:
        data = json.loads((ROOT / "examples" / "report.example.json").read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], "1.0.0")
        self.assertEqual(data["language"], "en")
        self.assertTrue(data["stories"])
        self.assertTrue(data["sources"])

    def test_run_example_loads(self) -> None:
        data = json.loads((ROOT / "examples" / "run.example.json").read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], "1.0.0")
        self.assertFalse(data["delivery"]["telegram"]["enabled"])
        self.assertEqual(data["errors"], [])


if __name__ == "__main__":
    unittest.main()