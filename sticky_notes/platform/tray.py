from __future__ import annotations

import ctypes
import queue
import sys
import threading
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

from ..i18n import DEFAULT_LANGUAGE, tr
from .single_instance import SHOW_MESSAGE_NAME


WM_APP = 0x8000
WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WM_NULL = 0x0000
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_CONTEXTMENU = 0x007B

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040
IDI_APPLICATION = 32512

MF_STRING = 0x0000
MF_SEPARATOR = 0x0800
MF_CHECKED = 0x0008
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100
TPM_NONOTIFY = 0x0080

CMD_NEW = 1
CMD_SETTINGS = 2
CMD_AUTOSTART = 3
CMD_EXIT = 4
TRAY_ICON_ID = 1
TRAY_CALLBACK_MESSAGE = WM_APP + 1
LEFT_CLICK_ACTION = "show"


@dataclass(frozen=True, slots=True)
class TrayMenuItem:
    label: str
    action: str | None = None
    checked: bool = False
    separator: bool = False


def build_tray_menu_spec(
    *,
    open_at_login: bool,
    language: str = DEFAULT_LANGUAGE,
) -> list[TrayMenuItem]:
    return [
        TrayMenuItem(tr("tray_new", language), "new"),
        TrayMenuItem("", separator=True),
        TrayMenuItem(tr("tray_settings", language), "settings"),
        TrayMenuItem(
            tr("tray_autostart", language),
            "autostart",
            checked=open_at_login,
        ),
        TrayMenuItem("", separator=True),
        TrayMenuItem(tr("tray_exit", language), "exit"),
    ]


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]


WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


def _configure_win32_api() -> tuple[object, object, object]:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    shell32 = ctypes.windll.shell32

    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE

    user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterWindowMessageW.restype = wintypes.UINT
    user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    user32.RegisterClassW.restype = wintypes.WORD
    user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
    user32.UnregisterClassW.restype = wintypes.BOOL
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        wintypes.HANDLE,
        wintypes.HINSTANCE,
        wintypes.LPVOID,
    ]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.DefWindowProcW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.DefWindowProcW.restype = ctypes.c_ssize_t
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.DestroyWindow.restype = wintypes.BOOL
    user32.PostMessageW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.PostMessageW.restype = wintypes.BOOL
    user32.GetMessageW.argtypes = [
        ctypes.POINTER(wintypes.MSG),
        wintypes.HWND,
        wintypes.UINT,
        wintypes.UINT,
    ]
    user32.GetMessageW.restype = ctypes.c_int
    user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.TranslateMessage.restype = wintypes.BOOL
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.DispatchMessageW.restype = ctypes.c_ssize_t
    user32.PostQuitMessage.argtypes = [ctypes.c_int]
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.LoadImageW.argtypes = [
        wintypes.HINSTANCE,
        wintypes.LPCWSTR,
        wintypes.UINT,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.LoadIconW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
    user32.LoadIconW.restype = wintypes.HICON
    user32.DestroyIcon.argtypes = [wintypes.HICON]
    user32.DestroyIcon.restype = wintypes.BOOL
    user32.CreatePopupMenu.restype = wintypes.HANDLE
    user32.AppendMenuW.argtypes = [
        wintypes.HANDLE,
        wintypes.UINT,
        ctypes.c_size_t,
        wintypes.LPCWSTR,
    ]
    user32.AppendMenuW.restype = wintypes.BOOL
    user32.TrackPopupMenu.argtypes = [
        wintypes.HANDLE,
        wintypes.UINT,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        wintypes.LPCVOID,
    ]
    user32.TrackPopupMenu.restype = wintypes.UINT
    user32.DestroyMenu.argtypes = [wintypes.HANDLE]
    user32.DestroyMenu.restype = wintypes.BOOL

    shell32.Shell_NotifyIconW.argtypes = [
        wintypes.DWORD,
        ctypes.POINTER(NOTIFYICONDATAW),
    ]
    shell32.Shell_NotifyIconW.restype = wintypes.BOOL
    return user32, kernel32, shell32


class SystemTray:
    """Small Win32 notification-area host with no runtime dependencies."""

    def __init__(self, icon_path: Path | None = None) -> None:
        self.icon_path = icon_path
        self._actions: queue.SimpleQueue[str] = queue.SimpleQueue()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._hwnd = 0
        self._hicon = 0
        self._owns_icon = False
        self._registered = False
        self.error: str | None = None
        self._wndproc: object | None = None
        self._taskbar_created = 0
        self._show_existing_message = 0
        self._state_lock = threading.Lock()
        self._open_at_login = False
        self._language = DEFAULT_LANGUAGE

    @property
    def is_registered(self) -> bool:
        return self._registered

    def start(self) -> bool:
        if sys.platform != "win32":
            return False
        if self._thread is not None and self._thread.is_alive():
            return self._registered
        self._ready.clear()
        self.error = None
        self._thread = threading.Thread(
            target=self._message_loop,
            name="sticky-notes-tray",
            daemon=True,
        )
        self._thread.start()
        self._ready.wait(timeout=2.0)
        return self._registered

    def stop(self) -> None:
        if sys.platform != "win32":
            return
        hwnd = self._hwnd
        if hwnd:
            ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self._thread = None

    def pop_actions(self) -> list[str]:
        actions: list[str] = []
        while True:
            try:
                actions.append(self._actions.get_nowait())
            except queue.Empty:
                return actions

    def update_state(
        self,
        *,
        open_at_login: bool,
        language: str = DEFAULT_LANGUAGE,
    ) -> None:
        with self._state_lock:
            self._open_at_login = open_at_login
            self._language = language
        if self._hwnd and self._registered:
            data = self._notify_data()
            ctypes.windll.shell32.Shell_NotifyIconW(
                NIM_MODIFY, ctypes.byref(data)
            )

    def _message_loop(self) -> None:
        try:
            self._run_message_loop()
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            self._registered = False
            self._ready.set()

    def _run_message_loop(self) -> None:
        user32, kernel32, _shell32 = _configure_win32_api()
        class_name = f"MyStickyNotesTray_{id(self):x}"
        hinstance = kernel32.GetModuleHandleW(None)
        self._taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")
        self._show_existing_message = user32.RegisterWindowMessageW(
            SHOW_MESSAGE_NAME
        )
        skip_next_left_up = False

        def window_proc(hwnd: int, message: int, wparam: int, lparam: int) -> int:
            nonlocal skip_next_left_up
            if message == TRAY_CALLBACK_MESSAGE:
                event = int(lparam) & 0xFFFF
                if event == WM_LBUTTONUP:
                    if skip_next_left_up:
                        skip_next_left_up = False
                    else:
                        self._actions.put(LEFT_CLICK_ACTION)
                    return 0
                if event == WM_LBUTTONDBLCLK:
                    skip_next_left_up = True
                    self._actions.put("settings")
                    return 0
                if event in (WM_RBUTTONUP, WM_CONTEXTMENU):
                    self._show_menu(hwnd)
                    return 0
            if message == self._taskbar_created:
                self._add_icon()
                return 0
            if message == self._show_existing_message:
                self._actions.put("show")
                return 0
            if message == WM_CLOSE:
                user32.DestroyWindow(hwnd)
                return 0
            if message == WM_DESTROY:
                self._remove_icon()
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, message, wparam, lparam)

        self._wndproc = WNDPROC(window_proc)
        window_class = WNDCLASSW()
        window_class.lpfnWndProc = self._wndproc
        window_class.hInstance = hinstance
        window_class.lpszClassName = class_name
        if not user32.RegisterClassW(ctypes.byref(window_class)):
            self._ready.set()
            return

        hwnd = user32.CreateWindowExW(
            0,
            class_name,
            "My Sticky Notes",
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            hinstance,
            None,
        )
        if not hwnd:
            user32.UnregisterClassW(class_name, hinstance)
            self._ready.set()
            return

        self._hwnd = int(hwnd)
        self._load_icon()
        self._add_icon()
        self._ready.set()

        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), 0, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))

        self._remove_icon()
        if self._hicon and self._owns_icon:
            user32.DestroyIcon(self._hicon)
        self._hicon = 0
        self._hwnd = 0
        self._wndproc = None
        user32.UnregisterClassW(class_name, hinstance)

    def _load_icon(self) -> None:
        user32 = ctypes.windll.user32
        if self.icon_path is not None and self.icon_path.exists():
            icon = user32.LoadImageW(
                0,
                str(self.icon_path),
                IMAGE_ICON,
                0,
                0,
                LR_LOADFROMFILE | LR_DEFAULTSIZE,
            )
            if icon:
                self._hicon = int(icon)
                self._owns_icon = True
                return
        self._hicon = int(
            user32.LoadIconW(None, ctypes.c_void_p(IDI_APPLICATION)) or 0
        )

    def _notify_data(self) -> NOTIFYICONDATAW:
        data = NOTIFYICONDATAW()
        data.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        data.hWnd = self._hwnd
        data.uID = TRAY_ICON_ID
        data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        data.uCallbackMessage = TRAY_CALLBACK_MESSAGE
        data.hIcon = self._hicon
        with self._state_lock:
            data.szTip = tr("app_name", self._language)
        return data

    def _add_icon(self) -> None:
        if not self._hwnd or not self._hicon:
            self._registered = False
            return
        data = self._notify_data()
        self._registered = bool(
            ctypes.windll.shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(data))
        )

    def _remove_icon(self) -> None:
        if self._hwnd:
            data = self._notify_data()
            ctypes.windll.shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(data))
        self._registered = False

    def _show_menu(self, hwnd: int) -> None:
        user32 = ctypes.windll.user32
        menu = user32.CreatePopupMenu()
        if not menu:
            return
        try:
            with self._state_lock:
                items = build_tray_menu_spec(
                    open_at_login=self._open_at_login,
                    language=self._language,
                )
            action_commands = {
                "new": CMD_NEW,
                "settings": CMD_SETTINGS,
                "autostart": CMD_AUTOSTART,
                "exit": CMD_EXIT,
            }
            command_actions = {
                command: action for action, command in action_commands.items()
            }
            for item in items:
                if item.separator:
                    user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
                    continue
                flags = MF_STRING | (MF_CHECKED if item.checked else 0)
                command_id = action_commands[item.action or ""]
                user32.AppendMenuW(menu, flags, command_id, item.label)
            point = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(point))
            user32.SetForegroundWindow(hwnd)
            command = user32.TrackPopupMenu(
                menu,
                TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY,
                point.x,
                point.y,
                0,
                hwnd,
                None,
            )
            action = command_actions.get(int(command))
            if action:
                self._actions.put(action)
            user32.PostMessageW(hwnd, WM_NULL, 0, 0)
        finally:
            user32.DestroyMenu(menu)
