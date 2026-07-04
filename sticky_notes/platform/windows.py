from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from typing import Iterable


MIN_WIDTH = 260
MIN_HEIGHT = 210

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_SHOWWINDOW = 0x0040
SW_SHOWNORMAL = 1
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_BORDER_COLOR = 34
DWMWA_COLOR_NONE = 0xFFFFFFFE


def enable_dpi_awareness() -> None:
    """Keep Win32 work-area coordinates and Tk geometry in the same pixel space."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def _wrapper_handle(window: object) -> int:
    window.update_idletasks()
    child = int(window.winfo_id())
    if sys.platform != "win32":
        return child
    return int(ctypes.windll.user32.GetParent(child) or child)


def taskbar_extended_style(style: int, *, visible: bool) -> int:
    """Return the Win32 extended style for a normal or overlay window."""
    if visible:
        return (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
    return (style & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW


def set_taskbar_visibility(window: object, *, visible: bool) -> None:
    if sys.platform != "win32":
        return
    try:
        hwnd = _wrapper_handle(window)
        user32 = ctypes.windll.user32
        get_style = user32.GetWindowLongPtrW
        set_style = user32.SetWindowLongPtrW
        get_style.argtypes = [wintypes.HWND, ctypes.c_int]
        get_style.restype = ctypes.c_ssize_t
        set_style.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        set_style.restype = ctypes.c_ssize_t
        style = taskbar_extended_style(
            get_style(hwnd, GWL_EXSTYLE), visible=visible
        )
        set_style(hwnd, GWL_EXSTYLE, style)
        user32.SetWindowPos(
            hwnd,
            0,
            0,
            0,
            0,
            0,
            SWP_NOMOVE
            | SWP_NOSIZE
            | SWP_NOZORDER
            | SWP_NOACTIVATE
            | SWP_FRAMECHANGED,
        )
    except (AttributeError, OSError, ValueError):
        return


def bring_windows_to_front(windows: Iterable[object]) -> None:
    """Raise a group of Tk windows without changing their lasting pin state."""
    active = [window for window in windows if window.winfo_exists()]
    if not active:
        return

    for window in active:
        window.deiconify()
        window.update_idletasks()

    if sys.platform != "win32":
        for window in active:
            window.lift()
        active[-1].focus_force()
        return

    try:
        user32 = ctypes.windll.user32
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.ShowWindow.restype = wintypes.BOOL
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
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.SetForegroundWindow.restype = wintypes.BOOL
        handles = [_wrapper_handle(window) for window in active]
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW

        # A short topmost pulse lifts the entire group above unrelated apps.
        # Callers restore each note's real pinned state immediately afterwards.
        for hwnd in handles:
            user32.ShowWindow(hwnd, SW_SHOWNORMAL)
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
        for hwnd in handles:
            user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)
        user32.SetForegroundWindow(handles[-1])
    except (AttributeError, OSError, ValueError):
        for window in active:
            window.lift()
        active[-1].focus_force()


def apply_note_window_style(window: object) -> None:
    """Make a note a taskbar-free desktop overlay with its own light border."""
    if sys.platform != "win32":
        return
    try:
        set_taskbar_visibility(window, visible=False)
        hwnd = _wrapper_handle(window)
        dwmapi = ctypes.windll.dwmapi
        preference = ctypes.c_int(2)
        dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(preference),
            ctypes.sizeof(preference),
        )
        border_color = ctypes.c_uint(DWMWA_COLOR_NONE)
        dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_BORDER_COLOR,
            ctypes.byref(border_color),
            ctypes.sizeof(border_color),
        )
    except (AttributeError, OSError, ValueError):
        return


def _monitor_work_areas() -> list[tuple[int, int, int, int]]:
    if sys.platform != "win32":
        return []

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    areas: list[tuple[bool, tuple[int, int, int, int]]] = []
    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HMONITOR,
        wintypes.HDC,
        ctypes.POINTER(RECT),
        wintypes.LPARAM,
    )

    def callback(monitor: int, _dc: int, _rect: object, _data: int) -> bool:
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if ctypes.windll.user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            rect = info.rcWork
            areas.append(
                (
                    bool(info.dwFlags & 1),
                    (rect.left, rect.top, rect.right, rect.bottom),
                )
            )
        return True

    ctypes.windll.user32.EnumDisplayMonitors(0, 0, callback_type(callback), 0)
    areas.sort(key=lambda item: not item[0])
    return [area for _is_primary, area in areas]


def top_right_geometry(
    width: int,
    height: int,
    fallback_area: Iterable[int],
    *,
    margin: int = 16,
) -> tuple[int, int, int, int]:
    """Place a new note inside the primary monitor's top-right work area."""
    areas = _monitor_work_areas() or [tuple(fallback_area)]
    left, top, right, bottom = areas[0]
    width = min(max(MIN_WIDTH, width), right - left)
    height = min(max(MIN_HEIGHT, height), bottom - top)
    x = max(left, right - width - margin)
    y = min(max(top + margin, top), bottom - height)
    return x, y, width, height


def clamp_geometry(
    x: int,
    y: int,
    width: int,
    height: int,
    fallback_area: Iterable[int],
) -> tuple[int, int, int, int]:
    width = max(MIN_WIDTH, width)
    height = max(MIN_HEIGHT, height)
    areas = _monitor_work_areas() or [tuple(fallback_area)]

    def visible_area(area: tuple[int, int, int, int]) -> int:
        left, top, right, bottom = area
        overlap_w = max(0, min(x + width, right) - max(x, left))
        overlap_h = max(0, min(y + height, bottom) - max(y, top))
        return overlap_w * overlap_h

    target = max(areas, key=visible_area)
    left, top, right, bottom = target
    width = min(width, max(MIN_WIDTH, right - left))
    height = min(height, max(MIN_HEIGHT, bottom - top))
    if visible_area(target) < 48 * 48:
        x = left + 24
        y = top + 24
    x = min(max(x, left), right - 64)
    y = min(max(y, top), bottom - 48)
    return x, y, width, height
