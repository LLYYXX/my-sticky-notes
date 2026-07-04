from __future__ import annotations

import os
import sys
import tarfile
import time
from pathlib import Path


def _validate_member(destination: Path, member: tarfile.TarInfo) -> None:
    if member.issym() or member.islnk():
        raise ValueError(f"NSIS archive contains an unsupported link: {member.name}")
    target = (destination / member.name).resolve()
    if os.path.commonpath((destination, target)) != str(destination):
        raise ValueError(f"NSIS archive contains an unsafe path: {member.name}")


def _is_file_with_retry(path: Path) -> bool:
    for attempt in range(10):
        try:
            return path.is_file()
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.2)
    return False


def extract_nsis(tools_directory: Path) -> Path:
    tools_directory = tools_directory.resolve()
    sys.path.insert(0, str(tools_directory))
    import smol_nsis

    destination = tools_directory / "nsis"
    compiler = destination / "smol-nsis" / "bin" / "makensis.exe"
    if _is_file_with_retry(compiler):
        return compiler

    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(smol_nsis.get_archive_path(), "r:xz") as archive:
        members = archive.getmembers()
        for member in members:
            _validate_member(destination, member)
        if sys.version_info >= (3, 12):
            archive.extractall(destination, members=members, filter="data")
        else:
            archive.extractall(destination, members=members)

    if not _is_file_with_retry(compiler):
        raise FileNotFoundError("makensis.exe was not found after extracting smol-nsis")
    return compiler


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: extract_nsis.py TOOLS_DIRECTORY")
    print(extract_nsis(Path(sys.argv[1])))


if __name__ == "__main__":
    main()
