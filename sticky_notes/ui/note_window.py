from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

from ..model import Note, Todo
from ..platform.windows import (
    MIN_HEIGHT,
    MIN_WIDTH,
    apply_note_window_style,
)
from ..theme import FONT_FAMILY, get_theme
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
        self.window.title(note.title)
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
            title=note.title,
            icons=icons,
            pinned=note.pinned,
            on_pin=self._toggle_pin,
            on_delete=lambda: controller.delete_note(note.id),
            on_title_change=self._change_title,
            on_drag_start=self._drag_start,
            on_drag_motion=self._drag_motion,
            on_drag_release=self._drag_release,
        )
        self.surface.grid_columnconfigure(0, weight=1)
        self.surface.grid_rowconfigure(2, weight=1)
        self.surface.grid_rowconfigure(3, minsize=60)
        self.title_bar.grid(row=0, column=0, sticky="ew")
        self.header_separator = tk.Frame(self.surface, height=1, borderwidth=0)
        self.header_separator.grid(row=1, column=0, sticky="ew")

        self.todo_list = TodoList(
            self.surface,
            icons=icons,
            on_toggle=self._toggle_todo,
            on_edit=self._edit_todo,
            on_delete=self._delete_todo,
        )
        self.todo_list.grid(row=2, column=0, sticky="nsew")

        self.footer = tk.Frame(self.surface, height=60, borderwidth=0)
        self.footer.grid(row=3, column=0, sticky="ew")
        self.footer.pack_propagate(False)
        self.add_box = tk.Canvas(
            self.footer,
            height=38,
            borderwidth=0,
            highlightthickness=0,
        )
        self.add_box.pack(fill="x", padx=(14, 27), pady=(5, 11))
        self.add_box_content = tk.Frame(self.add_box, borderwidth=0)
        self._add_box_window = self.add_box.create_window(
            (10, 2), window=self.add_box_content, anchor="nw"
        )
        self.add_box.bind("<Configure>", self._redraw_add_box)
        self.add_icon = tk.Label(
            self.add_box_content,
            image=icons.add,
            borderwidth=0,
            cursor="xterm",
        )
        self.add_icon.pack(side="left", padx=(10, 6))
        self.add_entry = tk.Entry(
            self.add_box_content,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            font=(FONT_FAMILY, 10),
        )
        self.add_entry.pack(side="left", fill="both", expand=True, pady=5, padx=(0, 6))
        self.add_entry.bind("<Return>", self._add_todo)
        self.add_entry.bind("<FocusIn>", self._clear_placeholder)
        self.add_entry.bind("<FocusOut>", self._restore_placeholder)

        self.resize_grip = tk.Label(
            self.footer,
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
        self.window.bind("<Escape>", lambda _event: self.add_entry.focus_set())

        self.apply_theme()
        self.refresh_todos()
        self._set_placeholder()
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
        self.footer.configure(bg=theme.background)
        self.add_box.configure(bg=theme.background)
        self.add_box_content.configure(bg=theme.input_background)
        self.add_icon.configure(bg=theme.input_background)
        self.add_entry.configure(
            bg=theme.input_background,
            fg=theme.muted,
            insertbackground=theme.text,
            disabledbackground=theme.input_background,
        )
        self.resize_grip.configure(bg=theme.background)
        self._redraw_add_box()
        self.todo_list.render(self.note.todos, theme)

    def refresh_todos(self) -> None:
        self.todo_list.render(self.note.todos, get_theme(self.note.color))

    def update_geometry_model(self) -> None:
        if not self.window.winfo_exists():
            return
        self.note.x = self.window.winfo_x()
        self.note.y = self.window.winfo_y()
        self.note.width = self.window.winfo_width()
        self.note.height = self.window.winfo_height()

    def destroy(self) -> None:
        if self.window.winfo_exists():
            self.window.destroy()

    def raise_window(self) -> None:
        if not self.window.winfo_exists():
            return
        self.window.deiconify()
        self.window.lift()
        self.window.after(0, self._apply_window_style)

    def sync_topmost(self) -> None:
        settings_open = self.controller.settings_window is not None
        self.window.wm_attributes("-topmost", self.note.pinned and not settings_open)

    def _change_title(self, title: str) -> None:
        self.note.title = title
        self.window.title(title)
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

    def _add_todo(self, _event: tk.Event | None = None) -> str:
        value = self.add_entry.get().strip()
        if not value or value == "添加待办":
            return "break"
        self.note.todos.append(Todo(text=value, order=len(self.note.todos)))
        self.add_entry.delete(0, "end")
        self.refresh_todos()
        self.controller.schedule_save()
        return "break"

    def _set_placeholder(self) -> None:
        theme = get_theme(self.note.color)
        self.add_entry.delete(0, "end")
        self.add_entry.insert(0, "添加待办")
        self.add_entry.configure(fg=theme.muted)

    def _clear_placeholder(self, _event: tk.Event | None = None) -> None:
        if self.add_entry.get() == "添加待办":
            self.add_entry.delete(0, "end")
            self.add_entry.configure(fg=get_theme(self.note.color).text)

    def _restore_placeholder(self, _event: tk.Event | None = None) -> None:
        if not self.add_entry.get().strip():
            self._set_placeholder()

    def _redraw_add_box(self, _event: tk.Event | None = None) -> None:
        if not self.add_box.winfo_exists():
            return
        theme = get_theme(self.note.color)
        width = max(24, self.add_box.winfo_width())
        height = max(24, self.add_box.winfo_height())
        radius = 8
        self.add_box.delete("add-box-border")
        self.add_box.create_rectangle(
            radius,
            1,
            width - radius,
            height - 1,
            fill=theme.input_background,
            outline="",
            tags="add-box-border",
        )
        self.add_box.create_rectangle(
            1,
            radius,
            width - 1,
            height - radius,
            fill=theme.input_background,
            outline="",
            tags="add-box-border",
        )
        for x1, y1, x2, y2 in (
            (1, 1, radius * 2, radius * 2),
            (width - radius * 2, 1, width - 1, radius * 2),
            (1, height - radius * 2, radius * 2, height - 1),
            (
                width - radius * 2,
                height - radius * 2,
                width - 1,
                height - 1,
            ),
        ):
            self.add_box.create_oval(
                x1,
                y1,
                x2,
                y2,
                fill=theme.input_background,
                outline="",
                tags="add-box-border",
            )
        self.add_box.create_line(
            radius,
            1,
            width - radius,
            1,
            fill=theme.border,
            tags="add-box-border",
        )
        self.add_box.create_line(
            radius,
            height - 1,
            width - radius,
            height - 1,
            fill=theme.border,
            tags="add-box-border",
        )
        self.add_box.create_line(
            1,
            radius,
            1,
            height - radius,
            fill=theme.border,
            tags="add-box-border",
        )
        self.add_box.create_line(
            width - 1,
            radius,
            width - 1,
            height - radius,
            fill=theme.border,
            tags="add-box-border",
        )
        for box, start in (
            ((1, 1, radius * 2, radius * 2), 90),
            ((width - radius * 2, 1, width - 1, radius * 2), 0),
            ((1, height - radius * 2, radius * 2, height - 1), 180),
            (
                (
                    width - radius * 2,
                    height - radius * 2,
                    width - 1,
                    height - 1,
                ),
                270,
            ),
        ):
            self.add_box.create_arc(
                *box,
                start=start,
                extent=90,
                style=tk.ARC,
                outline=theme.border,
                width=1,
                tags="add-box-border",
            )
        self.add_box.tag_lower("add-box-border")
        self.add_box.coords(self._add_box_window, 10, 2)
        self.add_box.itemconfigure(
            self._add_box_window,
            width=max(1, width - 20),
            height=max(1, height - 4),
        )

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
        if self._drag_distance < 4:
            self.title_bar.begin_title_edit()
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
