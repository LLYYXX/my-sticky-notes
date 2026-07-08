from __future__ import annotations

import ctypes
import json
import os
import sys
import tempfile
from ctypes import wintypes
from pathlib import Path

from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.capture_windows import enable_dpi_awareness, visible_windows
from sticky_notes.controller import StickyNotesController
from sticky_notes.platform.windows import (
    GWL_EXSTYLE,
    WS_EX_APPWINDOW,
    WS_EX_TOOLWINDOW,
)
from sticky_notes.store import StateStore


def longest_true_run(values: list[bool]) -> int:
    longest = 0
    current = 0
    for value in values:
        current = current + 1 if value else 0
        longest = max(longest, current)
    return longest


def primary_work_area() -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    spi_getworkarea = 0x0030
    if not ctypes.windll.user32.SystemParametersInfoW(
        spi_getworkarea, 0, ctypes.byref(rect), 0
    ):
        raise ctypes.WinError()
    return rect.left, rect.top, rect.right, rect.bottom


def main() -> int:
    enable_dpi_awareness()
    failures: list[str] = []
    evidence: dict[str, object] = {}
    get_window_style = ctypes.windll.user32.GetWindowLongPtrW
    get_window_style.argtypes = [wintypes.HWND, ctypes.c_int]
    get_window_style.restype = ctypes.c_ssize_t

    with tempfile.TemporaryDirectory() as directory:
        store = StateStore(Path(directory) / "state.json")
        controller = StickyNotesController(store)
        note = controller.state.notes[0]
        controller._open_note(note)
        controller.root.update()
        window = controller.windows[note.id]

        controller.raise_notes()
        controller.root.update()
        unpinned_topmost = bool(window.window.wm_attributes("-topmost"))
        evidence["unpinned_stays_unpinned_after_raise"] = not unpinned_topmost
        if unpinned_topmost:
            failures.append("raising notes permanently pinned an unpinned note")

        note.pinned = True
        window.sync_topmost()
        controller.raise_notes()
        controller.root.update()
        pinned_topmost = bool(window.window.wm_attributes("-topmost"))
        evidence["pinned_stays_pinned_after_raise"] = pinned_topmost
        if not pinned_topmost:
            failures.append("raising notes unpinned a pinned note")
        note.pinned = False
        window.sync_topmost()

        windows = visible_windows(os.getpid())
        if len(windows) != 1:
            failures.append(f"expected one visible note window, got {len(windows)}")
        else:
            hwnd, box = windows[0]
            image = ImageGrab.grab(box, include_layered_windows=True).convert("RGB")
            artifact_path = (
                Path(__file__).resolve().parents[1]
                / "qa"
                / "desktop-regression-current.png"
            )
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(artifact_path)
            evidence["capture"] = str(artifact_path)
            bottom_y = image.height - 1
            dark_fraction = sum(
                1
                for x in range(image.width)
                if max(image.getpixel((x, bottom_y))) < 70
            ) / image.width
            evidence["bottom_dark_fraction"] = round(dark_fraction, 4)
            if dark_fraction >= 0.25:
                failures.append(
                    f"unexpected dark bottom border: {dark_fraction:.1%} of bottom row"
                )
            bottom_max_dark_run = max(
                longest_true_run(
                    [
                        max(image.getpixel((x, y))) < 100
                        for x in range(image.width)
                    ]
                )
                for y in range(max(0, image.height - 8), image.height)
            )
            evidence["bottom_max_dark_run"] = bottom_max_dark_run
            if bottom_max_dark_run > 8:
                failures.append(
                    "resize grip contains a horizontal bottom edge "
                    f"({bottom_max_dark_run}px run)"
                )

            work_left, work_top, work_right, _work_bottom = primary_work_area()
            left, top, right, _bottom = box
            right_gap = work_right - right
            top_gap = top - work_top
            evidence["default_right_gap"] = right_gap
            evidence["default_top_gap"] = top_gap
            if not (8 <= right_gap <= 40 and 8 <= top_gap <= 40):
                failures.append(
                    "default note is not at the screen's top-right "
                    f"(right gap={right_gap}, top gap={top_gap})"
                )

            note_style = get_window_style(hwnd, GWL_EXSTYLE)
            evidence["note_has_toolwindow_style"] = bool(
                note_style & WS_EX_TOOLWINDOW
            )
            evidence["note_has_appwindow_style"] = bool(
                note_style & WS_EX_APPWINDOW
            )
            if not (note_style & WS_EX_TOOLWINDOW) or (
                note_style & WS_EX_APPWINDOW
            ):
                failures.append("note window is still represented in the taskbar")

            window.hide()
            controller.root.update()
            hidden_windows = visible_windows(os.getpid())
            evidence["single_note_hidden_from_desktop"] = not hidden_windows
            if hidden_windows:
                failures.append("minimized note remained visible on the desktop")
            controller.raise_notes()
            controller.root.update()
            restored_windows = visible_windows(os.getpid())
            evidence["tray_restore_returns_hidden_note"] = (
                len(restored_windows) == 1 and restored_windows[0][0] == hwnd
            )
            if len(restored_windows) != 1 or restored_windows[0][0] != hwnd:
                failures.append("show action did not restore the hidden note")

            controller.open_settings()
            controller.root.update()
            settings_windows = [
                item for item in visible_windows(os.getpid()) if item[0] != hwnd
            ]
            if len(settings_windows) != 1:
                failures.append(
                    "opening Settings did not create exactly one normal window"
                )
            else:
                settings_hwnd, _settings_box = settings_windows[0]
                settings_style = get_window_style(settings_hwnd, GWL_EXSTYLE)
                evidence["settings_has_appwindow_style"] = bool(
                    settings_style & WS_EX_APPWINDOW
                )
                evidence["settings_has_toolwindow_style"] = bool(
                    settings_style & WS_EX_TOOLWINDOW
                )
                if not (settings_style & WS_EX_APPWINDOW) or (
                    settings_style & WS_EX_TOOLWINDOW
                ):
                    failures.append("Settings is missing its taskbar representation")

            tray = getattr(controller, "tray", None)
            tray_registered = bool(
                tray is not None and getattr(tray, "is_registered", False)
            )
            evidence["tray_registered"] = tray_registered
            if not tray_registered:
                failures.append("notification-area icon was not registered")

            assert controller.settings_window is not None
            controller.settings_window._close()
            controller.root.update()
            remaining = visible_windows(os.getpid())
            evidence["visible_windows_after_settings_close"] = len(remaining)
            if len(remaining) != 1 or remaining[0][0] != hwnd:
                failures.append(
                    "closing Settings did not return to one taskbar-free note"
                )

        controller.stop()

    result = {
        "result": "failed" if failures else "passed",
        "failures": failures,
        "evidence": evidence,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
