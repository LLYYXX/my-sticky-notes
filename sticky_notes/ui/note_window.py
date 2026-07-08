from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

from ..i18n import tr
from ..model import Note, Todo
from ..platform.windows import (
    MIN_HEIGHT,
    MIN_WIDTH,
    apply_note_window_style,
)
from ..theme import THEMES, get_theme
from .icons import IconSet
from .title_bar import TitleBar
from .todo_list import TodoList

if TYPE_CHECKING:
    from ..controller import StickyNotesController


class NoteWindow:
    def __init__(
        self,
        controller: "StickyNotesController",
        note: Note,
        icons: IconSet,
        visible: bool = True,
    ) -> None:
        self.controller = controller
        self.note = note
        self.icons = icons
        self.window = tk.Toplevel(controller.root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.title(tr("app_name", controller.state.settings.language))
        self.window.minsize(MIN_WIDTH, MIN_HEIGHT)
        self.window.geometry(
            f"{note.width}x{note.height}+{note.x}+{note.y}"
        )
        self._drag_origin: tuple[int, int, int, int] | None = None
        self._drag_distance = 0
        self._resize_origin: tuple[int, int, int, int] | None = None

        self.surface = tk.Frame(
            self.window,
            borderwidth=0,
            highlightthickness=1,
        )
        self.surface.pack(fill="both", expand=True)

        self.title_bar = TitleBar(
            self.surface,
            theme_key=note.color,
            language=controller.state.settings.language,
            icons=icons,
            pinned=note.pinned,
            on_color=self._change_color,
            on_new=lambda: controller.create_note(note),
            on_minimize=self.hide,
            on_pin=self._toggle_pin,
            on_delete=lambda: controller.delete_note(note.id),
            on_drag_start=self._drag_start,
            on_drag_motion=self._drag_motion,
            on_drag_release=self._drag_release,
        )
        self.surface.grid_columnconfigure(0, weight=1)
        self.surface.grid_rowconfigure(2, weight=1)
        self.title_bar.grid(row=0, column=0, sticky="ew")
        self.header_separator = tk.Frame(self.surface, height=1, borderwidth=0)
        self.header_separator.grid(row=1, column=0, sticky="ew")

        self.todo_list = TodoList(
            self.surface,
            icons=icons,
            on_toggle=self._toggle_todo,
            on_edit=self._edit_todo,
            on_delete=self._delete_todo,
            on_add=self._add_todo,
            placeholder=tr("add_todo", controller.state.settings.language),
        )
        self.todo_list.grid(row=2, column=0, sticky="nsew")
        self.add_entry = self.todo_list.add_entry

        self.resize_grip = tk.Label(
            self.surface,
            image=icons.resize_corner,
            cursor="size_nw_se",
            borderwidth=0,
        )
        self.resize_grip.place(relx=1.0, rely=1.0, x=-2, y=-2, anchor="se")
        self.resize_grip.bind("<ButtonPress-1>", self._resize_start)
        self.resize_grip.bind("<B1-Motion>", self._resize_motion)
        self.resize_grip.bind("<ButtonRelease-1>", self._resize_release)

        self.window.bind("<Configure>", self._on_configure, add="+")
        self.window.bind("<Map>", self._on_map, add="+")
        self.window.bind("<Escape>", lambda _event: self.todo_list.focus_input())

        self.apply_theme()
        self.refresh_todos()
        self.sync_topmost()
        self.window.after(0, self._apply_window_style)
        if visible:
            self.window.deiconify()

    def apply_theme(self) -> None:
        theme = get_theme(self.note.color)
        self.window.configure(bg=theme.background)
        self.surface.configure(
            bg=theme.background,
            highlightbackground=theme.border,
            highlightcolor=theme.border,
        )
        self.title_bar.apply_theme(theme)
        self.header_separator.configure(bg=theme.border)
        self.resize_grip.configure(
            bg=theme.background,
            image=self.icons.themed("resize_corner", theme.icon_tone),
        )
        self.todo_list.render(self.note.todos, theme)

    def refresh_todos(self, *, scroll_to_end: bool = False) -> None:
        self.todo_list.render(
            self.note.todos,
            get_theme(self.note.color),
            scroll_to_end=scroll_to_end,
        )

    def update_geometry_model(self) -> None:
        if not self.window.winfo_exists():
            return
        self.note.x = self.window.winfo_x()
        self.note.y = self.window.winfo_y()
        self.note.width = self.window.winfo_width()
        self.note.height = self.window.winfo_height()

    def destroy(self) -> None:
        self.title_bar.close_palette()
        if self.window.winfo_exists():
            self.window.destroy()

    def hide(self) -> None:
        if not self.window.winfo_exists():
            return
        self.title_bar.close_palette()
        self.update_geometry_model()
        self.window.withdraw()
        self.controller.schedule_save()

    def is_visible(self) -> bool:
        return self.window.winfo_exists() and self.window.state() != "withdrawn"

    def focus_input(self) -> None:
        if self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            self.todo_list.focus_input()

    def sync_topmost(self) -> None:
        settings_open = self.controller.settings_window is not None
        self.window.wm_attributes("-topmost", self.note.pinned and not settings_open)

    def set_pinned(self, pinned: bool) -> None:
        self.note.pinned = pinned
        self.title_bar.set_pinned(pinned)
        self.sync_topmost()

    def refresh_language(self) -> None:
        language = self.controller.state.settings.language
        self.window.title(tr("app_name", language))
        self.title_bar.set_language(language)
        self.todo_list.set_placeholder(
            tr("add_todo", language)
        )

    def _change_color(self, theme_key: str) -> None:
        if theme_key not in THEMES:
            return
        self.note.color = theme_key
        self.apply_theme()
        self.controller.schedule_save()

    def _toggle_pin(self) -> None:
        self.note.pinned = not self.note.pinned
        self.sync_topmost()
        self.title_bar.set_pinned(self.note.pinned)
        self.controller.schedule_save()

    def _toggle_todo(self, todo_id: str, completed: bool) -> None:
        todo = self._find_todo(todo_id)
        if todo is not None:
            todo.completed = completed
            self.refresh_todos()
            self.controller.schedule_save()

    def _edit_todo(self, todo_id: str, text: str) -> None:
        todo = self._find_todo(todo_id)
        if todo is not None:
            todo.text = text.strip()
            self.refresh_todos()
            self.controller.schedule_save()

    def _delete_todo(self, todo_id: str) -> None:
        self.note.todos = [todo for todo in self.note.todos if todo.id != todo_id]
        for index, todo in enumerate(self.note.todos):
            todo.order = index
        self.refresh_todos()
        self.controller.schedule_save()

    def _find_todo(self, todo_id: str) -> Todo | None:
        return next((todo for todo in self.note.todos if todo.id == todo_id), None)

    def _add_todo(self, value: str) -> None:
        value = value.strip()
        if not value:
            return
        self.note.todos.append(Todo(text=value, order=len(self.note.todos)))
        self.refresh_todos(scroll_to_end=True)
        self.controller.schedule_save()

    def _drag_start(self, event: tk.Event) -> None:
        self._drag_origin = (
            event.x_root,
            event.y_root,
            self.window.winfo_x(),
            self.window.winfo_y(),
        )
        self._drag_distance = 0

    def _drag_motion(self, event: tk.Event) -> None:
        if self._drag_origin is None:
            return
        start_x, start_y, window_x, window_y = self._drag_origin
        delta_x = event.x_root - start_x
        delta_y = event.y_root - start_y
        self._drag_distance = max(self._drag_distance, abs(delta_x) + abs(delta_y))
        self.window.geometry(f"+{window_x + delta_x}+{window_y + delta_y}")

    def _drag_release(self, _event: tk.Event) -> None:
        self._drag_origin = None
        self.update_geometry_model()
        self.controller.schedule_save()

    def _resize_start(self, event: tk.Event) -> None:
        self._resize_origin = (
            event.x_root,
            event.y_root,
            self.window.winfo_width(),
            self.window.winfo_height(),
        )

    def _resize_motion(self, event: tk.Event) -> None:
        if self._resize_origin is None:
            return
        start_x, start_y, width, height = self._resize_origin
        new_width = max(MIN_WIDTH, width + event.x_root - start_x)
        new_height = max(MIN_HEIGHT, height + event.y_root - start_y)
        self.window.geometry(f"{new_width}x{new_height}")

    def _resize_release(self, _event: tk.Event) -> None:
        self._resize_origin = None
        self.update_geometry_model()
        self.controller.schedule_save()

    def _on_configure(self, event: tk.Event) -> None:
        if event.widget is self.window:
            self.controller.schedule_save()

    def _on_map(self, _event: tk.Event | None = None) -> None:
        self.window.after(0, self._apply_window_style)

    def _apply_window_style(self) -> None:
        if not self.window.winfo_exists():
            return
        apply_note_window_style(self.window)
        self.sync_topmost()
