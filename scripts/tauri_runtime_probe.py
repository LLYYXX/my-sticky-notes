from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import struct
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
NOTE_TITLE = "My Sticky Notes"
SETTINGS_TITLE = "桌面便利贴设置"


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


class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
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
    parser.add_argument(
        "--note-count",
        type=int,
        default=1,
        help="Populate an isolated state with this many notes before launch.",
    )
    parser.add_argument(
        "--skip-memory-budget",
        action="store_true",
        help="Record process memory without enforcing the lightweight budgets.",
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


def find_note_window(pid: int) -> dict[str, object]:
    return wait_for(lambda: next(iter(find_note_windows(pid)), None))


def find_note_windows(pid: int) -> list[dict[str, object]]:
    return [
        window
        for window in main_windows(pid)
        if window["title"] == NOTE_TITLE and bool(window["toolWindow"])
    ]


def find_settings_window(pid: int) -> dict[str, object]:
    return wait_for(
        lambda: next(
            (
                window
                for window in main_windows(pid)
                if window["title"] == SETTINGS_TITLE and bool(window["appWindow"])
            ),
            None,
        )
    )


def find_tray_hwnd(pid: int) -> int:
    def find() -> int | None:
        for window in enum_windows(pid):
            if window["class"] == "tray_icon_app":
                return int(window["hwnd"])
        return None

    return int(wait_for(find))


def click(hwnd_rect: list[int], relative_x: float, relative_y: float) -> None:
    left, top, right, bottom = hwnd_rect
    user32.SetCursorPos(
        round(left + (right - left) * relative_x),
        round(top + (bottom - top) * relative_y),
    )
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    user32.mouse_event(0x0004, 0, 0, 0, 0)


def post_tray_click(tray_hwnd: int) -> None:
    user32.PostMessageW(tray_hwnd, WM_USER_TRAYICON, 0, WM_LBUTTONUP)


def post_menu_command(tray_hwnd: int, command_id: int) -> None:
    user32.PostMessageW(tray_hwnd, WM_COMMAND, command_id, 0)


def assert_note_mode(window: dict[str, object]) -> None:
    if not window["toolWindow"] or window["appWindow"]:
        raise AssertionError(f"expected note mode tool window, got {window}")


def assert_independent_note_windows(
    windows: list[dict[str, object]], expected_count: int
) -> None:
    if len(windows) != expected_count:
        raise AssertionError(
            f"expected {expected_count} independent note windows, got {len(windows)}: {windows!r}"
        )
    for window in windows:
        width = int(window["rect"][2]) - int(window["rect"][0])
        height = int(window["rect"][3]) - int(window["rect"][1])
        if width >= 800 or height >= 600:
            raise AssertionError(f"unexpected desktop overlay window: {window!r}")


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


def write_fixture_state(state_dir: Path, note_count: int) -> None:
    if note_count < 1:
        raise AssertionError("note-count must be at least one")
    colors = ("yellow", "offwhite", "lime", "lilac", "cream", "pink", "mint", "coral", "navy")
    notes = [
        {
            "id": f"probe-note-{index}",
            "color": colors[index % len(colors)],
            "pinned": False,
            "collapsed": False,
            "todos": [
                {
                    "id": f"probe-todo-{index}",
                    "text": "runtime probe todo",
                    "completed": False,
                    "order": 0,
                }
            ],
        }
        for index in range(note_count)
    ]
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "state.json").write_text(
        json.dumps(
            {
                "version": 8,
                "settings": {"openAtLogin": False, "language": "en"},
                "notes": notes,
            }
        ),
        encoding="utf-8",
    )


def working_set_mb(pid: int) -> float:
    process_query_limited_information = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(
        process_query_limited_information, False, pid
    )
    if not handle:
        raise ctypes.WinError()
    try:
        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(counters)
        if not ctypes.windll.psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(counters), counters.cb
        ):
            raise ctypes.WinError()
        return round(counters.WorkingSetSize / (1024 * 1024), 1)
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def assert_memory_budget(working_set: float, note_count: int) -> None:
    budget = 220.0 if note_count >= 5 else 150.0
    if working_set > budget:
        raise AssertionError(
            f"working set exceeds {budget:.0f} MB budget: {working_set:.1f} MB"
        )


def assert_windows_gui_subsystem(exe: Path) -> int:
    with exe.open("rb") as stream:
        payload = stream.read(4096)
    if payload[:2] != b"MZ":
        raise AssertionError(f"expected a PE executable, got {exe}")
    pe_offset = struct.unpack_from("<I", payload, 0x3C)[0]
    optional_header = pe_offset + 24
    if (
        payload[pe_offset : pe_offset + 2] != b"PE"
        or payload[pe_offset + 2 : pe_offset + 4] != bytes(2)
    ):
        raise AssertionError("PE header is invalid")
    subsystem = struct.unpack_from("<H", payload, optional_header + 68)[0]
    if subsystem != 2:
        raise AssertionError(
            f"release executable must use Windows GUI subsystem 2, got {subsystem}"
        )
    return subsystem


def click_autostart_switch(pid: int) -> None:
    window = find_settings_window(pid)
    click(window["rect"], 0.89, 0.38)


def main() -> int:
    args = parse_args()
    enable_dpi_awareness()

    exe = args.exe.resolve()
    if not exe.exists():
        raise SystemExit(f"missing executable: {exe}")
    reset_probe_state(args.state_dir)
    write_fixture_state(args.state_dir, args.note_count)

    env = os.environ.copy()
    env["MY_STICKY_NOTES_DATA_DIR"] = str(args.state_dir.resolve())
    env["MY_STICKY_NOTES_INSTANCE_PORT"] = "45420"
    process = subprocess.Popen([str(exe)], env=env)
    evidence: dict[str, object] = {
        "pid": process.pid,
        "peSubsystem": assert_windows_gui_subsystem(exe),
    }
    try:
        notes = wait_for(
            lambda: find_note_windows(process.pid)
            if len(find_note_windows(process.pid)) == args.note_count
            else None,
            timeout=10.0,
        )
        assert_independent_note_windows(notes, args.note_count)
        evidence["initialNoteWindows"] = notes
        evidence["initialNoteMode"] = notes[0]
        idle_memory = working_set_mb(process.pid)
        evidence["idleWorkingSetMb"] = idle_memory
        if not args.skip_memory_budget:
            assert_memory_budget(idle_memory, args.note_count)

        tray_hwnd = find_tray_hwnd(process.pid)
        evidence["trayHwnd"] = tray_hwnd

        post_menu_command(tray_hwnd, MENU_SETTINGS)
        settings = wait_for(lambda: (assertion_probe(process.pid, "settings")))
        evidence["settingsWindow"] = settings
        settings_memory = working_set_mb(process.pid)
        evidence["settingsWorkingSetMb"] = settings_memory
        if not args.skip_memory_budget and settings_memory > 250.0:
            raise AssertionError(
                "Settings working set exceeds 250 MB budget: "
                f"{settings_memory:.1f} MB"
            )

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
    window = find_settings_window(pid) if mode == "settings" else find_note_window(pid)
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
