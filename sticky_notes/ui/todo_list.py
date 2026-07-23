from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Callable, Sequence

from ..model import Todo
from ..theme import FONT_FAMILY, NoteTheme
from .icons import IconSet
from .input_session import InputCommit, InputMode, TodoInputSession
from .todo_drag import TodoDragController


TodoResult = Sequence[Todo]


class TodoList(tk.Frame):
    """Render todos and translate Tk events into semantic todo operations."""

    def __init__(
        self,
        master: tk.Misc,
        icons: IconSet,
        on_toggle: Callable[[str, bool], TodoResult],
        on_edit: Callable[[str, str], TodoResult],
        on_delete: Callable[[str], TodoResult],
        on_add: Callable[[str], TodoResult],
        on_reorder: Callable[[str, int], TodoResult],
    ) -> None:
        super().__init__(master, borderwidth=0, highlightthickness=0)
        self.icons = icons
        self.on_toggle = on_toggle
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.on_add = on_add
        self.on_reorder = on_reorder

        self.theme: NoteTheme | None = None
        self.todos: list[Todo] = []
        self.placeholder = ""
        self.input_session = TodoInputSession()
        self._active_entry: tk.Entry | None = None
        self._placeholder_label: tk.Label | None = None
        self._rendering = False
        self._pending_todos: list[Todo] | None = None
        self._row_widgets: list[tuple[str, tk.Frame]] = []

        self.add_entry: tk.Entry | None = None
        self._add_canvas: tk.Canvas | None = None
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
        self.canvas.bind("<Button-1>", self._commit_from_blank, add="+")
        self.content.bind("<Button-1>", self._commit_from_blank, add="+")

        self._drag = TodoDragController(
            self,
            self.canvas,
            self.content,
            rows=lambda: self._row_widgets,
            todos=lambda: self.todos,
            theme=lambda: self.theme,
            ghost_factory=self._create_drag_ghost,
            on_reorder=self._reorder_from_drag,
        )

    def render(
        self,
        todos: Sequence[Todo],
        theme: NoteTheme,
        placeholder: str,
    ) -> None:
        """Rebuild the view while preserving the active input session."""
        had_focus = (
            self._active_entry is not None
            and self._active_entry.winfo_exists()
            and self.focus_get() is self._active_entry
        )
        self._rendering = True
        self._drag.reset()
        self.todos = list(todos)
        self.theme = theme
        self.placeholder = placeholder
        self.configure(bg=theme.background)
        self.canvas.configure(bg=theme.background)
        self.content.configure(bg=theme.background)
        self._active_entry = None
        for child in self.content.winfo_children():
            child.destroy()

        self._row_widgets = []
        for todo in self.todos:
            self._create_row(todo)
        self._create_add_row()
        self._restore_input_view()
        self._rendering = False
        self.after_idle(self._update_scroll_region)
        if had_focus and self._active_entry is not None:
            self.after_idle(self._focus_active_entry)

    def set_placeholder(self, placeholder: str) -> None:
        self.placeholder = placeholder
        if self._placeholder_label is not None:
            self._placeholder_label.configure(text=placeholder)

    def commit_active_input(self, *, refresh: bool = True) -> bool:
        """Commit the active session through one path for every UI event."""
        was_active = self.input_session.is_active
        command = self.input_session.commit()
        if not was_active:
            return False
        if command is None:
            if refresh:
                self._render_current()
            else:
                self._pending_todos = list(self.todos)
            return False

        todos = self._apply_input_commit(command)
        if refresh:
            self._render_result(todos)
        else:
            self.todos = list(todos)
            self._pending_todos = list(todos)
        return True

    def cancel_active_input(self) -> bool:
        changed = self.input_session.cancel()
        if changed:
            self._render_current()
        return changed

    def _apply_input_commit(self, command: InputCommit) -> TodoResult:
        if command.mode is InputMode.CREATING:
            return self.on_add(command.text)
        assert command.target_id is not None
        return self.on_edit(command.target_id, command.text)

    def _render_result(self, todos: TodoResult) -> None:
        self._pending_todos = None
        if self.theme is None:
            self.todos = list(todos)
            return
        self.render(todos, self.theme, self.placeholder)

    def _render_current(self) -> None:
        self._render_result(self.todos)

    def _create_row(self, todo: Todo) -> None:
        assert self.theme is not None
        theme = self.theme
        row = tk.Frame(self.content, bg=theme.background)
        row.pack(fill="x", padx=2, pady=1)
        row.grid_columnconfigure(1, weight=1)

        checkbox = tk.Button(
            row,
            image=self._checkbox_image(todo, theme),
            command=lambda: self._toggle_todo(todo.id, not todo.completed),
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

        label = self._make_todo_label(
            row,
            todo,
            theme,
            background=theme.background,
            cursor="fleur",
        )
        label.grid(row=0, column=1, sticky="ew", pady=7)
        label.bind("<Double-Button-1>", lambda _event: self._begin_edit(todo.id))
        for widget in (row, label):
            widget.bind(
                "<ButtonPress-1>",
                lambda event, todo_id=todo.id: self._start_row_drag(event, todo_id),
                add="+",
            )
            widget.bind("<B1-Motion>", self._drag_row, add="+")
            widget.bind("<ButtonRelease-1>", self._release_row, add="+")

        delete_button = tk.Button(
            row,
            image=self.icons.themed("delete", theme.icon_tone),
            command=lambda: self._delete_todo(todo.id),
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
        self._row_widgets.append((todo.id, row))

    def _make_todo_label(
        self,
        master: tk.Misc,
        todo: Todo,
        theme: NoteTheme,
        *,
        background: str,
        cursor: str = "",
    ) -> tk.Label:
        return tk.Label(
            master,
            text=todo.text,
            anchor="nw",
            justify="left",
            bg=background,
            fg=theme.completed if todo.completed else theme.text,
            font=tkfont.Font(
                family=FONT_FAMILY,
                size=11,
                overstrike=todo.completed,
            ),
            borderwidth=0,
            wraplength=max(80, self.winfo_width() - 76),
            cursor=cursor,
        )

    def _checkbox_image(self, todo: Todo, theme: NoteTheme) -> tk.PhotoImage:
        return self.icons.themed(
            "checkbox_on" if todo.completed else "checkbox_off",
            theme.icon_tone,
        )

    @staticmethod
    def _set_row_wraplength(width: int, label: tk.Label) -> None:
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

        initial = (
            self.input_session.draft
            if self.input_session.mode is InputMode.CREATING
            else ""
        )
        variable = tk.StringVar(master=self, value=initial)
        entry = tk.Entry(
            content,
            textvariable=variable,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            font=(FONT_FAMILY, 10),
            bg=theme.input_background,
            fg=theme.text,
            insertbackground=theme.text,
        )
        entry.pack(fill="both", expand=True, padx=10, pady=5)
        placeholder = tk.Label(
            content,
            text=self.placeholder,
            font=(FONT_FAMILY, 10),
            bg=theme.input_background,
            fg=theme.muted,
            borderwidth=0,
            cursor="xterm",
        )
        placeholder.bind("<Button-1>", self._activate_add_placeholder)

        entry.bind("<ButtonPress-1>", self._prepare_create_click, add="+")
        entry.bind("<Return>", self._commit_active_input_event)
        entry.bind("<Escape>", self._cancel_active_input_event)
        entry.bind("<FocusIn>", self._begin_create)
        entry.bind("<FocusOut>", self._input_focus_out)
        variable.trace_add(
            "write",
            lambda *_args, var=variable: self._sync_draft(
                var, InputMode.CREATING, None
            ),
        )
        canvas.bind("<Configure>", self._redraw_add_box)

        self.add_entry = entry
        self._add_canvas = canvas
        self._add_content_window = content_window
        self._placeholder_label = placeholder
        if self.input_session.mode is InputMode.CREATING:
            self._active_entry = entry
        self._sync_placeholder()
        self._redraw_add_box()

    def _prepare_create_click(self, _event: tk.Event) -> str | None:
        if self.input_session.mode is not InputMode.EDITING:
            return None
        self.commit_active_input()
        self.after_idle(self._focus_add_entry)
        return "break"

    def _activate_add_placeholder(self, _event: tk.Event) -> str:
        if self.input_session.mode is InputMode.EDITING:
            self.commit_active_input()
            self.after_idle(self._focus_add_entry)
        else:
            self._focus_add_entry()
        return "break"

    def _begin_create(self, _event: tk.Event | None = None) -> None:
        if self.input_session.mode is InputMode.EDITING:
            self.commit_active_input()
            self.after_idle(self._focus_add_entry)
            return
        if self.input_session.mode is InputMode.IDLE:
            self.input_session.begin_create()
        self._active_entry = self.add_entry
        self._sync_placeholder()

    def _sync_draft(
        self,
        variable: tk.StringVar,
        mode: InputMode,
        target_id: str | None,
    ) -> None:
        if self._rendering or self.input_session.mode is not mode:
            return
        if mode is InputMode.EDITING and self.input_session.target_id != target_id:
            return
        self.input_session.update_draft(variable.get())
        self._sync_placeholder()

    def _sync_placeholder(self) -> None:
        label = self._placeholder_label
        if label is None or not label.winfo_exists():
            return
        show = (
            self.input_session.mode is not InputMode.CREATING
            and self.add_entry is not None
            and not self.add_entry.get()
        )
        if show:
            label.place(x=10, rely=0.5, anchor="w")
            label.lift()
        else:
            label.place_forget()

    def _commit_active_input_event(self, _event: tk.Event | None = None) -> str:
        self.commit_active_input()
        self.canvas.focus_force()
        return "break"

    def _cancel_active_input_event(self, _event: tk.Event | None = None) -> str:
        self.cancel_active_input()
        self.canvas.focus_force()
        return "break"

    def _input_focus_out(self, event: tk.Event) -> None:
        if self._rendering or event.widget is not self._active_entry:
            return
        self.commit_active_input()

    def _restore_input_view(self) -> None:
        mode = self.input_session.mode
        if mode is InputMode.CREATING:
            self._active_entry = self.add_entry
            self._sync_placeholder()
            return
        if mode is not InputMode.EDITING:
            return
        todo_id = self.input_session.target_id
        todo = self._todo_for(todo_id)
        row = self._row_for(todo_id)
        if todo is None or row is None:
            self.input_session.cancel()
            return
        self._mount_edit_entry(row, todo)

    def _begin_edit(self, todo_id: str) -> None:
        if self.input_session.is_active:
            if (
                self.input_session.mode is InputMode.EDITING
                and self.input_session.target_id == todo_id
            ):
                return
            self.commit_active_input()
        todo = self._todo_for(todo_id)
        row = self._row_for(todo_id)
        if todo is None or row is None:
            return
        self.input_session.begin_edit(todo.id, todo.text)
        self._mount_edit_entry(row, todo)
        self._focus_active_entry()

    def _mount_edit_entry(self, row: tk.Frame, todo: Todo) -> None:
        assert self.theme is not None
        for child in row.winfo_children():
            child.grid_forget()
        variable = tk.StringVar(master=self, value=self.input_session.draft)
        entry = tk.Entry(
            row,
            textvariable=variable,
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
        entry.grid(row=0, column=0, columnspan=3, sticky="ew", padx=8, pady=5)
        entry.bind("<Return>", self._commit_active_input_event)
        entry.bind("<Escape>", self._cancel_active_input_event)
        entry.bind("<FocusOut>", self._input_focus_out)
        variable.trace_add(
            "write",
            lambda *_args, var=variable, target=todo.id: self._sync_draft(
                var, InputMode.EDITING, target
            ),
        )
        self._active_entry = entry
        entry.selection_range(0, "end")

    def _focus_active_entry(self) -> None:
        if self._active_entry is not None and self._active_entry.winfo_exists():
            self._active_entry.focus_set()

    def _focus_add_entry(self) -> None:
        if self.add_entry is not None and self.add_entry.winfo_exists():
            self.add_entry.focus_set()

    def _commit_from_blank(self, event: tk.Event) -> None:
        if event.widget is self._active_entry:
            return
        self.commit_active_input()
        self.canvas.focus_force()

    def _toggle_todo(self, todo_id: str, completed: bool) -> None:
        self.commit_active_input(refresh=False)
        self._render_result(self.on_toggle(todo_id, completed))

    def _delete_todo(self, todo_id: str) -> None:
        self.commit_active_input(refresh=False)
        self._render_result(self.on_delete(todo_id))

    def _start_row_drag(self, event: tk.Event, todo_id: str) -> None:
        if self.input_session.is_active:
            self.commit_active_input(refresh=False)
        self._drag.press(event, todo_id)

    def _drag_row(self, event: tk.Event) -> str | None:
        return "break" if self._drag.motion(event) else None

    def _release_row(self, event: tk.Event) -> str | None:
        reordered = self._drag.release(event)
        if self._pending_todos is not None:
            self._render_result(self._pending_todos)
        return "break" if reordered else None

    def _reorder_from_drag(self, todo_id: str, target_index: int) -> None:
        self._render_result(self.on_reorder(todo_id, target_index))

    def _create_drag_ghost(
        self,
        parent: tk.Misc,
        todo: Todo,
        theme: NoteTheme,
    ) -> tk.Widget:
        ghost = tk.Frame(
            parent,
            bg=theme.input_background,
            borderwidth=0,
            highlightbackground=theme.border,
            highlightthickness=1,
        )
        checkbox = tk.Label(
            ghost,
            image=self._checkbox_image(todo, theme),
            bg=theme.input_background,
            borderwidth=0,
        )
        checkbox.pack(side="left", padx=(5, 8), pady=5, anchor="n")
        label = self._make_todo_label(
            ghost,
            todo,
            theme,
            background=theme.input_background,
        )
        label.pack(side="left", fill="both", expand=True, pady=6)
        return ghost

    def _todo_for(self, todo_id: str | None) -> Todo | None:
        return next((todo for todo in self.todos if todo.id == todo_id), None)

    def _row_for(self, todo_id: str | None) -> tk.Frame | None:
        return next(
            (row for current_id, row in self._row_widgets if current_id == todo_id),
            None,
        )

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
            radius,
            1,
            width - radius,
            height - 1,
            fill=theme.input_background,
            outline="",
            tags="add-box-border",
        )
        canvas.create_rectangle(
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
            (width - radius * 2, height - radius * 2, width - 1, height - 1),
        ):
            canvas.create_oval(
                x1,
                y1,
                x2,
                y2,
                fill=theme.input_background,
                outline="",
                tags="add-box-border",
            )
        canvas.create_rectangle(
            1,
            1,
            width - 1,
            height - 1,
            outline=theme.border,
            width=1,
            tags="add-box-border",
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
