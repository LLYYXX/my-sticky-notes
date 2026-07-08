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
        placeholder: str,
    ) -> None:
        super().__init__(master, borderwidth=0, highlightthickness=0)
        self.icons = icons
        self.on_toggle = on_toggle
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.on_add = on_add
        self.theme: NoteTheme | None = None
        self.todos: list[Todo] = []
        self._rows: list[tk.Frame] = []
        self._placeholder = placeholder

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

        self.add_box = tk.Canvas(
            self.content,
            height=38,
            borderwidth=0,
            highlightthickness=0,
        )
        self.add_box_content = tk.Frame(self.add_box, borderwidth=0)
        self._add_box_window = self.add_box.create_window(
            (10, 2), window=self.add_box_content, anchor="nw"
        )
        self.add_box.bind("<Configure>", self._redraw_add_box)
        self.add_entry = tk.Entry(
            self.add_box_content,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            font=(FONT_FAMILY, 10),
        )
        self.add_entry.pack(fill="both", expand=True, padx=8, pady=5)
        self.add_entry.bind("<Return>", self._submit)
        self.add_entry.bind("<FocusIn>", self._clear_placeholder)
        self.add_entry.bind("<FocusOut>", self._restore_placeholder)
        self.add_box.pack(fill="x", padx=(6, 18), pady=(5, 12))
        self.add_entry.insert(0, placeholder)

    def render(
        self,
        todos: list[Todo],
        theme: NoteTheme,
        *,
        scroll_to_end: bool = False,
    ) -> None:
        self.todos = todos
        self.theme = theme
        self.configure(bg=theme.background)
        self.canvas.configure(bg=theme.background)
        self.content.configure(bg=theme.background)
        for row in self._rows:
            if row.winfo_exists():
                row.destroy()
        self._rows.clear()
        for todo in todos:
            self._create_row(todo)
        self.add_box.configure(bg=theme.background)
        self.add_box_content.configure(bg=theme.input_background)
        is_placeholder = self.add_entry.get() == self._placeholder
        self.add_entry.configure(
            bg=theme.input_background,
            fg=theme.muted if is_placeholder else theme.text,
            insertbackground=theme.text,
            disabledbackground=theme.input_background,
        )
        self._redraw_add_box()
        self.after_idle(
            lambda: self._finish_layout(scroll_to_end=scroll_to_end)
        )

    def set_placeholder(self, value: str) -> None:
        was_placeholder = self.add_entry.get() == self._placeholder
        self._placeholder = value
        if was_placeholder:
            self._set_placeholder()

    def focus_input(self) -> None:
        self._clear_placeholder()
        self.add_entry.focus_set()

    def _create_row(self, todo: Todo) -> None:
        assert self.theme is not None
        theme = self.theme
        row = tk.Frame(self.content, bg=theme.background)
        row.pack(fill="x", padx=2, pady=1, before=self.add_box)
        row.grid_columnconfigure(1, weight=1)
        self._rows.append(row)

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
        checkbox.grid(row=0, column=0, sticky="n", padx=(4, 8), pady=5)

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
        )
        label.grid(row=0, column=1, sticky="ew", pady=7)
        label.bind("<Double-Button-1>", lambda _event: self._begin_edit(row, todo))

        action_slot = tk.Frame(row, bg=theme.background, width=30)
        action_slot.grid(row=0, column=2, sticky="ns", padx=(2, 2))
        action_slot.grid_propagate(False)
        delete_button = tk.Button(
            action_slot,
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
                delete_button.pack(pady=5)

        def hide_delete(_event: tk.Event | None = None) -> None:
            row.after(80, lambda: self._hide_if_outside(row, delete_button))

        def reflow(event: tk.Event) -> None:
            label.configure(wraplength=max(80, event.width - 78))

        row.bind("<Configure>", reflow, add="+")
        for widget in (row, checkbox, label, action_slot, delete_button):
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
        entry.bind("<Escape>", lambda _event: self.render(self.todos, self.theme))
        entry.bind("<FocusOut>", finish)

    def _submit(self, _event: tk.Event | None = None) -> str:
        value = self.add_entry.get().strip()
        if not value or value == self._placeholder:
            return "break"
        self.add_entry.delete(0, "end")
        self.on_add(value)
        self.add_entry.focus_set()
        return "break"

    def _set_placeholder(self) -> None:
        self.add_entry.delete(0, "end")
        self.add_entry.insert(0, self._placeholder)
        if self.theme is not None:
            self.add_entry.configure(fg=self.theme.muted)

    def _clear_placeholder(self, _event: tk.Event | None = None) -> None:
        if self.add_entry.get() == self._placeholder:
            self.add_entry.delete(0, "end")
            if self.theme is not None:
                self.add_entry.configure(fg=self.theme.text)

    def _restore_placeholder(self, _event: tk.Event | None = None) -> None:
        if not self.add_entry.get().strip():
            self._set_placeholder()

    def _finish_layout(self, *, scroll_to_end: bool) -> None:
        self._update_scroll_region()
        if scroll_to_end:
            self.canvas.yview_moveto(1.0)

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

    def _redraw_add_box(self, _event: tk.Event | None = None) -> None:
        if not self.add_box.winfo_exists() or self.theme is None:
            return
        width = max(24, self.add_box.winfo_width())
        height = max(24, self.add_box.winfo_height())
        radius = 8
        self.add_box.delete("add-box")
        self.add_box.create_rectangle(
            radius,
            1,
            width - radius,
            height - 1,
            fill=self.theme.input_background,
            outline="",
            tags="add-box",
        )
        self.add_box.create_rectangle(
            1,
            radius,
            width - 1,
            height - radius,
            fill=self.theme.input_background,
            outline="",
            tags="add-box",
        )
        corners = (
            (1, 1, radius * 2, radius * 2),
            (width - radius * 2, 1, width - 1, radius * 2),
            (1, height - radius * 2, radius * 2, height - 1),
            (width - radius * 2, height - radius * 2, width - 1, height - 1),
        )
        for box in corners:
            self.add_box.create_oval(
                *box,
                fill=self.theme.input_background,
                outline="",
                tags="add-box",
            )
        self.add_box.create_line(
            radius, 1, width - radius, 1,
            fill=self.theme.border,
            tags="add-box",
        )
        self.add_box.create_line(
            radius, height - 1, width - radius, height - 1,
            fill=self.theme.border,
            tags="add-box",
        )
        self.add_box.create_line(
            1, radius, 1, height - radius,
            fill=self.theme.border,
            tags="add-box",
        )
        self.add_box.create_line(
            width - 1, radius, width - 1, height - radius,
            fill=self.theme.border,
            tags="add-box",
        )
        for box, start in zip(corners, (90, 0, 180, 270), strict=True):
            self.add_box.create_arc(
                *box,
                start=start,
                extent=90,
                style=tk.ARC,
                outline=self.theme.border,
                width=1,
                tags="add-box",
            )
        self.add_box.tag_lower("add-box")
        self.add_box.coords(self._add_box_window, 10, 2)
        self.add_box.itemconfigure(
            self._add_box_window,
            width=max(1, width - 20),
            height=max(1, height - 4),
        )
