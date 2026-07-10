from __future__ import annotations

import argparse
import ctypes
import time
from ctypes import wintypes


WM_COMMAND = 0x0111
MENU_SHOW = 1000
MENU_SETTINGS = 1001


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a notification-area click to a running packaged app."
    )
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("action", choices=("show", "settings"))
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
        class_name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_name, len(class_name))
        if class_name.value == "tray_icon_app":
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
    command = MENU_SETTINGS if args.action == "settings" else MENU_SHOW
    if not ctypes.windll.user32.PostMessageW(hwnd, WM_COMMAND, command, 0):
        raise ctypes.WinError()
    time.sleep(0.25)
    print(f"sent={args.action} pid={args.pid} hwnd={hwnd}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
