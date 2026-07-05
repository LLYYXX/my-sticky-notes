from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sticky_notes.controller import StickyNotesController
from sticky_notes.model import AppSettings, AppState, Note
from sticky_notes.store import StateStore
from sticky_notes.update_checker import DownloadedUpdate, UpdateResult


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        store = StateStore(Path(directory) / "state.json")
        store.save(AppState(notes=[Note(title="测试便签", x=80, y=80)]))
        controller = StickyNotesController(store)
        note = controller.state.notes[0]
        controller._open_note(note)
        controller.root.update()
        window = controller.windows[note.id]

        window.add_entry.delete(0, "end")
        window.add_entry.insert(0, "新增事项")
        window._add_todo()
        assert len(note.todos) == 1

        todo = note.todos[0]
        window._toggle_todo(todo.id, True)
        assert todo.completed is True
        window._edit_todo(todo.id, "编辑后的事项")
        assert todo.text == "编辑后的事项"

        window._change_title("编辑后的标题")
        window._toggle_pin()
        assert note.title == "编辑后的标题"
        assert note.pinned is True

        assert controller._save_settings(
            AppSettings(
                default_color="offwhite",
                notes_pinned=True,
                open_at_login=False,
                language="zh-CN",
            )
        )

        controller.open_settings()
        controller.root.update()
        assert controller.settings_window is not None
        settings_window = controller.settings_window
        assert "about" in settings_window._pages
        settings_window._show_page("about")
        assert settings_window._update_status_label.cget("text") == "尚未检查更新"
        settings_window._update_check = lambda: UpdateResult(
            current_version="0.2.0",
            latest_version="0.3.0",
            release_url=(
                "https://github.com/LLYYXX/my-sticky-notes/releases/tag/v0.3.0"
            ),
            update_available=True,
        )
        installed: list[DownloadedUpdate] = []
        settings_window._download_update = (
            lambda result, progress: DownloadedUpdate(
                result.latest_version,
                Path(directory) / "My Sticky Notes Setup 0.3.0.exe",
            )
        )
        settings_window._install_update = installed.append
        settings_window._start_update_check()
        deadline = time.monotonic() + 2.0
        while settings_window._update_checking and time.monotonic() < deadline:
            controller.root.update()
            time.sleep(0.01)
        assert not settings_window._update_checking
        assert len(installed) == 1
        assert settings_window._update_status_label.cget("text") == "安装程序已启动"
        settings_window._show_page("notes")
        settings_window._default_color.set("yellow")
        settings_window._commit()
        assert controller.state.settings.default_color == "yellow"
        assert note.color == "yellow"
        settings_window._default_color.set("offwhite")
        settings_window._commit()
        settings_window._language.set("en")
        settings_window._commit()
        controller.root.update()
        assert controller.state.settings.language == "en"
        settings_window._close()
        controller.root.update()
        assert controller.settings_window is None
        assert window.window.state() == "normal"
        assert controller.tray.is_registered

        second = controller.create_note(note)
        controller.root.update()
        assert len(controller.windows) == 2
        assert second.color == "offwhite"
        assert second.pinned is True
        controller.delete_note(second.id)
        controller.root.update()
        assert len(controller.windows) == 1

        window.window.geometry("300x240+50+60")
        controller.root.update_idletasks()
        window.update_geometry_model()
        assert note.width >= 300
        assert note.height >= 240

        controller.save_now()
        restored = store.load()
        restored_note = restored.notes[0]
        assert restored_note.title == "编辑后的标题"
        assert restored_note.pinned is True
        assert restored_note.todos[0].completed is True
        assert restored.settings.default_color == "offwhite"
        assert restored.settings.notes_pinned is True
        assert restored.settings.language == "en"
        controller.stop()

        print(
            json.dumps(
                {
                    "result": "passed",
                    "windows": 2,
                    "todo_add_edit_toggle": True,
                    "settings_defaults": True,
                    "pin_toggle": True,
                    "settings_live_save": True,
                    "verified_update_install": True,
                    "note_remains_visible": True,
                    "geometry_persisted": True,
                    "state_reloaded": True,
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
