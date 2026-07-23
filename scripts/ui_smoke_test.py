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
        assert not hasattr(window.title_bar, "title_label")
        window.title_bar.color_picker._toggle_popup()
        controller.root.update()
        palette = window.title_bar.color_picker._popup
        assert palette is not None and palette.winfo_exists()
        assert len(palette.winfo_children()[0].winfo_children()) == 9
        window.title_bar.color_picker.close_popup()

        def create_with_enter(text: str) -> None:
            entry = window.todo_list.add_entry
            assert entry is not None
            entry.focus_force()
            controller.root.update()
            entry.insert(0, text)
            entry.event_generate("<Return>")
            controller.root.update()

        create_with_enter("new item")
        assert len(note.todos) == 1

        create_with_enter("long todo item " * 16)
        controller.root.update_idletasks()
        long_row = window.todo_list.content.winfo_children()[1]
        long_label = next(
            child
            for child in long_row.winfo_children()
            if child.winfo_class() == "Label" and child.cget("text").startswith("long todo")
        )
        assert long_label.winfo_height() > 20
        assert window.todo_list.add_entry.winfo_rooty() > (
            long_label.winfo_rooty() + long_label.winfo_height()
        )

        first_id = note.todos[0].id
        first_row = window.todo_list._row_widgets[0][1]
        last_row = window.todo_list._row_widgets[-1][1]
        first_label = next(
            child
            for child in first_row.winfo_children()
            if child.winfo_class() == "Label"
        )
        drag_y = (
            last_row.winfo_rooty()
            + last_row.winfo_height()
            + 8
            - first_label.winfo_rooty()
        )
        first_label.event_generate("<ButtonPress-1>", x=4, y=4)
        first_label.event_generate("<B1-Motion>", x=4, y=drag_y)
        deadline = time.monotonic() + 0.2
        while (
            window.todo_list._drag._ghost is None
            and time.monotonic() < deadline
        ):
            controller.root.update()
            time.sleep(0.005)
        assert window.todo_list._drag._ghost is not None
        assert window.todo_list._drag._ghost.winfo_ismapped()
        first_label.event_generate("<ButtonRelease-1>", x=4, y=drag_y)
        controller.root.update_idletasks()
        assert note.todos[-1].id == first_id

        edited_todo = note.todos[0]
        edited_row = next(
            row
            for todo_id, row in window.todo_list._row_widgets
            if todo_id == edited_todo.id
        )
        window.todo_list._begin_edit(edited_todo.id)
        editing_entry = window.todo_list._active_entry
        assert editing_entry is not None
        editing_entry.delete(0, "end")
        editing_entry.insert(0, "saved by blank click")
        window.todo_list.canvas.event_generate("<Button-1>", x=4, y=4)
        controller.root.update()
        assert edited_todo.text == "saved by blank click"
        assert window.window.focus_get() is window.todo_list.canvas

        switch_todo = note.todos[0]
        window.todo_list._begin_edit(switch_todo.id)
        switch_editor = window.todo_list._active_entry
        switch_placeholder = window.todo_list._placeholder_label
        assert switch_editor is not None and switch_placeholder is not None
        switch_editor.delete(0, "end")
        switch_editor.insert(0, "saved before switching input")
        switch_placeholder.event_generate("<Button-1>", x=2, y=2)
        controller.root.update()
        controller.root.update()
        assert switch_todo.text == "saved before switching input"
        assert window.todo_list.input_session.mode.name == "CREATING"
        assert window.window.focus_get() is window.todo_list.add_entry
        window.todo_list.cancel_active_input()
        controller.root.update()

        add_entry = window.todo_list.add_entry
        assert add_entry is not None
        add_entry.focus_force()
        controller.root.update()
        add_entry.insert(0, "created by blank click")
        window.todo_list.canvas.event_generate("<Button-1>", x=4, y=4)
        controller.root.update()
        assert note.todos[-1].text == "created by blank click"

        empty_entry = window.todo_list.add_entry
        assert empty_entry is not None
        empty_entry.focus_force()
        controller.root.update()
        empty_entry.event_generate("<Return>")
        controller.root.update()
        assert not window.todo_list.input_session.is_active
        assert window.window.focus_get() is window.todo_list.canvas

        draft_entry = window.todo_list.add_entry
        assert draft_entry is not None
        draft_entry.focus_force()
        controller.root.update()
        draft_entry.insert(0, "draft survives render")
        window.todo_list.render(
            note.todos,
            window.todo_list.theme,
            window.todo_list.placeholder,
        )
        controller.root.update()
        assert window.todo_list.input_session.draft == "draft survives render"
        assert window.todo_list.add_entry.get() == "draft survives render"
        window.todo_list.canvas.event_generate("<Button-1>", x=4, y=4)
        controller.root.update()
        assert note.todos[-1].text == "draft survives render"

        escape_entry = window.todo_list.add_entry
        assert escape_entry is not None
        escape_entry.focus_force()
        controller.root.update()
        escape_entry.event_generate("<Escape>")
        controller.root.update()
        assert not window.todo_list.input_session.is_active
        assert window.window.focus_get() is window.todo_list.canvas

        drag_commit_entry = window.todo_list.add_entry
        assert drag_commit_entry is not None
        drag_commit_entry.focus_force()
        controller.root.update()
        drag_commit_entry.insert(0, "committed before drag")
        drag_source_row = window.todo_list._row_widgets[0][1]
        drag_target_row = window.todo_list._row_widgets[-1][1]
        drag_source_label = next(
            child
            for child in drag_source_row.winfo_children()
            if child.winfo_class() == "Label"
        )
        drag_to_y = (
            drag_target_row.winfo_rooty()
            + drag_target_row.winfo_height()
            - drag_source_label.winfo_rooty()
        )
        drag_source_label.event_generate("<ButtonPress-1>", x=4, y=4)
        drag_source_label.event_generate("<B1-Motion>", x=4, y=drag_to_y)
        controller.root.update()
        assert window.todo_list._drag.active
        drag_source_label.event_generate("<ButtonRelease-1>", x=4, y=drag_to_y)
        controller.root.update()
        assert any(todo.text == "committed before drag" for todo in note.todos)

        todo = note.todos[0]
        window._toggle_todo(todo.id, True)
        assert todo.completed is True
        window._edit_todo(todo.id, "编辑后的事项")
        assert todo.text == "编辑后的事项"

        color_entry = window.todo_list.add_entry
        assert color_entry is not None
        color_entry.focus_force()
        controller.root.update()
        color_entry.insert(0, "committed before color")
        window.title_bar.color_picker._select("navy")
        controller.root.update()
        assert note.color == "navy"

        pin_entry = window.todo_list.add_entry
        assert pin_entry is not None
        pin_entry.focus_force()
        controller.root.update()
        pin_entry.insert(0, "committed before pin")
        window.title_bar.pin_button.invoke()
        controller.root.update()
        assert note.pinned is True
        assert any(todo.text == "committed before pin" for todo in note.todos)

        assert controller._save_settings(
            AppSettings(
                open_at_login=False,
                language="zh-CN",
            )
        )

        controller.open_settings()
        controller.root.update()
        assert controller.settings_window is not None
        settings_window = controller.settings_window
        assert "notes" not in settings_window._pages
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
        assert second.color == "yellow"
        assert second.pinned is False
        controller.delete_note(second.id)
        controller.root.update()
        assert len(controller.windows) == 1

        window._toggle_collapsed()
        controller.root.update()
        assert note.collapsed is True
        assert window.window.winfo_height() < 100
        window._toggle_collapsed()
        controller.root.update()
        assert note.collapsed is False
        assert window.window.winfo_height() >= 210

        window.window.geometry("300x240+50+60")
        controller.root.update_idletasks()
        window.update_geometry_model()
        assert note.width >= 300
        assert note.height >= 240

        controller.save_now()
        restored = store.load()
        restored_note = restored.notes[0]
        assert restored_note.color == "navy"
        assert restored_note.pinned is True
        assert restored_note.todos[0].completed is True
        assert restored.settings.language == "en"
        controller.stop()

        print(
            json.dumps(
                {
                    "result": "passed",
                    "windows": 2,
                    "todo_add_edit_toggle": True,
                    "todo_wrap_and_inline_input": True,
                    "todo_drag_reorder": True,
                    "todo_drag_visual": True,
                    "blank_click_commits_edit": True,
                    "blank_click_creates_todo": True,
                    "blank_click_focuses_note": True,
                    "input_switch_commits_and_continues": True,
                    "empty_submit_and_cancel_are_coherent": True,
                    "draft_survives_render": True,
                    "first_drag_commits_and_continues": True,
                    "title_actions_commit_input": True,
                    "per_note_color": True,
                    "nine_color_picker": True,
                    "title_removed": True,
                    "pin_toggle": True,
                    "settings_live_save": True,
                    "verified_update_install": True,
                    "note_remains_visible": True,
                    "note_collapse_toggle": True,
                    "geometry_persisted": True,
                    "state_reloaded": True,
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
