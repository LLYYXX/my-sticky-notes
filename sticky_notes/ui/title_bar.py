from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from ..i18n import theme_label
from ..theme import FONT_FAMILY, THEMES, NoteTheme
from .icons import IconSet


THEME_KEYS = (
    "yellow",
    "offwhite",
    "lime",
    "lilac",
    "cream",
    "pink",
    "mint",
    "coral",
    "navy",
)


class ColorPalette(tk.Toplevel):
    """Compact nine-color picker attached to one note window."""

    def __init__(
        self,
        owner: tk.Misc,
        anchor: tk.Widget,
        icons: IconSet,
        theme: NoteTheme,
        selected: str,
        language: str,
        on_select: Callable[[str], None],
        on_close: Callable[[], None],
    ) -> None:
        super().__init__(owner)
        self.withdraw()
        self.overrideredirect(True)
        self.transient(owner.winfo_toplevel())
        self.configure(bg=theme.border)
        self._on_close = on_close
        self._closed = False

        panel = tk.Frame(self, bg=theme.menu, padx=7, pady=7)
        panel.pack(padx=1, pady=1)
        for index, key in enumerate(THEME_KEYS):
            button = tk.Button(
                panel,
                image=icons.swatch(key),
                text=theme_label(key, language),
                compound="top",
                command=lambda value=key: self._choose(value, on_select),
                bg=theme.pressed if key == selected else theme.menu,
                fg=theme.text,
                activebackground=theme.hover,
                activeforeground=theme.text,
                font=(FONT_FAMILY, 8),
                width=62,
                height=48,
                borderwidth=0,
                relief="flat",
                highlightthickness=0,
                cursor="hand2",
                takefocus=True,
            )
            button.grid(
                row=index // 3,
                column=index % 3,
                padx=2,
                pady=2,
            )

        self.bind("<Escape>", lambda _event: self.close())
        self.bind("<FocusOut>", self._handle_focus_out, add="+")
        self.update_idletasks()
        note = owner.winfo_toplevel()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        menu_width = self.winfo_reqwidth()
        menu_height = self.winfo_reqheight()
        note_left = note.winfo_rootx()
        note_top = note.winfo_rooty()
        note_right = note_left + note.winfo_width()
        gap = 8
        if note_right + gap + menu_width <= screen_width:
            x = note_right + gap
            y = note_top
        elif note_left - gap - menu_width >= 0:
            x = note_left - gap - menu_width
            y = note_top
        else:
            x = anchor.winfo_rootx()
            y = anchor.winfo_rooty() + anchor.winfo_height() + 4
        x = min(max(0, x), max(0, screen_width - menu_width))
        y = min(max(0, y), max(0, screen_height - menu_height))
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.lift()
        self.focus_force()

    def _choose(self, key: str, callback: Callable[[str], None]) -> None:
        self.close()
        callback(key)

    def _handle_focus_out(self, _event: tk.Event) -> None:
        self.after_idle(self._close_if_focus_left)

    def _close_if_focus_left(self) -> None:
        if self._closed:
            return
        focused = self.focus_get()
        if focused is None or focused.winfo_toplevel() is not self:
            self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.winfo_exists():
            self.destroy()
        self._on_close()


class TitleBar(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        theme_key: str,
        language: str,
        icons: IconSet,
        pinned: bool,
        on_color: Callable[[str], None],
        on_new: Callable[[], None],
        on_minimize: Callable[[], None],
        on_pin: Callable[[], None],
        on_delete: Callable[[], None],
        on_drag_start: Callable[[tk.Event], None],
        on_drag_motion: Callable[[tk.Event], None],
        on_drag_release: Callable[[tk.Event], None],
    ) -> None:
        super().__init__(master, height=44, borderwidth=0, highlightthickness=0)
        self.pack_propagate(False)
        self._theme_key = theme_key
        self._language = language
        self._icons = icons
        self._on_color = on_color
        self._pinned = pinned
        self._palette: ColorPalette | None = None

        self.color_button = tk.Button(
            self,
            image=icons.swatch(theme_key),
            command=self._toggle_palette,
            width=30,
            height=30,
            borderwidth=0,
            relief="flat",
            cursor="hand2",
            takefocus=True,
            highlightthickness=0,
            name="note_color",
        )
        self.color_button.pack(side="left", padx=(8, 2), pady=7)
        self.drag_region = tk.Frame(self, borderwidth=0, highlightthickness=0)
        self.drag_region.pack(side="left", fill="both", expand=True)

        self.actions = tk.Frame(self, borderwidth=0, highlightthickness=0)
        self.buttons: dict[str, tk.Button] = {
            "add": self._make_button(icons.add, on_new, "new_note"),
            "minus": self._make_button(icons.minus, on_minimize, "minimize_note"),
            "pin": self._make_button(icons.pin, on_pin, "pin_note"),
            "delete": self._make_button(icons.delete, on_delete, "delete_note"),
        }
        for index, key in enumerate(("add", "minus", "pin", "delete")):
            self.buttons[key].pack(
                side="left",
                padx=(0, 8 if index == 3 else 2),
                pady=8,
            )
        self.pin_button = self.buttons["pin"]
        self.actions.pack(side="right", fill="y")

        for widget in (self, self.drag_region):
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

    def _toggle_palette(self) -> None:
        if self._palette is not None and self._palette.winfo_exists():
            self._palette.close()
            return
        theme = THEMES.get(self._theme_key, THEMES["yellow"])
        self._palette = ColorPalette(
            self,
            self.color_button,
            self._icons,
            theme,
            self._theme_key,
            self._language,
            self._on_color,
            self._palette_closed,
        )

    def _palette_closed(self) -> None:
        self._palette = None

    def close_palette(self) -> None:
        if self._palette is not None and self._palette.winfo_exists():
            self._palette.close()

    def set_pinned(self, pinned: bool) -> None:
        self._pinned = pinned
        if hasattr(self, "_theme"):
            self._apply_pin_state()

    def set_language(self, language: str) -> None:
        self._language = language
        self.close_palette()

    def apply_theme(self, theme: NoteTheme) -> None:
        self.close_palette()
        self._theme = theme
        self._theme_key = theme.key
        self.configure(bg=theme.header)
        self.drag_region.configure(bg=theme.header)
        self.actions.configure(bg=theme.header)
        self.color_button.configure(
            image=self._icons.swatch(theme.key),
            bg=theme.header,
            activebackground=theme.hover,
        )
        for button in self.buttons.values():
            button.configure(
                bg=theme.header,
                activebackground=theme.hover,
                activeforeground=theme.text,
            )
        for key in ("add", "minus", "pin", "delete"):
            self.buttons[key].configure(
                image=self._icons.themed(key, theme.icon_tone)
            )
        self._apply_pin_state()

    def _apply_pin_state(self) -> None:
        theme = self._theme
        self.pin_button.configure(
            bg=theme.pressed if self._pinned else theme.header,
            activebackground=theme.pressed,
            relief="sunken" if self._pinned else "flat",
        )
