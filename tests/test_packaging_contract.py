from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PackagingContractTests(unittest.TestCase):
    def test_github_test_jobs_install_declared_dev_dependencies(self) -> None:
        for workflow_name in ("ci.yml", "release.yml"):
            workflow = (
                ROOT / ".github" / "workflows" / workflow_name
            ).read_text(encoding="utf-8")
            self.assertIn('python -m pip install ".[dev]"', workflow)

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

    def test_windows_bundle_is_guarded_against_console_subsystem(self) -> None:
        script = (ROOT / "build.ps1").read_text(encoding="utf-8")

        self.assertIn('"--windowed"', script)
        self.assertIn("scripts\\check_pe_subsystem.py", script)

    def test_build_cache_is_validated_against_active_python(self) -> None:
        script = (ROOT / "build.ps1").read_text(encoding="utf-8")

        self.assertIn("import PIL._imaging, PyInstaller", script)
        self.assertIn("--force-reinstall", script)

    def test_conda_openssl_runtime_is_available_to_pyinstaller(self) -> None:
        script = (ROOT / "build.ps1").read_text(encoding="utf-8")

        self.assertIn('Join-Path $PythonPrefix "Library\\bin"', script)
        self.assertIn('$env:PATH = "$CondaLibraryBin;$env:PATH"', script)

    def test_tcl_runtime_is_refreshed_for_the_active_python(self) -> None:
        script = (ROOT / "build.ps1").read_text(encoding="utf-8")

        self.assertIn("tkinter.Tcl().eval('info library')", script)
        self.assertIn('Remove-Item -LiteralPath $TclRuntime -Recurse -Force', script)
        self.assertNotIn(
            'if (-not (Test-Path -LiteralPath (Join-Path $TclRuntime',
            script,
        )


if __name__ == "__main__":
    unittest.main()
