from __future__ import annotations

import argparse
import struct
from pathlib import Path


WINDOWS_GUI_SUBSYSTEM = 2


def read_pe_subsystem(path: Path) -> int:
    data = path.read_bytes()
    if len(data) < 64 or data[:2] != b"MZ":
        raise ValueError(f"not a PE executable: {path}")
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if pe_offset + 94 > len(data) or data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise ValueError(f"invalid PE header: {path}")
    return struct.unpack_from("<H", data, pe_offset + 24 + 68)[0]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Assert that Windows executables use the GUI subsystem."
    )
    parser.add_argument("executables", type=Path, nargs="+")
    args = parser.parse_args()
    failed = False
    for path in args.executables:
        subsystem = read_pe_subsystem(path)
        print(f"{path}: PE subsystem {subsystem}")
        if subsystem != WINDOWS_GUI_SUBSYSTEM:
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
