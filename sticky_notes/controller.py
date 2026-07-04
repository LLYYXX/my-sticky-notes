from __future__ import annotations

import tkinter as tk
from dataclasses import replace
from pathlib import Path
from tkinter import messagebox

from .model import AppSettings, Note
from .platform.autostart import AutostartManager
from .platform.single_instance import SingleInstance
from .platform.tray import SystemTray
from .platform.windows import (
    bring_windows_to_front,
    clamp_geometry,
    top_right_geometry,
)
from .store import StateStore
from .ui.icons import IconSet
from .ui.note_window import NoteWindow
from .ui.settings_window import SettingsWindow


class StickyNotesController:
    def __init__(
        self,
        store: StateStore | None = None,
        *,
        launched_at_login: bool = False,
        instance: SingleInstance | None = None,
        system_integration: bool | None = None,
    ) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.option_add("*tearOff", False)
        self.store = store or StateStore()
        _ = launched_at_login  # Kept for command-line compatibility.
        self.instance = instance
        self.system_integration = (
            store is None if system_integration is None else system_integration
        )
        is_first_run = not self.store.path.exists()
        self.state = self.store.load()
        if is_first_run:
            note = self.state.ensure_note()
            note.x, note.y, note.width, note.height = self._top_right_geometry(
                note.width, note.height
            )

        tray_icon = (
            Path(__file__).resolve().parents[1]
            / "assets"
            / "icons"
            / "tray.ico"
        )
        try:
            self.root.iconbitmap(default=str(tray_icon))
        except tk.TclError:
            pass
        self.icons = IconSet(self.root)
        self.windows: dict[str, NoteWindow] = {}
        self.settings_window: SettingsWindow | None = None
        self._save_job: str | None = None
        self._tray_poll_job: str | None = None
        self._stopping = False
        self.autostart = AutostartManager()
        self._sync_autostart_from_settings()

        self.tray = SystemTray(tray_icon)
        self.tray.start()
        self._tray_poll_job = self.root.after(80, self._drain_tray_actions)
        self._update_tray_state()

    def run(self) -> None:
        self.state.ensure_note()
        for note in list(self.state.notes):
            self._open_note(note, visible=True)
        self._update_tray_state()
        self.root.mainloop()

    def create_note(self, source: Note | None = None) -> Note:
        if source is None:
            x, y, width, height = self._top_right_geometry(320, 360)
        else:
            x, y = source.x + 28, source.y + 28
            width, height = 320, 360
        settings = self.state.settings
        note = Note(
            title="新便签",
            color=settings.default_color,
            pinned=settings.new_notes_pinned,
            x=x,
            y=y,
            width=width,
            height=height,
        )
        self.state.notes.append(note)
        self._open_note(note, visible=True)
        self.schedule_save()
        self._update_tray_state()
        return note

    def delete_note(self, note_id: str) -> None:
        note = next((item for item in self.state.notes if item.id == note_id), None)
        if note is None:
            return
        if note.todos and not messagebox.askyesno(
            "删除便签",
            "这张便签里还有待办。确定删除吗？",
            parent=self.windows[note_id].window,
        ):
            return
        window = self.windows.pop(note_id, None)
        if window is not None:
            window.destroy()
        self.state.notes = [item for item in self.state.notes if item.id != note_id]
        if not self.state.notes:
            self.create_note()
        self.schedule_save()
        self._update_tray_state()

    def schedule_save(self) -> None:
        if self._stopping:
            return
        if self._save_job is not None:
            self.root.after_cancel(self._save_job)
        self._save_job = self.root.after(250, self.save_now)

    def save_now(self) -> None:
        self._save_job = None
        for window in list(self.windows.values()):
            window.update_geometry_model()
        self.store.save(self.state)

    def raise_notes(self) -> None:
        windows = list(self.windows.values())
        bring_windows_to_front(window.window for window in windows)
        for window in windows:
            window.sync_topmost()

    def activate_workspace(self) -> None:
        """Bring all notes forward while keeping Settings as the active window."""
        windows = list(self.windows.values())
        surfaces = [window.window for window in windows]
        settings = self.settings_window
        if settings is not None and settings.winfo_exists():
            surfaces.append(settings)
        bring_windows_to_front(surfaces)
        for window in windows:
            window.sync_topmost()

    def open_settings(self) -> None:
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.deiconify()
            self.settings_window.lift()
            self.settings_window.focus_force()
            return
        self.settings_window = SettingsWindow(
            self.root,
            replace(self.state.settings),
            self._save_settings,
            self._settings_closed,
            self.activate_workspace,
        )
        for window in self.windows.values():
            window.sync_topmost()
        self.settings_window.lift()
        self.settings_window.focus_force()

    def toggle_autostart(self) -> None:
        settings = replace(
            self.state.settings,
            open_at_login=not self.state.settings.open_at_login,
        )
        self._save_settings(settings)

    def stop(self) -> None:
        if self._stopping:
            return
        self._stopping = True
        if self._save_job is not None:
            self.root.after_cancel(self._save_job)
            self._save_job = None
        if self._tray_poll_job is not None:
            self.root.after_cancel(self._tray_poll_job)
            self._tray_poll_job = None
        try:
            for window in list(self.windows.values()):
                window.update_geometry_model()
            self.store.save(self.state)
        finally:
            if self.settings_window is not None and self.settings_window.winfo_exists():
                self.settings_window.destroy()
            for window in list(self.windows.values()):
                window.destroy()
            self.tray.stop()
            if self.instance is not None:
                self.instance.close()
            self.root.destroy()

    def _open_note(self, note: Note, *, visible: bool = True) -> None:
        fallback = (
            0,
            0,
            self.root.winfo_screenwidth(),
            self.root.winfo_screenheight(),
        )
        note.x, note.y, note.width, note.height = clamp_geometry(
            note.x,
            note.y,
            note.width,
            note.height,
            fallback,
        )
        window = NoteWindow(self, note, self.icons, visible=visible)
        self.windows[note.id] = window
        if visible:
            window.window.lift()

    def _top_right_geometry(
        self, width: int, height: int
    ) -> tuple[int, int, int, int]:
        fallback = (
            0,
            0,
            self.root.winfo_screenwidth(),
            self.root.winfo_screenheight(),
        )
        return top_right_geometry(width, height, fallback)

    def _save_settings(self, settings: AppSettings) -> bool:
        settings.normalize()
        if self.system_integration:
            try:
                self.autostart.set_enabled(settings.open_at_login)
                if self.autostart.is_enabled() != settings.open_at_login:
                    raise OSError("系统未接受开机启动设置")
            except OSError as exc:
                messagebox.showerror(
                    "无法更新开机启动",
                    str(exc),
                    parent=self.settings_window or self.root,
                )
                return False
        self.state.settings = settings
        self.save_now()
        self._update_tray_state()
        return True

    def _sync_autostart_from_settings(self) -> None:
        if not self.system_integration:
            return
        try:
            self.autostart.sync(self.state.settings.open_at_login)
        except OSError:
            self.state.settings.open_at_login = self.autostart.is_enabled()

    def _settings_closed(self) -> None:
        self.settings_window = None
        for window in self.windows.values():
            window.sync_topmost()

    def _update_tray_state(self) -> None:
        if not hasattr(self, "tray"):
            return
        self.tray.update_state(
            open_at_login=self.state.settings.open_at_login,
        )

    def _drain_tray_actions(self) -> None:
        if self._stopping:
            return
        for action in self.tray.pop_actions():
            if action == "show":
                self.raise_notes()
            elif action == "new":
                self.create_note()
            elif action == "settings":
                self.open_settings()
            elif action == "autostart":
                self.toggle_autostart()
            elif action == "exit":
                self.stop()
                return
        self._tray_poll_job = self.root.after(80, self._drain_tray_actions)
