from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from ..theme import FONT_FAMILY, NoteTheme
from .icons import IconSet


class TitleBar(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        title: str,
        default_title: str,
        icons: IconSet,
        pinned: bool,
        on_pin: Callable[[], None],
        on_delete: Callable[[], None],
        on_title_change: Callable[[str], None],
        on_drag_start: Callable[[tk.Event], None],
        on_drag_motion: Callable[[tk.Event], None],
        on_drag_release: Callable[[tk.Event], None],
    ) -> None:
        super().__init__(master, height=44, borderwidth=0, highlightthickness=0)
        self.pack_propagate(False)
        self._on_title_change = on_title_change
        self._icons = icons
        self._pinned = pinned
        self._default_title = default_title
        self.title_label = tk.Label(
            self,
            text=title,
            anchor="w",
            font=(FONT_FAMILY, 13, "bold"),
            padx=16,
            borderwidth=0,
        )
        self.title_label.pack(side="left", fill="both", expand=True)

        self.actions = tk.Frame(self, borderwidth=0, highlightthickness=0)
        self.buttons: list[tk.Button] = []
        self.pin_button = self._make_button(
            icons.pin,
            on_pin,
            "取消置顶" if pinned else "置顶便签",
        )
        self.pin_button.pack(side="left", padx=(0, 2), pady=8)
        self.buttons.append(self.pin_button)
        delete_button = self._make_button(icons.delete, on_delete, "删除便签")
        delete_button.pack(side="left", padx=(0, 8), pady=8)
        self.buttons.append(delete_button)
        self.actions.pack(side="right", fill="y")

        for widget in (self, self.title_label):
            widget.bind("<ButtonPress-1>", on_drag_start)
            widget.bind("<B1-Motion>", on_drag_motion)
            widget.bind("<ButtonRelease-1>", on_drag_release)

    def _make_button(
        self, image: tk.PhotoImage, command: Callable[[], None], name: str
    ) -> tk.Button:
        return tk.Button(
            self.actions,
            image=image,
            command=command,
            width=26,
            height=26,
            borderwidth=0,
            relief="flat",
            cursor="hand2",
            takefocus=True,
            highlightthickness=0,
            name=name,
        )

    def set_pinned(self, pinned: bool) -> None:
        self._pinned = pinned
        if hasattr(self, "_theme"):
            self._apply_pin_state()

    def set_default_title(self, title: str) -> None:
        self._default_title = title

    def begin_title_edit(self) -> None:
        if hasattr(self, "_title_entry") and self._title_entry.winfo_exists():
            return
        self.title_label.pack_forget()
        entry = tk.Entry(
            self,
            font=(FONT_FAMILY, 13, "bold"),
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
        )
        self._title_entry = entry
        entry.insert(0, self.title_label.cget("text"))
        entry.pack(side="left", fill="both", expand=True, padx=(14, 8), pady=7)
        entry.focus_set()
        entry.selection_range(0, "end")
        entry.bind("<Return>", self._finish_title_edit)
        entry.bind("<Escape>", self._cancel_title_edit)
        entry.bind("<FocusOut>", self._finish_title_edit)

    def _finish_title_edit(self, _event: tk.Event | None = None) -> None:
        if not hasattr(self, "_title_entry") or not self._title_entry.winfo_exists():
            return
        title = self._title_entry.get().strip() or self._default_title
        self.title_label.configure(text=title)
        self._title_entry.destroy()
        self.title_label.pack(side="left", fill="both", expand=True)
        self._on_title_change(title)

    def _cancel_title_edit(self, _event: tk.Event | None = None) -> None:
        if hasattr(self, "_title_entry") and self._title_entry.winfo_exists():
            self._title_entry.destroy()
            self.title_label.pack(side="left", fill="both", expand=True)

    def apply_theme(self, theme: NoteTheme) -> None:
        self._theme = theme
        self.configure(bg=theme.header)
        self.title_label.configure(bg=theme.header, fg=theme.text)
        self.actions.configure(bg=theme.header)
        if hasattr(self, "_title_entry") and self._title_entry.winfo_exists():
            self._title_entry.configure(
                bg=theme.header,
                fg=theme.text,
                insertbackground=theme.text,
            )
        for button in self.buttons:
            button.configure(
                bg=theme.header,
                activebackground=theme.hover,
                activeforeground=theme.text,
            )
        self.pin_button.configure(image=self._icons.themed("pin", theme.icon_tone))
        self.buttons[1].configure(
            image=self._icons.themed("delete", theme.icon_tone)
        )
        self._apply_pin_state()

    def _apply_pin_state(self) -> None:
        theme = self._theme
        self.pin_button.configure(
            bg=theme.pressed if self._pinned else theme.header,
            activebackground=theme.pressed,
            relief="sunken" if self._pinned else "flat",
        )
