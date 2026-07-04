from __future__ import annotations

import re
import sys
from pathlib import Path


VERSION_PATTERN = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:[-+].*)?$"
)


def numeric_version(version: str) -> tuple[int, int, int, int]:
    match = VERSION_PATTERN.fullmatch(version)
    if not match:
        raise ValueError(f"Unsupported version: {version!r}")
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        0,
    )


def render(version: str) -> str:
    numbers = numeric_version(version)
    tuple_text = ", ".join(str(part) for part in numbers)
    file_version = ".".join(str(part) for part in numbers)
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({tuple_text}),
    prodvers=({tuple_text}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'My Sticky Notes'),
          StringStruct('FileDescription', 'My Sticky Notes'),
          StringStruct('FileVersion', '{file_version}'),
          StringStruct('InternalName', 'MyStickyNotes'),
          StringStruct('OriginalFilename', 'MyStickyNotes.exe'),
          StringStruct('ProductName', 'My Sticky Notes'),
          StringStruct('ProductVersion', '{version}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: write_version_info.py VERSION OUTPUT")
    destination = Path(sys.argv[2])
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render(sys.argv[1]), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
