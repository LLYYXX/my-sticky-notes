from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import time
import winreg
from ctypes import wintypes
from pathlib import Path


GWL_EXSTYLE = -20
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020
WM_COMMAND = 0x0111
WM_LBUTTONUP = 0x0202
WM_USER_TRAYICON = 6002

WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000

MENU_SHOW = 1000
MENU_SETTINGS = 1001
MENU_QUIT = 1002

RUN_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
APP_REG_NAMES = ("my-sticky-notes", "My Sticky Notes")


user32 = ctypes.windll.user32
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe packaged Tauri runtime behavior on Windows."
    )
    parser.add_argument(
        "--exe",
        type=Path,
        default=Path("src-tauri/target/release/my-sticky-notes.exe"),
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path("qa/tauri-runtime-probe-state"),
    )
    parser.add_argument(
        "--skip-autostart",
        action="store_true",
        help="Skip reversible HKCU autostart verification.",
    )
    return parser.parse_args()


def enable_dpi_awareness() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def enum_windows(pid: int) -> list[dict[str, object]]:
    windows: list[dict[str, object]] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd: int, _lparam: int) -> bool:
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        if process_id.value != pid:
            return True

        rect = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        title_length = user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(title_length + 1)
        user32.GetWindowTextW(hwnd, title, len(title))
        class_name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_name, len(class_name))
        exstyle = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        windows.append(
            {
                "hwnd": int(hwnd),
                "class": class_name.value,
                "title": title.value,
                "visible": bool(user32.IsWindowVisible(hwnd)),
                "rect": [rect.left, rect.top, rect.right, rect.bottom],
                "exstyle": int(exstyle),
                "toolWindow": bool(exstyle & WS_EX_TOOLWINDOW),
                "appWindow": bool(exstyle & WS_EX_APPWINDOW),
            }
        )
        return True

    user32.EnumWindows(callback_type(callback), 0)
    return windows


def main_windows(pid: int) -> list[dict[str, object]]:
    return [
        window
        for window in enum_windows(pid)
        if window["visible"]
        and int(window["rect"][2]) - int(window["rect"][0]) >= 80
        and int(window["rect"][3]) - int(window["rect"][1]) >= 80
    ]


def wait_for(predicate, timeout: float = 5.0, interval: float = 0.1):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError(f"timed out waiting for condition; last={last!r}")


def find_main_window(pid: int) -> dict[str, object]:
    return wait_for(lambda: (main_windows(pid) or [None])[0])


def find_tray_hwnd(pid: int) -> int:
    def find() -> int | None:
        for window in enum_windows(pid):
            if window["class"] == "tray_icon_app":
                return int(window["hwnd"])
        return None

    return int(wait_for(find))


def click(hwnd_rect: list[int], css_x: float, css_y: float) -> None:
    left, top, right, bottom = hwnd_rect
    scale_x = (right - left) / 1120
    scale_y = (bottom - top) / 760
    user32.SetCursorPos(round(left + css_x * scale_x), round(top + css_y * scale_y))
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    user32.mouse_event(0x0004, 0, 0, 0, 0)


def post_tray_click(tray_hwnd: int) -> None:
    user32.PostMessageW(tray_hwnd, WM_USER_TRAYICON, 0, WM_LBUTTONUP)


def post_menu_command(tray_hwnd: int, command_id: int) -> None:
    user32.PostMessageW(tray_hwnd, WM_COMMAND, command_id, 0)


def assert_note_mode(window: dict[str, object]) -> None:
    if not window["toolWindow"] or window["appWindow"]:
        raise AssertionError(f"expected note mode tool window, got {window}")


def assert_settings_mode(window: dict[str, object]) -> None:
    if not window["appWindow"] or window["toolWindow"]:
        raise AssertionError(f"expected Settings app window, got {window}")


def read_run_values() -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            index = 0
            while True:
                try:
                    name, value, _value_type = winreg.EnumValue(key, index)
                except OSError:
                    break
                values[str(name)] = str(value)
                index += 1
    except FileNotFoundError:
        return values
    return values


def matching_autostart_values(values: dict[str, str], exe: Path) -> dict[str, str]:
    exe_text = str(exe).lower()
    exe_name = exe.name.lower()
    return {
        name: value
        for name, value in values.items()
        if exe_text in value.lower() or exe_name in value.lower()
    }


def delete_autostart_values(names: set[str]) -> None:
    if not names:
        return
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        for name in names:
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass


def reset_probe_state(state_dir: Path) -> None:
    resolved = state_dir.resolve()
    qa_root = Path.cwd().resolve() / "qa"
    if resolved == qa_root or qa_root not in resolved.parents:
        raise AssertionError(f"refusing to reset non-QA state dir: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def click_settings_button(pid: int) -> None:
    window = find_main_window(pid)
    click(window["rect"], 65, 44)


def click_autostart_switch(pid: int) -> None:
    window = find_main_window(pid)
    click(window["rect"], 650, 315)


def main() -> int:
    args = parse_args()
    enable_dpi_awareness()

    exe = args.exe.resolve()
    if not exe.exists():
        raise SystemExit(f"missing executable: {exe}")
    reset_probe_state(args.state_dir)

    env = os.environ.copy()
    env["MY_STICKY_NOTES_DATA_DIR"] = str(args.state_dir.resolve())
    process = subprocess.Popen([str(exe)], env=env)
    evidence: dict[str, object] = {"pid": process.pid}
    try:
        note = wait_for(lambda: assertion_probe(process.pid, "note"), timeout=10.0)
        evidence["initialNoteMode"] = note

        tray_hwnd = find_tray_hwnd(process.pid)
        evidence["trayHwnd"] = tray_hwnd

        post_menu_command(tray_hwnd, MENU_SETTINGS)
        settings = wait_for(lambda: (assertion_probe(process.pid, "settings")))
        evidence["traySettingsCommand"] = settings

        post_tray_click(tray_hwnd)
        restored = wait_for(lambda: (assertion_probe(process.pid, "note")))
        evidence["trayLeftClickRestore"] = restored

        post_menu_command(tray_hwnd, MENU_SETTINGS)
        wait_for(lambda: assertion_probe(process.pid, "settings"))

        if not args.skip_autostart:
            before_values = read_run_values()
            before_matches = matching_autostart_values(before_values, exe)
            if before_matches:
                raise AssertionError(
                    f"refusing to overwrite existing autostart values: {before_matches!r}"
                )
            click_autostart_switch(process.pid)
            enabled_values = wait_for(
                lambda: matching_autostart_values(read_run_values(), exe)
            )
            evidence["autostartEnabledValues"] = enabled_values
            click_autostart_switch(process.pid)
            wait_for(lambda: not matching_autostart_values(read_run_values(), exe))
            evidence["autostartDisabled"] = True

        post_menu_command(tray_hwnd, MENU_QUIT)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired as exc:
            raise AssertionError("tray quit command did not exit process") from exc
        evidence["trayQuitCommand"] = "exited"
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
        if not args.skip_autostart:
            current_matches = matching_autostart_values(read_run_values(), exe)
            delete_autostart_values(set(current_matches).union(APP_REG_NAMES))

    print(json.dumps({"result": "passed", "evidence": evidence}, ensure_ascii=False))
    return 0


def assertion_probe(pid: int, mode: str) -> dict[str, object] | None:
    window = find_main_window(pid)
    try:
        if mode == "settings":
            assert_settings_mode(window)
        else:
            assert_note_mode(window)
        return window
    except AssertionError:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
