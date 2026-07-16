from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from ..theme import NoteTheme
from .color_picker import ColorPicker
from .icons import IconSet


class TitleBar(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        icons: IconSet,
        color_key: str,
        pinned: bool,
        collapsed: bool,
        on_color: Callable[[str], None],
        on_new: Callable[[], None],
        on_pin: Callable[[], None],
        on_delete: Callable[[], None],
        on_collapse: Callable[[], None],
        on_drag_start: Callable[[tk.Event], None],
        on_drag_motion: Callable[[tk.Event], None],
        on_drag_release: Callable[[tk.Event], None],
    ) -> None:
        super().__init__(master, height=44, borderwidth=0, highlightthickness=0)
        self.pack_propagate(False)
        self._icons = icons
        self._pinned = pinned
        self._collapsed = collapsed
        self.color_picker = ColorPicker(
            self,
            icons,
            color_key,
            on_color,
        )
        self.color_picker.pack(side="left", padx=(8, 2), pady=8)

        self.actions = tk.Frame(self, borderwidth=0, highlightthickness=0)
        self.buttons: list[tk.Button] = []
        self.new_button = self._make_button(
            icons.add,
            on_new,
            "新建便签",
        )
        self.new_button.pack(side="left", padx=(0, 2), pady=8)
        self.buttons.append(self.new_button)
        self.delete_button = self._make_button(
            icons.delete,
            on_delete,
            "删除便签",
        )
        self.delete_button.pack(side="left", padx=(0, 2), pady=8)
        self.buttons.append(self.delete_button)
        self.pin_button = self._make_button(
            icons.pin,
            on_pin,
            "取消置顶" if pinned else "置顶便签",
        )
        self.pin_button.pack(side="left", padx=(0, 2), pady=8)
        self.buttons.append(self.pin_button)
        self.collapse_button = self._make_button(
            icons.chevron_down if collapsed else icons.minus,
            on_collapse,
            "展开便签" if collapsed else "收起便签",
        )
        self.collapse_button.pack(side="left", padx=(0, 8), pady=8)
        self.buttons.append(self.collapse_button)
        self.actions.pack(side="right", fill="y")
        self.drag_area = tk.Frame(self, borderwidth=0, highlightthickness=0)
        self.drag_area.pack(side="left", fill="both", expand=True)

        for widget in (self, self.drag_area):
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

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        tone = self._theme.icon_tone if hasattr(self, "_theme") else "dark"
        icon = "chevron_down" if collapsed else "minus"
        self.collapse_button.configure(image=self._icons.themed(icon, tone))

    def apply_theme(self, theme: NoteTheme) -> None:
        self._theme = theme
        self.configure(bg=theme.header)
        self.drag_area.configure(bg=theme.header)
        self.actions.configure(bg=theme.header)
        self.color_picker.apply_theme(theme)
        for button in self.buttons:
            button.configure(
                bg=theme.header,
                fg=theme.text,
                activebackground=theme.hover,
                activeforeground=theme.text,
            )
        self.new_button.configure(image=self._icons.themed("add", theme.icon_tone))
        self.pin_button.configure(image=self._icons.themed("pin", theme.icon_tone))
        self.delete_button.configure(
            image=self._icons.themed("delete", theme.icon_tone)
        )
        collapse_icon = "chevron_down" if self._collapsed else "minus"
        self.collapse_button.configure(
            image=self._icons.themed(collapse_icon, theme.icon_tone)
        )
        self._apply_pin_state()

    def _apply_pin_state(self) -> None:
        theme = self._theme
        self.pin_button.configure(
            bg=theme.pressed if self._pinned else theme.header,
            activebackground=theme.pressed,
            relief="sunken" if self._pinned else "flat",
        )
