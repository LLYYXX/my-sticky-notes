from __future__ import annotations

import argparse
import ctypes
import time
from ctypes import wintypes


WM_APP = 0x8000
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
TRAY_CALLBACK_MESSAGE = WM_APP + 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a notification-area click to a running packaged app."
    )
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("action", choices=("settings",))
    return parser.parse_args()


def hidden_tray_window(pid: int) -> int:
    user32 = ctypes.windll.user32
    result = 0
    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
    )

    def callback(hwnd: int, _lparam: int) -> bool:
        nonlocal result
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        if process_id.value != pid:
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, len(title))
        if title.value == "My Sticky Notes":
            result = int(hwnd)
            return False
        return True

    user32.EnumWindows(callback_type(callback), 0)
    if not result:
        raise SystemExit(f"Tray host window not found for pid {pid}")
    return result


def main() -> int:
    args = parse_args()
    hwnd = hidden_tray_window(args.pid)
    events = (WM_LBUTTONUP, WM_LBUTTONDBLCLK, WM_LBUTTONUP)
    for event in events:
        if not ctypes.windll.user32.PostMessageW(
            hwnd, TRAY_CALLBACK_MESSAGE, 0, event
        ):
            raise ctypes.WinError()
        time.sleep(0.04)
    time.sleep(0.65)
    print(f"sent={args.action} pid={args.pid} hwnd={hwnd}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
