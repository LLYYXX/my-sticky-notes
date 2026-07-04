from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PackagingContractTests(unittest.TestCase):
    def test_installer_is_per_user_and_keeps_note_data_on_uninstall(self) -> None:
        script = (ROOT / "installer" / "MyStickyNotes.nsi").read_text(
            encoding="utf-8"
        )

        self.assertIn("RequestExecutionLevel user", script)
        self.assertIn('InstallDir "$LOCALAPPDATA\\Programs\\MyStickyNotes"', script)
        self.assertIn("MUI_PAGE_DIRECTORY", script)
        self.assertIn('CreateShortcut "$SMPROGRAMS\\${APP_NAME}.lnk"', script)
        self.assertNotIn('RMDir /r "$LOCALAPPDATA\\MyStickyNotes"', script)

    def test_setup_is_the_only_release_artifact(self) -> None:
        script = (ROOT / "build.ps1").read_text(encoding="utf-8")

        self.assertIn('"My Sticky Notes Setup $Version.exe"', script)
        self.assertIn('[string]$OutputDirectory = "release"', script)
        self.assertIn('"SHA256SUMS.txt"', script)
        self.assertNotIn("--onefile", script)
        self.assertNotIn("Portable", script)
        self.assertNotIn("Compress-Archive", script)


if __name__ == "__main__":
    unittest.main()
