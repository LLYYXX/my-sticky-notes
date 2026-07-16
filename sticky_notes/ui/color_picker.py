from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from ..theme import NoteTheme, THEMES
from .icons import IconSet


class ColorPicker(tk.Button):
    """Compact palette action with a transient nine-color chooser."""

    def __init__(
        self,
        master: tk.Misc,
        icons: IconSet,
        color_key: str,
        on_select: Callable[[str], None],
    ) -> None:
        super().__init__(
            master,
            image=icons.palette,
            command=self._toggle_popup,
            width=26,
            height=26,
            borderwidth=0,
            relief="flat",
            highlightthickness=0,
            cursor="hand2",
            takefocus=True,
        )
        self._icons = icons
        self._color_key = color_key
        self._on_select = on_select
        self._theme = THEMES[color_key]
        self._popup: tk.Toplevel | None = None
        self.bind("<Return>", self._toggle_popup)
        self.bind("<space>", self._toggle_popup)

    def apply_theme(self, theme: NoteTheme) -> None:
        self._theme = theme
        self._color_key = theme.key
        self.configure(
            image=self._icons.themed("palette", theme.icon_tone),
            bg=theme.header,
            activebackground=theme.hover,
            activeforeground=theme.text,
        )

    def close_popup(self) -> None:
        popup = self._popup
        self._popup = None
        if popup is None or not popup.winfo_exists():
            return
        try:
            popup.grab_release()
        except tk.TclError:
            pass
        popup.destroy()

    def _toggle_popup(self, _event: tk.Event | None = None) -> str:
        if self._popup is not None and self._popup.winfo_exists():
            self.close_popup()
        else:
            self._open_popup()
        return "break"

    def _open_popup(self) -> None:
        popup = tk.Toplevel(self)
        popup.withdraw()
        popup.overrideredirect(True)
        popup.transient(self.winfo_toplevel())
        popup.configure(bg=self._theme.border)

        panel = tk.Frame(popup, bg=self._theme.menu, padx=7, pady=7)
        panel.pack(padx=1, pady=1)
        for index, (key, theme) in enumerate(THEMES.items()):
            swatch = tk.Canvas(
                panel,
                width=34,
                height=34,
                bg=self._theme.menu,
                borderwidth=0,
                highlightthickness=0,
                cursor="hand2",
                takefocus=True,
            )
            swatch.grid(row=index // 3, column=index % 3, padx=3, pady=3)
            self._draw_swatch(swatch, theme, key == self._color_key)
            swatch.bind("<Button-1>", lambda _event, value=key: self._select(value))
            swatch.bind("<Return>", lambda _event, value=key: self._select(value))
            swatch.bind("<space>", lambda _event, value=key: self._select(value))

        popup.update_idletasks()
        width = popup.winfo_reqwidth()
        height = popup.winfo_reqheight()
        x = min(
            self.winfo_rootx(),
            max(0, popup.winfo_screenwidth() - width - 8),
        )
        y = self.winfo_rooty() + self.winfo_height() + 3
        if y + height > popup.winfo_screenheight() - 8:
            y = max(0, self.winfo_rooty() - height - 3)
        popup.geometry(f"{width}x{height}+{x}+{y}")
        popup.bind("<Escape>", lambda _event: self.close_popup())
        popup.bind("<Button-1>", self._close_when_outside, add="+")
        popup.protocol("WM_DELETE_WINDOW", self.close_popup)
        self._popup = popup
        popup.deiconify()
        popup.lift()
        popup.focus_force()
        popup.grab_set()

    def _select(self, color_key: str) -> str:
        self.close_popup()
        if color_key != self._color_key:
            self._color_key = color_key
            self._on_select(color_key)
        return "break"

    def _close_when_outside(self, event: tk.Event) -> None:
        popup = self._popup
        if popup is None or not popup.winfo_exists():
            return
        inside = (
            popup.winfo_rootx() <= event.x_root < popup.winfo_rootx() + popup.winfo_width()
            and popup.winfo_rooty() <= event.y_root < popup.winfo_rooty() + popup.winfo_height()
        )
        if not inside:
            self.close_popup()

    def _draw_swatch(
        self,
        canvas: tk.Canvas,
        theme: NoteTheme,
        selected: bool,
    ) -> None:
        outline = self._theme.text if selected else self._theme.border
        width = 3 if selected else 1
        canvas.create_oval(
            4,
            4,
            30,
            30,
            fill=theme.background,
            outline=outline,
            width=width,
        )
