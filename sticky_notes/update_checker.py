from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .i18n import tr


PROJECT_URL = "https://github.com/LLYYXX/my-sticky-notes"
RELEASES_API_URL = f"https://api.github.com/repos/LLYYXX/my-sticky-notes/releases/latest"
MAX_RESPONSE_BYTES = 1_000_000
MAX_CHECKSUM_BYTES = 64_000
MAX_INSTALLER_BYTES = 150_000_000
_VERSION_PATTERN = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?P<suffix>[-+][0-9A-Za-z.-]+)?$"
)
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


class UpdateCheckError(RuntimeError):
    """Raised when an official update cannot be checked or installed safely."""

    def __init__(self, code: str, **values: object) -> None:
        self.code = code
        self.values = values
        super().__init__(tr(code, **values))


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    name: str
    download_url: str
    size: int


@dataclass(frozen=True, slots=True)
class UpdateResult:
    current_version: str
    latest_version: str
    release_url: str
    update_available: bool
    installer_asset: ReleaseAsset | None = None
    checksum_asset: ReleaseAsset | None = None


@dataclass(frozen=True, slots=True)
class DownloadedUpdate:
    version: str
    installer_path: Path


def _version_key(value: str) -> tuple[int, int, int, int]:
    match = _VERSION_PATTERN.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"Unsupported version: {value}")
    stable = 1 if match.group("suffix") is None else 0
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        stable,
    )


def normalize_version(value: str) -> str:
    match = _VERSION_PATTERN.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"Unsupported version: {value}")
    suffix = match.group("suffix") or ""
    return (
        f"{match.group('major')}.{match.group('minor')}."
        f"{match.group('patch')}{suffix}"
    )


def is_version_newer(candidate: str, current: str) -> bool:
    return _version_key(candidate) > _version_key(current)


def _request_headers(version: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"MyStickyNotes/{normalize_version(version)}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _read_limited(response: Any, limit: int) -> bytes:
    payload = response.read(limit + 1)
    if len(payload) > limit:
        raise UpdateCheckError("update_error_too_large")
    return payload


def _read_json(response: Any) -> dict[str, Any]:
    payload = _read_limited(response, MAX_RESPONSE_BYTES)
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateCheckError("update_error_invalid_info") from exc
    if not isinstance(value, dict):
        raise UpdateCheckError("update_error_invalid_info")
    return value


def _validate_github_url(value: object, *, release_download: bool = False) -> str:
    if not isinstance(value, str):
        raise UpdateCheckError("update_error_invalid_url")
    parsed = urlparse(value)
    expected_prefix = "/LLYYXX/my-sticky-notes/releases/"
    if (
        parsed.scheme != "https"
        or parsed.netloc.casefold() != "github.com"
        or not parsed.path.casefold().startswith(expected_prefix.casefold())
    ):
        raise UpdateCheckError("update_error_invalid_url")
    if release_download and "/releases/download/" not in parsed.path.casefold():
        raise UpdateCheckError("update_error_invalid_url")
    return value


def _asset_from_json(value: object) -> ReleaseAsset | None:
    if not isinstance(value, dict):
        return None
    name = value.get("name")
    if not isinstance(name, str) or not name or Path(name).name != name:
        return None
    try:
        size = int(value.get("size", 0))
    except (TypeError, ValueError):
        return None
    if size < 0:
        return None
    return ReleaseAsset(
        name=name,
        download_url=_validate_github_url(
            value.get("browser_download_url"),
            release_download=True,
        ),
        size=size,
    )


def _release_assets(
    payload: dict[str, Any], latest_version: str
) -> tuple[ReleaseAsset | None, ReleaseAsset | None]:
    raw_assets = payload.get("assets", [])
    if not isinstance(raw_assets, list):
        raise UpdateCheckError("update_error_invalid_info")
    assets: list[ReleaseAsset] = []
    for value in raw_assets:
        asset = _asset_from_json(value)
        if asset is not None:
            assets.append(asset)
    expected_installer = f"My Sticky Notes Setup {latest_version}.exe"
    installer = next((asset for asset in assets if asset.name == expected_installer), None)
    checksum = next((asset for asset in assets if asset.name == "SHA256SUMS.txt"), None)
    return installer, checksum


def _map_request_error(exc: BaseException) -> UpdateCheckError:
    if isinstance(exc, HTTPError):
        if exc.code in (403, 429):
            return UpdateCheckError("update_error_rate_limit")
        if exc.code == 404:
            return UpdateCheckError("update_error_not_found")
        return UpdateCheckError("update_error_http", status=exc.code)
    return UpdateCheckError("update_error_network")


def check_for_updates(
    current_version: str,
    *,
    timeout: float = 8.0,
    opener: Callable[..., Any] | None = None,
) -> UpdateResult:
    """Return the latest published GitHub release and verified asset metadata."""
    request = Request(RELEASES_API_URL, headers=_request_headers(current_version))
    open_request = opener or urlopen
    try:
        with open_request(request, timeout=timeout) as response:
            payload = _read_json(response)
    except UpdateCheckError:
        raise
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise _map_request_error(exc) from exc

    try:
        latest_version = normalize_version(str(payload["tag_name"]))
    except (KeyError, ValueError) as exc:
        raise UpdateCheckError("update_error_invalid_version") from exc
    release_url = _validate_github_url(payload.get("html_url"))
    update_available = is_version_newer(latest_version, current_version)
    installer, checksum = _release_assets(payload, latest_version)
    if update_available and (installer is None or checksum is None):
        raise UpdateCheckError("update_error_missing_assets")
    return UpdateResult(
        current_version=normalize_version(current_version),
        latest_version=latest_version,
        release_url=release_url,
        update_available=update_available,
        installer_asset=installer,
        checksum_asset=checksum,
    )


def _expected_checksum(payload: bytes, installer_name: str) -> str:
    try:
        lines = payload.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise UpdateCheckError("update_error_checksum") from exc
    for line in lines:
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2:
            continue
        digest, name = parts
        if name.lstrip("*") == installer_name and _SHA256_PATTERN.fullmatch(digest):
            return digest.casefold()
    raise UpdateCheckError("update_error_checksum")


def default_update_directory() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    root = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return root / "MyStickyNotes" / "updates"


def download_release_update(
    result: UpdateResult,
    progress: Callable[[int, int], None] | None = None,
    *,
    destination_dir: Path | None = None,
    timeout: float = 30.0,
    opener: Callable[..., Any] | None = None,
) -> DownloadedUpdate:
    installer = result.installer_asset
    checksum = result.checksum_asset
    if not result.update_available or installer is None or checksum is None:
        raise UpdateCheckError("update_error_missing_assets")
    if installer.size > MAX_INSTALLER_BYTES:
        raise UpdateCheckError("update_error_too_large")
    open_request = opener or urlopen
    headers = _request_headers(result.current_version)
    try:
        with open_request(
            Request(checksum.download_url, headers=headers), timeout=timeout
        ) as response:
            expected = _expected_checksum(
                _read_limited(response, MAX_CHECKSUM_BYTES), installer.name
            )
    except UpdateCheckError:
        raise
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise _map_request_error(exc) from exc

    target_dir = destination_dir or default_update_directory() / result.latest_version
    target = target_dir / installer.name
    partial = target.with_suffix(target.suffix + ".part")
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        partial.unlink(missing_ok=True)
        digest = hashlib.sha256()
        total = 0
        with open_request(
            Request(installer.download_url, headers=headers), timeout=timeout
        ) as response, partial.open("wb") as stream:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_INSTALLER_BYTES:
                    raise UpdateCheckError("update_error_too_large")
                digest.update(chunk)
                stream.write(chunk)
                if progress is not None:
                    progress(total, installer.size)
            stream.flush()
            os.fsync(stream.fileno())
        if digest.hexdigest().casefold() != expected:
            raise UpdateCheckError("update_error_checksum")
        os.replace(partial, target)
    except UpdateCheckError:
        partial.unlink(missing_ok=True)
        raise
    except (HTTPError, URLError, TimeoutError) as exc:
        partial.unlink(missing_ok=True)
        raise _map_request_error(exc) from exc
    except OSError as exc:
        partial.unlink(missing_ok=True)
        raise UpdateCheckError("update_error_write") from exc
    return DownloadedUpdate(result.latest_version, target)


def launch_update_installer(update: DownloadedUpdate) -> None:
    path = update.installer_path.resolve()
    if path.suffix.casefold() != ".exe" or not path.is_file():
        raise UpdateCheckError("update_error_launch")
    try:
        subprocess.Popen([str(path)], close_fds=True)
    except OSError as exc:
        raise UpdateCheckError("update_error_launch") from exc
