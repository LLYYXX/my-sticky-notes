from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Callable

from ..model import Todo
from ..theme import FONT_FAMILY, NoteTheme
from .icons import IconSet


class TodoList(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        icons: IconSet,
        on_toggle: Callable[[str, bool], None],
        on_edit: Callable[[str, str], None],
        on_delete: Callable[[str], None],
    ) -> None:
        super().__init__(master, borderwidth=0, highlightthickness=0)
        self.icons = icons
        self.on_toggle = on_toggle
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.theme: NoteTheme | None = None
        self.todos: list[Todo] = []

        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.content = tk.Frame(self.canvas, borderwidth=0, highlightthickness=0)
        self.content_window = self.canvas.create_window(
            (0, 0), window=self.content, anchor="nw"
        )
        self.canvas.pack(fill="both", expand=True, padx=10)
        self.content.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._resize_content)
        self.canvas.bind("<Enter>", lambda _event: self._bind_mousewheel(True))
        self.canvas.bind("<Leave>", lambda _event: self._bind_mousewheel(False))

    def render(self, todos: list[Todo], theme: NoteTheme) -> None:
        self.todos = todos
        self.theme = theme
        self.configure(bg=theme.background)
        self.canvas.configure(bg=theme.background)
        self.content.configure(bg=theme.background)
        for child in self.content.winfo_children():
            child.destroy()
        for todo in todos:
            self._create_row(todo)
        self.after_idle(self._update_scroll_region)

    def _create_row(self, todo: Todo) -> None:
        assert self.theme is not None
        theme = self.theme
        row = tk.Frame(self.content, bg=theme.background, height=38)
        row.pack(fill="x", padx=2, pady=1)
        row.pack_propagate(False)

        checkbox = tk.Button(
            row,
            image=self.icons.themed(
                "checkbox_on" if todo.completed else "checkbox_off",
                theme.icon_tone,
            ),
            command=lambda: self.on_toggle(todo.id, not todo.completed),
            bg=theme.background,
            activebackground=theme.hover,
            fg=theme.checkbox,
            activeforeground=theme.checkbox,
            borderwidth=0,
            relief="flat",
            highlightthickness=0,
            cursor="hand2",
            takefocus=True,
            width=24,
            height=24,
        )
        checkbox.pack(side="left", padx=(4, 8))

        font = tkfont.Font(
            family=FONT_FAMILY,
            size=11,
            overstrike=todo.completed,
        )
        label = tk.Label(
            row,
            text=todo.text,
            anchor="w",
            bg=theme.background,
            fg=theme.completed if todo.completed else theme.text,
            font=font,
            borderwidth=0,
        )
        label.pack(side="left", fill="both", expand=True)
        label.bind("<Double-Button-1>", lambda _event: self._begin_edit(row, todo))

        delete_button = tk.Button(
            row,
            image=self.icons.themed("delete", theme.icon_tone),
            command=lambda: self.on_delete(todo.id),
            width=24,
            height=24,
            bg=theme.background,
            activebackground=theme.hover,
            borderwidth=0,
            relief="flat",
            highlightthickness=0,
            cursor="hand2",
            takefocus=True,
        )

        def show_delete(_event: tk.Event | None = None) -> None:
            if not delete_button.winfo_ismapped():
                delete_button.pack(side="right", padx=(4, 2))

        def hide_delete(_event: tk.Event | None = None) -> None:
            row.after(80, lambda: self._hide_if_outside(row, delete_button))

        for widget in (row, checkbox, label, delete_button):
            widget.bind("<Enter>", show_delete, add="+")
            widget.bind("<Leave>", hide_delete, add="+")

    @staticmethod
    def _hide_if_outside(row: tk.Frame, button: tk.Button) -> None:
        if not row.winfo_exists() or not button.winfo_exists():
            return
        x = row.winfo_pointerx()
        y = row.winfo_pointery()
        inside = (
            row.winfo_rootx() <= x <= row.winfo_rootx() + row.winfo_width()
            and row.winfo_rooty() <= y <= row.winfo_rooty() + row.winfo_height()
        )
        if not inside:
            button.pack_forget()

    def _begin_edit(self, row: tk.Frame, todo: Todo) -> None:
        if not row.winfo_exists() or self.theme is None:
            return
        for child in row.winfo_children():
            child.pack_forget()
        entry = tk.Entry(
            row,
            font=(FONT_FAMILY, 11),
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=self.theme.border,
            highlightcolor=self.theme.border,
            bg=self.theme.background,
            fg=self.theme.text,
            insertbackground=self.theme.text,
        )
        entry.insert(0, todo.text)
        entry.pack(fill="both", expand=True, padx=8, pady=5)
        entry.focus_set()
        entry.selection_range(0, "end")

        def finish(_event: tk.Event | None = None) -> None:
            if not entry.winfo_exists():
                return
            value = entry.get().strip()
            if value:
                self.on_edit(todo.id, value)
            else:
                self.render(self.todos, self.theme)

        entry.bind("<Return>", finish)
        entry.bind("<Escape>", lambda _event: self.render(self.todos, self.theme))
        entry.bind("<FocusOut>", finish)

    def _update_scroll_region(self, _event: tk.Event | None = None) -> None:
        if self.canvas.winfo_exists():
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_content(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.content_window, width=event.width)

    def _bind_mousewheel(self, enabled: bool) -> None:
        if enabled:
            self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        else:
            self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
