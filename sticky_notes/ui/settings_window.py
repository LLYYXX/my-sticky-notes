from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import replace

from ..model import AppSettings
from ..platform.windows import set_taskbar_visibility
from ..theme import FONT_FAMILY, THEMES


BACKGROUND = "#EDEDED"
NAVIGATION = "#DDDCDD"
NAVIGATION_ACTIVE = "#C9C8C9"
TEXT = "#252525"
MUTED = "#727272"
DIVIDER = "#D1D1D1"
CONTROL_BACKGROUND = "#FFFFFF"
ACCENT = "#FFF0A0"


class SettingsWindow(tk.Toplevel):
    """A normal taskbar window; changes are applied and persisted immediately."""

    def __init__(
        self,
        master: tk.Misc,
        settings: AppSettings,
        on_change: Callable[[AppSettings], bool],
        on_close: Callable[[], None],
    ) -> None:
        super().__init__(master)
        self.title("桌面便利贴设置")
        self.resizable(False, False)
        self.configure(bg=BACKGROUND)
        self._on_change = on_change
        self._on_close = on_close
        self._accepted = replace(settings)
        self._restoring = False
        self._open_at_login = tk.BooleanVar(value=settings.open_at_login)
        self._default_color = tk.StringVar(value=settings.default_color)
        self._new_notes_pinned = tk.BooleanVar(value=settings.new_notes_pinned)
        self._pages: dict[str, tk.Frame] = {}
        self._nav_buttons: dict[str, tk.Button] = {}

        self._build_navigation()
        content = tk.Frame(self, bg=BACKGROUND, padx=46, pady=28)
        content.pack(fill="both", expand=True)
        self._pages["general"] = self._build_general_page(content)
        self._pages["notes"] = self._build_notes_page(content)

        footer = tk.Frame(self, bg=BACKGROUND, height=42)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Frame(footer, bg=DIVIDER, height=1).pack(fill="x", side="top")
        tk.Label(
            footer,
            text="更改会自动保存",
            bg=BACKGROUND,
            fg=MUTED,
            font=(FONT_FAMILY, 9),
        ).pack(side="right", padx=22, pady=(9, 0))

        self._show_page("general")
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda _event: self._close())
        self.bind("<Map>", self._on_map, add="+")
        self.update_idletasks()
        width, height = 620, 430
        x = max(0, (self.winfo_screenwidth() - width) // 2)
        y = max(0, (self.winfo_screenheight() - height) // 3)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.after(0, self._apply_window_style)
        self.lift()
        self.focus_force()

    def _build_navigation(self) -> None:
        navigation = tk.Frame(self, bg=NAVIGATION, height=62)
        navigation.pack(fill="x", side="top")
        navigation.pack_propagate(False)
        tk.Label(
            navigation,
            text="桌面便利贴",
            bg=NAVIGATION,
            fg=TEXT,
            font=(FONT_FAMILY, 12, "bold"),
        ).pack(side="left", padx=(22, 28))
        for key, label in (("general", "常规"), ("notes", "便签")):
            button = tk.Button(
                navigation,
                text=label,
                command=lambda page=key: self._show_page(page),
                bg=NAVIGATION,
                activebackground=NAVIGATION_ACTIVE,
                fg=TEXT,
                activeforeground=TEXT,
                relief="flat",
                borderwidth=0,
                highlightthickness=0,
                width=10,
                font=(FONT_FAMILY, 10),
                cursor="hand2",
            )
            button.pack(side="left", fill="y")
            self._nav_buttons[key] = button
        tk.Frame(self, bg=DIVIDER, height=1).pack(fill="x", side="top")

    def _build_general_page(self, master: tk.Misc) -> tk.Frame:
        page = self._page(master, "常规", "控制应用如何随 Windows 启动。")
        self._setting_row(
            page,
            "开机时自动启动",
            "登录 Windows 后自动显示桌面便签。",
            lambda row: self._check(row, self._open_at_login),
        )
        self._setting_row(
            page,
            "轻量桌面模式",
            "便签始终留在桌面，但不会在任务栏程序栏中显示。",
            lambda row: self._value_label(row, "始终开启"),
        )
        return page

    def _build_notes_page(self, master: tk.Misc) -> tk.Frame:
        page = self._page(master, "便签", "设置新建便签的默认外观和行为。")
        self._setting_row(
            page,
            "便签颜色",
            "用于之后创建的便签。",
            self._color_control,
        )
        self._setting_row(
            page,
            "新建便签默认置顶",
            "新建后自动保持在其他窗口上方。",
            lambda row: self._check(row, self._new_notes_pinned),
        )
        return page

    @staticmethod
    def _page(master: tk.Misc, title: str, description: str) -> tk.Frame:
        page = tk.Frame(master, bg=BACKGROUND)
        tk.Label(
            page,
            text=title,
            bg=BACKGROUND,
            fg=TEXT,
            anchor="w",
            font=(FONT_FAMILY, 18, "bold"),
        ).pack(fill="x")
        tk.Label(
            page,
            text=description,
            bg=BACKGROUND,
            fg=MUTED,
            anchor="w",
            font=(FONT_FAMILY, 9),
        ).pack(fill="x", pady=(4, 22))
        return page

    @staticmethod
    def _setting_row(
        master: tk.Misc,
        title: str,
        description: str,
        control_factory: Callable[[tk.Misc], tk.Widget],
    ) -> None:
        row = tk.Frame(master, bg=BACKGROUND, height=76)
        row.pack(fill="x")
        row.pack_propagate(False)
        text = tk.Frame(row, bg=BACKGROUND)
        text.pack(side="left", fill="both", expand=True, pady=12)
        tk.Label(
            text,
            text=title,
            bg=BACKGROUND,
            fg=TEXT,
            anchor="w",
            font=(FONT_FAMILY, 10),
        ).pack(fill="x")
        tk.Label(
            text,
            text=description,
            bg=BACKGROUND,
            fg=MUTED,
            anchor="w",
            font=(FONT_FAMILY, 9),
        ).pack(fill="x", pady=(3, 0))
        control_factory(row).pack(side="right", padx=(24, 4))
        tk.Frame(master, bg=DIVIDER, height=1).pack(fill="x")

    def _color_control(self, master: tk.Misc) -> tk.Frame:
        control = tk.Frame(master, bg=BACKGROUND)
        for key in ("yellow", "offwhite"):
            tk.Radiobutton(
                control,
                text=THEMES[key].label,
                value=key,
                variable=self._default_color,
                command=self._commit,
                bg=BACKGROUND,
                activebackground=BACKGROUND,
                selectcolor=CONTROL_BACKGROUND,
                fg=TEXT,
                font=(FONT_FAMILY, 10),
                borderwidth=0,
                highlightthickness=0,
            ).pack(side="left", padx=(12, 0))
        return control

    def _check(self, master: tk.Misc, variable: tk.BooleanVar) -> tk.Checkbutton:
        return tk.Checkbutton(
            master,
            text="启用",
            variable=variable,
            command=self._commit,
            bg=BACKGROUND,
            activebackground=BACKGROUND,
            selectcolor=CONTROL_BACKGROUND,
            fg=TEXT,
            font=(FONT_FAMILY, 10),
            borderwidth=0,
            highlightthickness=0,
        )

    @staticmethod
    def _value_label(master: tk.Misc, text: str) -> tk.Label:
        return tk.Label(
            master,
            text=text,
            bg=ACCENT,
            fg=TEXT,
            padx=10,
            pady=4,
            font=(FONT_FAMILY, 9),
        )

    def _show_page(self, key: str) -> None:
        for page in self._pages.values():
            page.pack_forget()
        self._pages[key].pack(fill="both", expand=True)
        for page_key, button in self._nav_buttons.items():
            button.configure(
                bg=NAVIGATION_ACTIVE if page_key == key else NAVIGATION,
                font=(
                    FONT_FAMILY,
                    10,
                    "bold" if page_key == key else "normal",
                ),
            )

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
            return
        self._restoring = True
        try:
            self._open_at_login.set(self._accepted.open_at_login)
            self._default_color.set(self._accepted.default_color)
            self._new_notes_pinned.set(self._accepted.new_notes_pinned)
        finally:
            self._restoring = False

    def _on_map(self, _event: tk.Event | None = None) -> None:
        self.after(0, self._apply_window_style)

    def _apply_window_style(self) -> None:
        if self.winfo_exists():
            set_taskbar_visibility(self, visible=True)

    def _close(self) -> None:
        if self.winfo_exists():
            self.destroy()
        self._on_close()
