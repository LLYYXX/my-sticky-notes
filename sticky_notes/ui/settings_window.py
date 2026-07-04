from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import replace

from ..model import AppSettings
from ..platform.windows import set_taskbar_visibility
from ..theme import FONT_FAMILY, THEMES


CANVAS = "#FFFFFF"
INK = "#000000"
ON_PRIMARY = "#FFFFFF"
HAIRLINE = "#E6E6E6"
SURFACE_SOFT = "#F7F7F5"
BLOCK_LIME = "#DCEEB1"
BLOCK_LILAC = "#C5B0F4"
MONO_FONT = "Cascadia Mono"
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


def _rounded_rectangle(
    canvas: tk.Canvas,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    radius: int,
    *,
    fill: str,
    outline: str | None = None,
    width: int = 1,
    tags: str,
) -> None:
    radius = max(1, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
    canvas.create_rectangle(
        x1 + radius,
        y1,
        x2 - radius,
        y2,
        fill=fill,
        outline="",
        tags=tags,
    )
    canvas.create_rectangle(
        x1,
        y1 + radius,
        x2,
        y2 - radius,
        fill=fill,
        outline="",
        tags=tags,
    )
    for bounds in (
        (x1, y1, x1 + radius * 2, y1 + radius * 2),
        (x2 - radius * 2, y1, x2, y1 + radius * 2),
        (x2 - radius * 2, y2 - radius * 2, x2, y2),
        (x1, y2 - radius * 2, x1 + radius * 2, y2),
    ):
        canvas.create_oval(*bounds, fill=fill, outline="", tags=tags)
    if outline is None:
        return
    for coords in (
        (x1 + radius, y1, x2 - radius, y1),
        (x2, y1 + radius, x2, y2 - radius),
        (x1 + radius, y2, x2 - radius, y2),
        (x1, y1 + radius, x1, y2 - radius),
    ):
        canvas.create_line(*coords, fill=outline, width=width, tags=tags)
    for bounds, start in (
        ((x1, y1, x1 + radius * 2, y1 + radius * 2), 90),
        ((x2 - radius * 2, y1, x2, y1 + radius * 2), 0),
        ((x2 - radius * 2, y2 - radius * 2, x2, y2), 270),
        ((x1, y2 - radius * 2, x1 + radius * 2, y2), 180),
    ):
        canvas.create_arc(
            *bounds,
            start=start,
            extent=90,
            style=tk.ARC,
            outline=outline,
            width=width,
            tags=tags,
        )


class RoundedPanel(tk.Canvas):
    def __init__(
        self,
        master: tk.Misc,
        *,
        outer: str,
        fill: str,
        radius: int,
        padding: int,
        height: int | None = None,
        outline: str | None = None,
    ) -> None:
        super().__init__(
            master,
            bg=outer,
            borderwidth=0,
            highlightthickness=0,
            height=height or 1,
        )
        self._fill = fill
        self._radius = radius
        self._padding = padding
        self._outline = outline
        self.content = tk.Frame(self, bg=fill, borderwidth=0)
        self._content_window = self.create_window(
            (padding, padding),
            window=self.content,
            anchor="nw",
        )
        self.bind("<Configure>", self._redraw)

    def _redraw(self, _event: tk.Event | None = None) -> None:
        width = max(2, self.winfo_width())
        height = max(2, self.winfo_height())
        self.delete("panel")
        _rounded_rectangle(
            self,
            1,
            1,
            width - 1,
            height - 1,
            self._radius,
            fill=self._fill,
            outline=self._outline,
            tags="panel",
        )
        self.tag_lower("panel")
        self.coords(self._content_window, self._padding, self._padding)
        self.itemconfigure(
            self._content_window,
            width=max(1, width - self._padding * 2),
            height=max(1, height - self._padding * 2),
        )


class PillButton(tk.Canvas):
    def __init__(
        self,
        master: tk.Misc,
        text: str,
        command: Callable[[], None],
    ) -> None:
        super().__init__(
            master,
            width=86,
            height=38,
            bg=CANVAS,
            borderwidth=0,
            highlightthickness=0,
            cursor="hand2",
            takefocus=True,
        )
        self._text = text
        self._command = command
        self._selected = False
        self._hovered = False
        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", lambda _event: self._command())
        self.bind("<Return>", lambda _event: self._command())
        self.bind("<space>", lambda _event: self._command())

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self._draw()

    def _enter(self, _event: tk.Event) -> None:
        self._hovered = True
        self._draw()

    def _leave(self, _event: tk.Event) -> None:
        self._hovered = False
        self._draw()

    def _draw(self) -> None:
        width = max(2, self.winfo_width())
        height = max(2, self.winfo_height())
        self.delete("all")
        fill = INK if self._selected else (SURFACE_SOFT if self._hovered else CANVAS)
        _rounded_rectangle(
            self,
            1,
            1,
            width - 1,
            height - 1,
            height // 2,
            fill=fill,
            tags="pill",
        )
        self.create_text(
            width // 2,
            height // 2,
            text=self._text,
            fill=ON_PRIMARY if self._selected else INK,
            font=(FONT_FAMILY, 10, "bold" if self._selected else "normal"),
        )


class ToggleSwitch(tk.Canvas):
    def __init__(
        self,
        master: tk.Misc,
        variable: tk.BooleanVar,
        command: Callable[[], None],
    ) -> None:
        super().__init__(
            master,
            width=104,
            height=38,
            bg=CANVAS,
            borderwidth=0,
            highlightthickness=0,
            cursor="hand2",
            takefocus=True,
        )
        self._variable = variable
        self._command = command
        self.bind("<Configure>", lambda _event: self.refresh())
        self.bind("<Button-1>", self._toggle)
        self.bind("<Return>", self._toggle)
        self.bind("<space>", self._toggle)

    def _toggle(self, _event: tk.Event | None = None) -> None:
        self._variable.set(not self._variable.get())
        self.refresh()
        self._command()

    def refresh(self) -> None:
        enabled = self._variable.get()
        width = max(2, self.winfo_width())
        height = max(2, self.winfo_height())
        self.delete("all")
        _rounded_rectangle(
            self,
            1,
            1,
            width - 1,
            height - 1,
            height // 2,
            fill=INK if enabled else SURFACE_SOFT,
            outline=None if enabled else HAIRLINE,
            tags="toggle",
        )
        knob_size = 22
        knob_left = width - knob_size - 8 if enabled else 8
        self.create_oval(
            knob_left,
            (height - knob_size) // 2,
            knob_left + knob_size,
            (height + knob_size) // 2,
            fill=ON_PRIMARY if enabled else INK,
            outline="",
        )
        self.create_text(
            34 if enabled else 70,
            height // 2,
            text="开启" if enabled else "关闭",
            fill=ON_PRIMARY if enabled else INK,
            font=(FONT_FAMILY, 9, "bold"),
        )


class StatusPill(tk.Canvas):
    def __init__(self, master: tk.Misc, text: str) -> None:
        super().__init__(
            master,
            width=104,
            height=36,
            bg=CANVAS,
            borderwidth=0,
            highlightthickness=0,
        )
        self._text = text
        self.bind("<Configure>", lambda _event: self._draw())

    def _draw(self) -> None:
        width = max(2, self.winfo_width())
        height = max(2, self.winfo_height())
        self.delete("all")
        _rounded_rectangle(
            self,
            1,
            1,
            width - 1,
            height - 1,
            height // 2,
            fill=SURFACE_SOFT,
            tags="status",
        )
        self.create_text(
            width // 2,
            height // 2,
            text=self._text,
            fill=INK,
            font=(FONT_FAMILY, 9, "bold"),
        )


class ThemeOption(tk.Canvas):
    def __init__(
        self,
        master: tk.Misc,
        theme_key: str,
        variable: tk.StringVar,
        command: Callable[[], None],
    ) -> None:
        super().__init__(
            master,
            width=176,
            height=48,
            bg=CANVAS,
            borderwidth=0,
            highlightthickness=0,
            cursor="hand2",
            takefocus=True,
        )
        self._theme_key = theme_key
        self._variable = variable
        self._command = command
        self.bind("<Configure>", lambda _event: self.refresh())
        self.bind("<Button-1>", self._select)
        self.bind("<Return>", self._select)
        self.bind("<space>", self._select)

    def _select(self, _event: tk.Event | None = None) -> None:
        self._variable.set(self._theme_key)
        self._command()

    def refresh(self) -> None:
        selected = self._variable.get() == self._theme_key
        theme = THEMES[self._theme_key]
        width = max(2, self.winfo_width())
        height = max(2, self.winfo_height())
        self.delete("all")
        _rounded_rectangle(
            self,
            1,
            1,
            width - 1,
            height - 1,
            8,
            fill=SURFACE_SOFT if selected else CANVAS,
            outline=INK if selected else HAIRLINE,
            width=2 if selected else 1,
            tags="option",
        )
        _rounded_rectangle(
            self,
            10,
            9,
            40,
            height - 9,
            6,
            fill=theme.background,
            outline=theme.border,
            tags="swatch",
        )
        self.create_text(
            52,
            height // 2,
            text=theme.label,
            anchor="w",
            fill=INK,
            font=(FONT_FAMILY, 9, "bold" if selected else "normal"),
        )


class ThemeSelector(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        variable: tk.StringVar,
        command: Callable[[], None],
    ) -> None:
        super().__init__(master, bg=CANVAS, borderwidth=0)
        self._variable = variable
        self._command = command
        self.options: list[ThemeOption] = []
        for index, key in enumerate(THEME_KEYS):
            option = ThemeOption(self, key, variable, self._select)
            option.grid(
                row=index // 3,
                column=index % 3,
                padx=4,
                pady=4,
                sticky="ew",
            )
            self.grid_columnconfigure(index % 3, weight=1)
            self.options.append(option)

    def _select(self) -> None:
        self.refresh()
        self._command()

    def refresh(self) -> None:
        for option in self.options:
            option.refresh()


class SettingsWindow(tk.Toplevel):
    """Taskbar-visible settings window with automatically persisted changes."""

    def __init__(
        self,
        master: tk.Misc,
        settings: AppSettings,
        on_change: Callable[[AppSettings], bool],
        on_close: Callable[[], None],
        on_activate: Callable[[], None],
    ) -> None:
        super().__init__(master)
        self.title("桌面便利贴设置")
        self.resizable(False, False)
        self.configure(bg=CANVAS)
        self._on_change = on_change
        self._on_close = on_close
        self._on_activate = on_activate
        self._accepted = replace(settings)
        self._restoring = False
        self._open_at_login = tk.BooleanVar(value=settings.open_at_login)
        self._default_color = tk.StringVar(value=settings.default_color)
        self._new_notes_pinned = tk.BooleanVar(value=settings.new_notes_pinned)
        self._pages: dict[str, tk.Frame] = {}
        self._nav_buttons: dict[str, PillButton] = {}
        self._refreshables: list[object] = []

        self._build_navigation()
        content = tk.Frame(self, bg=CANVAS, padx=28, pady=22)
        content.pack(fill="both", expand=True)
        self._pages["general"] = self._build_general_page(content)
        self._pages["notes"] = self._build_notes_page(content)

        footer = tk.Frame(self, bg=CANVAS, height=38)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Frame(footer, bg=HAIRLINE, height=1).pack(fill="x", side="top")
        tk.Label(
            footer,
            text="更改自动保存",
            bg=CANVAS,
            fg=INK,
            font=(MONO_FONT, 9),
        ).pack(side="right", padx=28, pady=(9, 0))

        self._show_page("general")
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda _event: self._close())
        self.bind("<Map>", self._on_map, add="+")
        self.bind("<FocusIn>", self._handle_activate, add="+")
        self.update_idletasks()
        width = min(780, max(680, self.winfo_screenwidth() - 64))
        height = min(660, max(620, self.winfo_screenheight() - 48))
        x = max(0, (self.winfo_screenwidth() - width) // 2)
        y = max(0, (self.winfo_screenheight() - height) // 3)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.after(0, self._apply_window_style)
        self.lift()
        self.focus_force()

    def _build_navigation(self) -> None:
        navigation = tk.Frame(self, bg=CANVAS, height=72)
        navigation.pack(fill="x", side="top")
        navigation.pack_propagate(False)
        brand = tk.Frame(navigation, bg=CANVAS)
        brand.pack(side="left", padx=(28, 0), pady=14)
        tk.Label(
            brand,
            text="SETTINGS",
            bg=CANVAS,
            fg=INK,
            anchor="w",
            font=(MONO_FONT, 8),
        ).pack(anchor="w")
        tk.Label(
            brand,
            text="桌面便利贴",
            bg=CANVAS,
            fg=INK,
            anchor="w",
            font=(FONT_FAMILY, 14, "bold"),
        ).pack(anchor="w")
        tabs = tk.Frame(navigation, bg=CANVAS)
        tabs.pack(side="right", padx=28, pady=17)
        for key, label in (("general", "常规"), ("notes", "便签")):
            button = PillButton(
                tabs,
                label,
                command=lambda page=key: self._show_page(page),
            )
            button.pack(side="left", padx=(8, 0))
            self._nav_buttons[key] = button
        tk.Frame(self, bg=HAIRLINE, height=1).pack(fill="x", side="top")

    def _build_general_page(self, master: tk.Misc) -> tk.Frame:
        page, body = self._page(
            master,
            BLOCK_LIME,
            "常规",
            "控制桌面便利贴如何随 Windows 启动与驻留。",
        )
        self._setting_card(
            body,
            BLOCK_LIME,
            "开机时自动启动",
            "登录 Windows 后自动启动桌面便利贴。",
            lambda row: self._toggle(row, self._open_at_login),
        )
        self._setting_card(
            body,
            BLOCK_LIME,
            "轻量桌面模式",
            "便签不占用任务栏，只在打开设置时显示应用入口。",
            lambda row: StatusPill(row, "始终开启"),
        )
        return page

    def _build_notes_page(self, master: tk.Misc) -> tk.Frame:
        page, body = self._page(
            master,
            BLOCK_LILAC,
            "便签",
            "选择新便签的默认颜色与置顶行为。",
        )
        color_card = RoundedPanel(
            body,
            outer=BLOCK_LILAC,
            fill=CANVAS,
            radius=24,
            padding=18,
            height=272,
            outline=HAIRLINE,
        )
        color_card.pack(fill="x", pady=(0, 12))
        tk.Label(
            color_card.content,
            text="便签颜色",
            bg=CANVAS,
            fg=INK,
            anchor="w",
            font=(FONT_FAMILY, 11, "bold"),
        ).pack(fill="x")
        tk.Label(
            color_card.content,
            text="保留经典配色，并加入编辑感更强的柔和色块。",
            bg=CANVAS,
            fg=INK,
            anchor="w",
            font=(FONT_FAMILY, 9),
        ).pack(fill="x", pady=(2, 6))
        selector = ThemeSelector(
            color_card.content,
            self._default_color,
            self._commit,
        )
        selector.pack(fill="x")
        self._refreshables.append(selector)
        self._setting_card(
            body,
            BLOCK_LILAC,
            "新建便签默认置顶",
            "新建后自动保持在其他窗口上方。",
            lambda row: self._toggle(row, self._new_notes_pinned),
        )
        return page

    @staticmethod
    def _page(
        master: tk.Misc,
        block_color: str,
        title: str,
        description: str,
    ) -> tuple[tk.Frame, tk.Frame]:
        page = tk.Frame(master, bg=CANVAS)
        panel = RoundedPanel(
            page,
            outer=CANVAS,
            fill=block_color,
            radius=24,
            padding=28,
        )
        panel.pack(fill="both", expand=True)
        tk.Label(
            panel.content,
            text=title,
            bg=block_color,
            fg=INK,
            anchor="w",
            font=(FONT_FAMILY, 22, "bold"),
        ).pack(fill="x")
        tk.Label(
            panel.content,
            text=description,
            bg=block_color,
            fg=INK,
            anchor="w",
            font=(FONT_FAMILY, 10),
        ).pack(fill="x", pady=(3, 18))
        body = tk.Frame(panel.content, bg=block_color)
        body.pack(fill="both", expand=True)
        return page, body

    def _setting_card(
        self,
        master: tk.Misc,
        outer: str,
        title: str,
        description: str,
        control_factory: Callable[[tk.Misc], tk.Widget],
    ) -> None:
        card = RoundedPanel(
            master,
            outer=outer,
            fill=CANVAS,
            radius=24,
            padding=18,
            height=86,
            outline=HAIRLINE,
        )
        card.pack(fill="x", pady=(0, 12))
        text = tk.Frame(card.content, bg=CANVAS)
        text.pack(side="left", fill="both", expand=True)
        tk.Label(
            text,
            text=title,
            bg=CANVAS,
            fg=INK,
            anchor="w",
            font=(FONT_FAMILY, 11, "bold"),
        ).pack(fill="x")
        tk.Label(
            text,
            text=description,
            bg=CANVAS,
            fg=INK,
            anchor="w",
            font=(FONT_FAMILY, 9),
        ).pack(fill="x", pady=(3, 0))
        control_factory(card.content).pack(side="right", padx=(22, 0), pady=4)

    def _toggle(self, master: tk.Misc, variable: tk.BooleanVar) -> ToggleSwitch:
        control = ToggleSwitch(master, variable, self._commit)
        self._refreshables.append(control)
        return control

    def _show_page(self, key: str) -> None:
        for page in self._pages.values():
            page.pack_forget()
        self._pages[key].pack(fill="both", expand=True)
        for page_key, button in self._nav_buttons.items():
            button.set_selected(page_key == key)

    def _current_settings(self) -> AppSettings:
        return AppSettings(
            default_color=self._default_color.get(),
            new_notes_pinned=self._new_notes_pinned.get(),
            open_at_login=self._open_at_login.get(),
        )

    def _commit(self) -> None:
        if self._restoring:
            return
        settings = self._current_settings()
        if self._on_change(settings):
            self._accepted = replace(settings)
            self._refresh_controls()
            return
        self._restoring = True
        try:
            self._open_at_login.set(self._accepted.open_at_login)
            self._default_color.set(self._accepted.default_color)
            self._new_notes_pinned.set(self._accepted.new_notes_pinned)
            self._refresh_controls()
        finally:
            self._restoring = False

    def _refresh_controls(self) -> None:
        for control in self._refreshables:
            control.refresh()

    def _on_map(self, _event: tk.Event | None = None) -> None:
        self.after(0, self._apply_window_style)

    def _handle_activate(self, event: tk.Event | None = None) -> None:
        if event is None or event.widget is self:
            self.after_idle(self._on_activate)

    def _apply_window_style(self) -> None:
        if self.winfo_exists():
            set_taskbar_visibility(self, visible=True)

    def _close(self) -> None:
        if self.winfo_exists():
            self.destroy()
        self._on_close()
