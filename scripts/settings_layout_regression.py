from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sticky_notes.model import AppSettings
from sticky_notes.platform.windows import enable_dpi_awareness
from sticky_notes.ui.settings_window import RoundedPanel, SettingsWindow, ThemeSelector
from scripts.capture_windows import visible_windows


BASE_TK_SCALING = 96 / 72
SCENARIOS = (
    {
        "name": "1920x1040-100pct",
        "work_area": (0, 0, 1920, 1040),
        "tk_scaling": BASE_TK_SCALING,
    },
    {
        "name": "1366x728-150pct",
        "work_area": (0, 0, 1366, 728),
        "tk_scaling": BASE_TK_SCALING * 1.5,
    },
    {
        "name": "1024x560-125pct",
        "work_area": (0, 0, 1024, 560),
        "tk_scaling": BASE_TK_SCALING * 1.25,
    },
    {
        "name": "800x560-100pct",
        "work_area": (0, 0, 800, 560),
        "tk_scaling": BASE_TK_SCALING,
    },
    {
        "name": "3840x2080-200pct",
        "work_area": (0, 0, 3840, 2080),
        "tk_scaling": BASE_TK_SCALING * 2,
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Settings across work-area, DPI, and language combinations."
    )
    parser.add_argument(
        "--capture-dir",
        type=Path,
        default=None,
        help="Optionally save visual evidence for representative scenarios.",
    )
    return parser.parse_args()


def _descendants(widget: tk.Misc) -> list[tk.Misc]:
    children: list[tk.Misc] = []
    for child in widget.winfo_children():
        children.append(child)
        children.extend(_descendants(child))
    return children


def _panel_overflow(panel: RoundedPanel) -> dict[str, int] | None:
    required = panel.content.winfo_reqheight() + panel._padding * 2
    actual = panel.winfo_height()
    if required <= actual + 1:
        return None
    return {"required": required, "actual": actual}


def _capture_settings_window(path: Path) -> None:
    windows = visible_windows(os.getpid())
    if len(windows) != 1:
        raise AssertionError(
            f"expected one visible Settings window for capture, got {len(windows)}"
        )
    hwnd, box = windows[0]
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
    flags = 0x0001 | 0x0002 | 0x0010 | 0x0040
    topmost = ctypes.c_void_p(-1)
    notopmost = ctypes.c_void_p(-2)
    if not user32.SetWindowPos(hwnd, topmost, 0, 0, 0, 0, flags):
        raise ctypes.WinError()
    try:
        time.sleep(0.08)
        path.parent.mkdir(parents=True, exist_ok=True)
        ImageGrab.grab(box, include_layered_windows=True).convert("RGB").save(path)
    finally:
        if not user32.SetWindowPos(hwnd, notopmost, 0, 0, 0, 0, flags):
            raise ctypes.WinError()


def _scenario(
    root: tk.Tk,
    spec: dict[str, object],
    language: str,
) -> dict[str, object]:
    root.tk.call("tk", "scaling", float(spec["tk_scaling"]))
    window = SettingsWindow(
        root,
        AppSettings(language=language),
        lambda _settings: True,
        lambda: None,
        lambda: None,
        work_area=tuple(spec["work_area"]),
    )
    pages: dict[str, object] = {}
    try:
        for page_name in ("general", "notes", "about"):
            window._show_page(page_name)
            window.update()
            descendants = _descendants(window._pages[page_name])
            panels = [child for child in descendants if isinstance(child, RoundedPanel)]
            clipped_panels = [
                overflow
                for panel in panels
                if (overflow := _panel_overflow(panel)) is not None
            ]
            selectors = [
                child for child in descendants if isinstance(child, ThemeSelector)
            ]
            horizontal_overflow = [
                {
                    "required": selector.winfo_reqwidth(),
                    "actual": selector.winfo_width(),
                }
                for selector in selectors
                if selector.winfo_reqwidth() > selector.winfo_width() + 1
            ]
            content_required = window._content_host.content.winfo_reqheight()
            viewport_height = window._content_host.canvas.winfo_height()
            missing_scrollbar = (
                content_required > viewport_height + 1
                and not window._content_host.overflow
            )
            if window._content_host.overflow:
                window._content_host.canvas.yview_moveto(1.0)
                window.update_idletasks()
                scroll_reaches_end = window._content_host.canvas.yview()[1] >= 0.999
            else:
                scroll_reaches_end = True
            pages[page_name] = {
                "clipped_panels": clipped_panels,
                "horizontal_overflow": horizontal_overflow,
                "scrollable": window._content_host.overflow,
                "missing_scrollbar": missing_scrollbar,
                "scroll_reaches_end": scroll_reaches_end,
            }
        left, top, right, bottom = spec["work_area"]
        if window.winfo_width() > right - left or window.winfo_height() > bottom - top:
            raise AssertionError(
                f"{spec['name']} window exceeds work area: "
                f"{window.winfo_width()}x{window.winfo_height()}"
            )
        return {
            "client": [window.winfo_width(), window.winfo_height()],
            "pages": pages,
        }
    finally:
        if window.winfo_exists():
            window.destroy()


def _capture_case(
    root: tk.Tk,
    spec: dict[str, object],
    language: str,
    page_name: str,
    capture_dir: Path,
) -> None:
    root.tk.call("tk", "scaling", float(spec["tk_scaling"]))
    window = SettingsWindow(
        root,
        AppSettings(language=language),
        lambda _settings: True,
        lambda: None,
        lambda: None,
        work_area=tuple(spec["work_area"]),
    )
    try:
        window._show_page(page_name)
        window.update()
        _capture_settings_window(
            capture_dir / f"{spec['name']}-{language}-{page_name}.png"
        )
    finally:
        if window.winfo_exists():
            window.destroy()
        root.update()


def main() -> int:
    args = parse_args()
    enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    evidence: dict[str, object] = {}
    try:
        for spec in SCENARIOS:
            for language in ("zh-CN", "en"):
                name = f"{spec['name']}-{language}"
                evidence[name] = _scenario(root, spec, language)
        failures = {
            name: {
                page: result
                for page, result in scenario["pages"].items()
                if (
                    result["clipped_panels"]
                    or result["horizontal_overflow"]
                    or result["missing_scrollbar"]
                    or not result["scroll_reaches_end"]
                )
            }
            for name, scenario in evidence.items()
        }
        failures = {name: pages for name, pages in failures.items() if pages}
        if failures:
            raise AssertionError(json.dumps(failures, ensure_ascii=False))
        if args.capture_dir is not None:
            capture_cases = (
                ("1920x1040-100pct", "zh-CN", "general"),
                ("1920x1040-100pct", "zh-CN", "notes"),
                ("1024x560-125pct", "zh-CN", "about"),
                ("800x560-100pct", "en", "notes"),
            )
            specs = {str(spec["name"]): spec for spec in SCENARIOS}
            for scenario_name, language, page_name in capture_cases:
                _capture_case(
                    root,
                    specs[scenario_name],
                    language,
                    page_name,
                    args.capture_dir,
                )
        print(json.dumps({"result": "passed", "scenarios": evidence}))
        return 0
    finally:
        root.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
