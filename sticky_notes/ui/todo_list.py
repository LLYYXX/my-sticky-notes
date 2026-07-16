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
        on_add: Callable[[str], None],
    ) -> None:
        super().__init__(master, borderwidth=0, highlightthickness=0)
        self.icons = icons
        self.on_toggle = on_toggle
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.on_add = on_add
        self.theme: NoteTheme | None = None
        self.todos: list[Todo] = []
        self.placeholder = ""
        self.add_entry: tk.Entry | None = None
        self._add_canvas: tk.Canvas | None = None
        self._add_content: tk.Frame | None = None
        self._add_content_window: int | None = None

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

    def render(self, todos: list[Todo], theme: NoteTheme, placeholder: str) -> None:
        self.todos = todos
        self.theme = theme
        self.placeholder = placeholder
        self.configure(bg=theme.background)
        self.canvas.configure(bg=theme.background)
        self.content.configure(bg=theme.background)
        for child in self.content.winfo_children():
            child.destroy()
        for todo in todos:
            self._create_row(todo)
        self._create_add_row()
        self.after_idle(self._update_scroll_region)

    def set_placeholder(self, placeholder: str) -> None:
        previous = self.placeholder
        self.placeholder = placeholder
        if self.add_entry is not None and self.add_entry.winfo_exists():
            if self.add_entry.get() == previous:
                self._set_placeholder()

    def focus_add(self) -> None:
        if self.add_entry is not None and self.add_entry.winfo_exists():
            self.add_entry.focus_set()

    def _create_row(self, todo: Todo) -> None:
        assert self.theme is not None
        theme = self.theme
        row = tk.Frame(self.content, bg=theme.background)
        row.pack(fill="x", padx=2, pady=1)
        row.grid_columnconfigure(1, weight=1)

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
        checkbox.grid(row=0, column=0, sticky="nw", padx=(4, 8), pady=6)

        font = tkfont.Font(
            family=FONT_FAMILY,
            size=11,
            overstrike=todo.completed,
        )
        label = tk.Label(
            row,
            text=todo.text,
            anchor="nw",
            justify="left",
            bg=theme.background,
            fg=theme.completed if todo.completed else theme.text,
            font=font,
            borderwidth=0,
            wraplength=1,
        )
        label.grid(row=0, column=1, sticky="ew", pady=7)
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
                delete_button.grid(row=0, column=2, sticky="ne", padx=(4, 2), pady=6)

        def hide_delete(_event: tk.Event | None = None) -> None:
            row.after(80, lambda: self._hide_if_outside(row, delete_button))

        for widget in (row, checkbox, label, delete_button):
            widget.bind("<Enter>", show_delete, add="+")
            widget.bind("<Leave>", hide_delete, add="+")
        row.bind(
            "<Configure>",
            lambda event: self._set_row_wraplength(event.width, label),
            add="+",
        )

    @staticmethod
    def _set_row_wraplength(width: int, label: tk.Label) -> None:
        # Reserve space for the checkbox and the hover-only delete action.
        label.configure(wraplength=max(80, width - 76))

    def _create_add_row(self) -> None:
        assert self.theme is not None
        theme = self.theme
        row = tk.Frame(self.content, bg=theme.background, height=44)
        row.pack(fill="x", padx=2, pady=(4, 8))
        row.pack_propagate(False)
        canvas = tk.Canvas(
            row,
            height=36,
            bg=theme.background,
            borderwidth=0,
            highlightthickness=0,
        )
        canvas.pack(fill="x", expand=True, padx=2, pady=2)
        content = tk.Frame(canvas, bg=theme.input_background, borderwidth=0)
        content_window = canvas.create_window((10, 2), window=content, anchor="nw")
        entry = tk.Entry(
            content,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            font=(FONT_FAMILY, 10),
            bg=theme.input_background,
            fg=theme.muted,
            insertbackground=theme.text,
        )
        entry.pack(fill="both", expand=True, padx=10, pady=5)
        entry.bind("<Return>", self._submit_add)
        entry.bind("<FocusIn>", self._clear_placeholder)
        entry.bind("<FocusOut>", self._restore_placeholder)
        canvas.bind("<Configure>", self._redraw_add_box)
        self.add_entry = entry
        self._add_canvas = canvas
        self._add_content = content
        self._add_content_window = content_window
        self._set_placeholder()
        self._redraw_add_box()

    def _submit_add(self, _event: tk.Event | None = None) -> str:
        if self.add_entry is None:
            return "break"
        value = self.add_entry.get().strip()
        if value and value != self.placeholder:
            self.on_add(value)
        return "break"

    def _set_placeholder(self) -> None:
        if self.add_entry is None or self.theme is None:
            return
        self.add_entry.delete(0, "end")
        self.add_entry.insert(0, self.placeholder)
        self.add_entry.configure(fg=self.theme.muted)

    def _clear_placeholder(self, _event: tk.Event | None = None) -> None:
        if self.add_entry is None or self.theme is None:
            return
        if self.add_entry.get() == self.placeholder:
            self.add_entry.delete(0, "end")
            self.add_entry.configure(fg=self.theme.text)

    def _restore_placeholder(self, _event: tk.Event | None = None) -> None:
        if self.add_entry is not None and not self.add_entry.get().strip():
            self._set_placeholder()

    def _redraw_add_box(self, _event: tk.Event | None = None) -> None:
        if (
            self._add_canvas is None
            or self._add_content_window is None
            or self.theme is None
        ):
            return
        canvas = self._add_canvas
        theme = self.theme
        width = max(24, canvas.winfo_width())
        height = max(24, canvas.winfo_height())
        radius = 8
        canvas.delete("add-box-border")
        canvas.create_rectangle(
            radius, 1, width - radius, height - 1,
            fill=theme.input_background, outline="", tags="add-box-border",
        )
        canvas.create_rectangle(
            1, radius, width - 1, height - radius,
            fill=theme.input_background, outline="", tags="add-box-border",
        )
        for x1, y1, x2, y2 in (
            (1, 1, radius * 2, radius * 2),
            (width - radius * 2, 1, width - 1, radius * 2),
            (1, height - radius * 2, radius * 2, height - 1),
            (width - radius * 2, height - radius * 2, width - 1, height - 1),
        ):
            canvas.create_oval(
                x1, y1, x2, y2,
                fill=theme.input_background, outline="", tags="add-box-border",
            )
        canvas.create_rectangle(
            1, 1, width - 1, height - 1,
            outline=theme.border, width=1, tags="add-box-border",
        )
        canvas.tag_lower("add-box-border")
        canvas.coords(self._add_content_window, 10, 2)
        canvas.itemconfigure(
            self._add_content_window,
            width=max(1, width - 20),
            height=max(1, height - 4),
        )

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
            button.grid_remove()

    def _begin_edit(self, row: tk.Frame, todo: Todo) -> None:
        if not row.winfo_exists() or self.theme is None:
            return
        for child in row.winfo_children():
            child.grid_forget()
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
        entry.grid(row=0, column=0, columnspan=3, sticky="ew", padx=8, pady=5)
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
        entry.bind(
            "<Escape>",
            lambda _event: self.render(self.todos, self.theme, self.placeholder),
        )
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
