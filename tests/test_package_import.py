import unittest

import ai_signal_brief
from ai_signal_brief.cli import main, run_doctor


class PackageImportTests(unittest.TestCase):
    def test_version_is_public(self) -> None:
        self.assertEqual(ai_signal_brief.__version__, "0.1.0")

    def test_version_cli_returns_success(self) -> None:
        self.assertEqual(main(["--version"]), 0)

    def test_doctor_returns_success(self) -> None:
        self.assertEqual(run_doctor(), 0)


if __name__ == "__main__":
    unittest.main()