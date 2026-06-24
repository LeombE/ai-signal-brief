import unittest
from pathlib import Path

from ai_signal_brief.cli import main
from ai_signal_brief.validation import load_source_registry, source_priorities, validate_sources_path


ROOT = Path(__file__).resolve().parents[1]


class SourceRegistryValidationTests(unittest.TestCase):
    def test_valid_source_registry_passes(self) -> None:
        result = validate_sources_path(ROOT / "config" / "sources.example.json")
        self.assertEqual(result.errors, ())
        self.assertEqual(main(["validate-sources", str(ROOT / "config" / "sources.example.json")]), 0)

    def test_list_source_priorities_passes(self) -> None:
        self.assertEqual(main(["list-source-priorities"]), 0)

    def test_source_priorities_are_sorted(self) -> None:
        registry = load_source_registry(ROOT / "config" / "sources.example.json")
        priorities = source_priorities(registry)
        self.assertEqual([item["id"] for item in priorities[:3]], ["official", "paper", "repository"])

    def test_invalid_source_registry_fails(self) -> None:
        result = validate_sources_path(ROOT / "tests" / "fixtures" / "sources.invalid.json")
        joined = "\n".join(result.errors)
        self.assertIn("$.source_policy must be 'official_sources_first'", joined)
        self.assertIn("duplicates category id", joined)
        self.assertIn("duplicates source id", joined)
        self.assertIn("official category must exist with priority 1", joined)
        self.assertIn("must be compatible with report source_type values", joined)
        self.assertIn("references unknown category id", joined)
        self.assertIn("must be public HTTPS and not local/private", joined)
        self.assertIn("contains secret-like value", joined)
        self.assertEqual(main(["validate-sources", str(ROOT / "tests" / "fixtures" / "sources.invalid.json")]), 1)


if __name__ == "__main__":
    unittest.main()