from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import URLError

from sticky_notes.update_checker import (
    UpdateCheckError,
    check_for_updates,
    download_release_update,
    is_version_newer,
    normalize_version,
)


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.stream = io.BytesIO(payload)

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self.stream.read(size)


def release_payload(version: str = "0.3.0") -> dict[str, object]:
    base = (
        "https://github.com/LLYYXX/my-sticky-notes/"
        f"releases/download/v{version}"
    )
    return {
        "tag_name": f"v{version}",
        "html_url": (
            "https://github.com/LLYYXX/my-sticky-notes/"
            f"releases/tag/v{version}"
        ),
        "assets": [
            {
                "name": f"My.Sticky.Notes.Setup.{version}.exe",
                "browser_download_url": (
                    f"{base}/My.Sticky.Notes.Setup.{version}.exe"
                ),
                "size": 12,
            },
            {
                "name": "SHA256SUMS.txt",
                "browser_download_url": f"{base}/SHA256SUMS.txt",
                "size": 100,
            },
        ],
    }


class UpdateCheckerTests(unittest.TestCase):
    def test_versions_accept_release_tag_prefix(self) -> None:
        self.assertEqual(normalize_version("v1.2.3"), "1.2.3")
        self.assertTrue(is_version_newer("v1.3.0", "1.2.9"))
        self.assertFalse(is_version_newer("v1.2.0", "1.2.0"))

    def test_latest_release_selects_installer_and_checksum_assets(self) -> None:
        captured: dict[str, object] = {}

        def opener(request: object, *, timeout: float) -> FakeResponse:
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse(json.dumps(release_payload()).encode("utf-8"))

        result = check_for_updates("0.2.0", opener=opener)
        request = captured["request"]

        self.assertTrue(result.update_available)
        self.assertEqual(result.latest_version, "0.3.0")
        self.assertEqual(result.installer_asset.name, "My.Sticky.Notes.Setup.0.3.0.exe")
        self.assertEqual(result.checksum_asset.name, "SHA256SUMS.txt")
        self.assertEqual(captured["timeout"], 8.0)
        self.assertEqual(request.get_header("User-agent"), "MyStickyNotes/0.2.0")
        self.assertEqual(request.get_header("X-github-api-version"), "2022-11-28")

    def test_current_newer_than_published_release_is_up_to_date(self) -> None:
        payload = release_payload("0.1.0")
        result = check_for_updates(
            "0.2.0",
            opener=lambda *_args, **_kwargs: FakeResponse(
                json.dumps(payload).encode("utf-8")
            ),
        )

        self.assertFalse(result.update_available)

    def test_available_release_requires_installer_and_checksum(self) -> None:
        payload = release_payload()
        payload["assets"] = []
        with self.assertRaisesRegex(UpdateCheckError, "缺少安装包"):
            check_for_updates(
                "0.2.0",
                opener=lambda *_args, **_kwargs: FakeResponse(
                    json.dumps(payload).encode("utf-8")
                ),
            )

    def test_non_github_asset_url_is_rejected(self) -> None:
        payload = release_payload()
        payload["assets"][0]["browser_download_url"] = "https://example.com/update.exe"
        with self.assertRaises(UpdateCheckError):
            check_for_updates(
                "0.2.0",
                opener=lambda *_args, **_kwargs: FakeResponse(
                    json.dumps(payload).encode("utf-8")
                ),
            )

    def test_download_verifies_checksum_before_exposing_installer(self) -> None:
        installer_bytes = b"fake-installer"
        payload = release_payload()
        payload["assets"][0]["size"] = len(installer_bytes)
        result = check_for_updates(
            "0.2.0",
            opener=lambda *_args, **_kwargs: FakeResponse(
                json.dumps(payload).encode("utf-8")
            ),
        )
        digest = hashlib.sha256(installer_bytes).hexdigest()
        checksum_bytes = (
            f"{digest}  My Sticky Notes Setup 0.3.0.exe\n".encode("ascii")
        )

        def download_opener(request: object, *, timeout: float) -> FakeResponse:
            del timeout
            if request.full_url.endswith("SHA256SUMS.txt"):
                return FakeResponse(checksum_bytes)
            return FakeResponse(installer_bytes)

        with tempfile.TemporaryDirectory() as directory:
            downloaded = download_release_update(
                result,
                destination_dir=Path(directory),
                opener=download_opener,
            )

            self.assertEqual(
                downloaded.installer_path.name,
                "My Sticky Notes Setup 0.3.0.exe",
            )
            self.assertEqual(downloaded.installer_path.read_bytes(), installer_bytes)

    def test_checksum_mismatch_removes_partial_installer(self) -> None:
        payload = release_payload()
        result = check_for_updates(
            "0.2.0",
            opener=lambda *_args, **_kwargs: FakeResponse(
                json.dumps(payload).encode("utf-8")
            ),
        )
        checksum_bytes = (
            f"{'0' * 64}  My Sticky Notes Setup 0.3.0.exe\n".encode("ascii")
        )

        def download_opener(request: object, *, timeout: float) -> FakeResponse:
            del timeout
            if request.full_url.endswith("SHA256SUMS.txt"):
                return FakeResponse(checksum_bytes)
            return FakeResponse(b"tampered")

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(UpdateCheckError, "校验失败"):
                download_release_update(
                    result,
                    destination_dir=Path(directory),
                    opener=download_opener,
                )
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_network_errors_become_user_facing_error(self) -> None:
        def opener(*_args: object, **_kwargs: object) -> FakeResponse:
            raise URLError("offline")

        with self.assertRaisesRegex(UpdateCheckError, "无法连接 GitHub"):
            check_for_updates("0.2.0", opener=opener)


if __name__ == "__main__":
    unittest.main()
