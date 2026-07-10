from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import time
from ctypes import wintypes
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assert that a second Tauri launch activates the first instance and exits."
    )
    parser.add_argument(
        "--exe",
        type=Path,
        default=Path("src-tauri/target/release/my-sticky-notes.exe"),
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path("qa/tauri-single-instance-state"),
    )
    return parser.parse_args()


def reset_state(path: Path) -> None:
    resolved = path.resolve()
    qa_root = Path.cwd().resolve() / "qa"
    if resolved == qa_root or qa_root not in resolved.parents:
        raise AssertionError(f"refusing to reset non-QA state dir: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def visible_tauri_windows(pid: int) -> list[int]:
    user32 = ctypes.windll.user32
    handles: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd: int, _lparam: int) -> bool:
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value != pid or not user32.IsWindowVisible(hwnd):
            return True
        class_name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_name, len(class_name))
        if class_name.value == "Tauri Window":
            handles.append(int(hwnd))
        return True

    user32.EnumWindows(callback_type(callback), 0)
    return handles


def wait_for(predicate, timeout: float = 5.0) -> object:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("timed out waiting for Tauri instance state")


def terminate(process: subprocess.Popen[object]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def main() -> int:
    args = parse_args()
    exe = args.exe.resolve()
    if not exe.exists():
        raise SystemExit(f"missing executable: {exe}")
    reset_state(args.state_dir)
    environment = os.environ.copy()
    environment["MY_STICKY_NOTES_DATA_DIR"] = str(args.state_dir.resolve())
    first = subprocess.Popen([str(exe)], env=environment)
    second: subprocess.Popen[object] | None = None
    evidence: dict[str, object] = {"firstPid": first.pid}
    try:
        first_windows = wait_for(lambda: visible_tauri_windows(first.pid))
        evidence["firstWindows"] = first_windows
        second = subprocess.Popen([str(exe)], env=environment)
        evidence["secondPid"] = second.pid
        wait_for(lambda: second.poll() is not None, timeout=4.0)
        evidence["secondExitCode"] = second.poll()
        surviving = visible_tauri_windows(first.pid)
        if not surviving:
            raise AssertionError("first instance did not remain visible after duplicate launch")
        evidence["firstWindowsAfterDuplicate"] = surviving
    finally:
        if second is not None:
            terminate(second)
        terminate(first)

    print(json.dumps({"result": "passed", "evidence": evidence}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
