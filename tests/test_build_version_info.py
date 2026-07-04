from __future__ import annotations

import unittest

from scripts.write_version_info import numeric_version, render


class VersionInfoTests(unittest.TestCase):
    def test_semantic_version_becomes_windows_four_part_version(self) -> None:
        self.assertEqual(numeric_version("1.2.3"), (1, 2, 3, 0))
        self.assertIn("filevers=(1, 2, 3, 0)", render("1.2.3"))

    def test_prerelease_suffix_does_not_change_numeric_version(self) -> None:
        self.assertEqual(numeric_version("2.0.0-beta.1"), (2, 0, 0, 0))

    def test_invalid_version_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            numeric_version("next")


if __name__ == "__main__":
    unittest.main()
