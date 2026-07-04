from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Protocol

if sys.platform == "win32":
    import winreg


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


class AutostartBackend(Protocol):
    def read(self, name: str) -> str | None: ...

    def write(self, name: str, command: str) -> None: ...

    def delete(self, name: str) -> None: ...


class WindowsRunKeyBackend:
    def read(self, name: str) -> str | None:
        if sys.platform != "win32":
            return None
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                value, _value_type = winreg.QueryValueEx(key, name)
        except FileNotFoundError:
            return None
        return str(value)

    def write(self, name: str, command: str) -> None:
        if sys.platform != "win32":
            return
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)

    def delete(self, name: str) -> None:
        if sys.platform != "win32":
            return
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                RUN_KEY,
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                winreg.DeleteValue(key, name)
        except FileNotFoundError:
            pass


class AutostartManager:
    entry_name = "MyStickyNotes"

    def __init__(
        self,
        *,
        backend: AutostartBackend | None = None,
        command: str | None = None,
    ) -> None:
        self.backend = backend or WindowsRunKeyBackend()
        self.command = command or self.current_command()

    @staticmethod
    def current_command() -> str:
        if getattr(sys, "frozen", False):
            parts = [str(Path(sys.executable).resolve()), "--autostart"]
        else:
            executable = Path(sys.executable).resolve()
            pythonw = executable.with_name("pythonw.exe")
            if pythonw.exists():
                executable = pythonw
            app_path = Path(__file__).resolve().parents[2] / "app.py"
            parts = [str(executable), str(app_path), "--autostart"]
        return subprocess.list2cmdline(parts)

    def is_enabled(self) -> bool:
        return self.backend.read(self.entry_name) == self.command

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            self.backend.write(self.entry_name, self.command)
        else:
            self.backend.delete(self.entry_name)

    def sync(self, enabled: bool) -> bool:
        current_value = self.backend.read(self.entry_name)
        if enabled and current_value != self.command:
            self.backend.write(self.entry_name, self.command)
        elif not enabled and current_value is not None:
            self.backend.delete(self.entry_name)
        return self.is_enabled()
