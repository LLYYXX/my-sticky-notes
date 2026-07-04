from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes


MUTEX_NAME = r"Local\MyStickyNotes.Singleton"
SHOW_MESSAGE_NAME = "MyStickyNotes.ShowExisting"
ERROR_ALREADY_EXISTS = 183
HWND_BROADCAST = 0xFFFF


class SingleInstance:
    def __init__(self) -> None:
        self._handle = 0

    def acquire(self) -> bool:
        if sys.platform != "win32":
            return True
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.argtypes = [
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if not handle:
            raise ctypes.WinError()
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            self._handle = 0
            return False
        self._handle = int(handle)
        return True

    def signal_existing(self) -> None:
        if sys.platform != "win32":
            return
        user32 = ctypes.windll.user32
        message = user32.RegisterWindowMessageW(SHOW_MESSAGE_NAME)
        if message:
            user32.PostMessageW(HWND_BROADCAST, message, 0, 0)

    def close(self) -> None:
        if sys.platform != "win32" or not self._handle:
            return
        kernel32 = ctypes.windll.kernel32
        kernel32.CloseHandle(self._handle)
        self._handle = 0
