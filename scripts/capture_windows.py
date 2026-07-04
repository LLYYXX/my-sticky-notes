from __future__ import annotations

import argparse
import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

from PIL import Image, ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sticky_notes.platform.windows import enable_dpi_awareness


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture visible windows for one process.")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--hover", action="store_true")
    return parser.parse_args()


def visible_windows(pid: int) -> list[tuple[int, tuple[int, int, int, int]]]:
    user32 = ctypes.windll.user32
    handles: list[tuple[int, tuple[int, int, int, int]]] = []

    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        if process_id.value != pid:
            return True
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width >= 40 and height >= 40:
            handles.append((hwnd, (rect.left, rect.top, rect.right, rect.bottom)))
        return True

    user32.EnumWindows(callback_type(callback), 0)
    return sorted(handles, key=lambda item: (item[1][0], item[1][1]))


def main() -> int:
    args = parse_args()
    enable_dpi_awareness()
    windows = visible_windows(args.pid)
    if not windows:
        raise SystemExit(f"No visible windows found for pid {args.pid}")

    user32 = ctypes.windll.user32
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    hwnd_topmost = ctypes.c_void_p(-1)
    hwnd_notopmost = ctypes.c_void_p(-2)
    swp_flags = 0x0001 | 0x0002 | 0x0010 | 0x0040
    for hwnd, _box in windows:
        if not user32.SetWindowPos(hwnd, hwnd_topmost, 0, 0, 0, 0, swp_flags):
            raise ctypes.WinError()
    time.sleep(0.35)

    if args.hover:
        _, (left, top, right, _bottom) = windows[0]
        ctypes.windll.user32.SetCursorPos(right - 70, top + 22)
        time.sleep(0.35)
    canvas = Image.new("RGB", (1440, 900), "#EEECE8")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    captures: list[tuple[tuple[int, int, int, int], Image.Image]] = []
    for index, (hwnd, box) in enumerate(windows):
        if not user32.SetWindowPos(hwnd, hwnd_topmost, 0, 0, 0, 0, swp_flags):
            raise ctypes.WinError()
        time.sleep(0.08)
        left, top, right, bottom = box
        image = ImageGrab.grab(box, include_layered_windows=True).convert("RGB")
        image.save(args.out.with_name(f"{args.out.stem}-note-{index}.png"))
        captures.append((box, image))

    min_left = min(box[0] for box, _image in captures)
    min_top = min(box[1] for box, _image in captures)
    max_right = max(box[2] for box, _image in captures)
    max_bottom = max(box[3] for box, _image in captures)
    scale = min(
        1.0,
        (canvas.width - 120) / max(1, max_right - min_left),
        (canvas.height - 120) / max(1, max_bottom - min_top),
    )
    for box, image in captures:
        left, top, _right, _bottom = box
        if scale < 1.0:
            image = image.resize(
                (round(image.width * scale), round(image.height * scale)),
                Image.Resampling.LANCZOS,
            )
        x = 60 + round((left - min_left) * scale)
        y = 60 + round((top - min_top) * scale)
        canvas.paste(image, (x, y))
    canvas.save(args.out)
    for hwnd, _box in windows:
        if not user32.SetWindowPos(hwnd, hwnd_notopmost, 0, 0, 0, 0, swp_flags):
            raise ctypes.WinError()
    print(f"captured={len(windows)} output={args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
