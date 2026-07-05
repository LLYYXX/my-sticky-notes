from __future__ import annotations

import queue
import threading
import tkinter as tk
import webbrowser
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from .. import __version__
from ..i18n import theme_label, tr
from ..model import AppSettings
from ..platform.windows import set_taskbar_visibility
from ..theme import FONT_FAMILY
from ..update_checker import (
    PROJECT_URL,
    DownloadedUpdate,
    UpdateCheckError,
    UpdateResult,
    check_for_updates,
    download_release_update,
    launch_update_installer,
)


CANVAS = "#FFFFFF"
INK = "#000000"
ON_PRIMARY = "#FFFFFF"
HAIRLINE = "#E6E6E6"
SURFACE_SOFT = "#F7F7F5"
BLOCK_LIME = "#DCEEB1"
BLOCK_LILAC = "#C5B0F4"
BLOCK_CREAM = "#F4ECD6"
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
CONTROL_ASSET_DIR = Path(__file__).resolve().parents[2] / "assets" / "icons"


def _control_image(master: tk.Misc, name: str) -> tk.PhotoImage:
    return tk.PhotoImage(master=master, file=CONTROL_ASSET_DIR / name)


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
        self._black_image = _control_image(
            self,
            "settings-pill-black-86x38.png",
        )
        self._hover_image = _control_image(
            self,
            "settings-pill-black-hover-86x38.png",
        )
        self._soft_image = _control_image(
            self,
            "settings-pill-soft-86x38.png",
        )
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
        if self._selected:
            image = self._hover_image if self._hovered else self._black_image
            self.create_image(width // 2, height // 2, image=image)
        elif self._hovered:
            self.create_image(width // 2, height // 2, image=self._soft_image)
        self.create_text(
            width // 2,
            height // 2,
            text=self._text,
            fill=ON_PRIMARY if self._selected else INK,
            font=(FONT_FAMILY, 10, "bold" if self._selected else "normal"),
        )


class PrimaryButton(tk.Canvas):
    def __init__(
        self,
        master: tk.Misc,
        text: str,
        command: Callable[[], None],
        *,
        width: int = 128,
    ) -> None:
        super().__init__(
            master,
            width=width,
            height=40,
            bg=CANVAS,
            borderwidth=0,
            highlightthickness=0,
            cursor="hand2",
            takefocus=True,
        )
        self._text = text
        self._command = command
        self._enabled = True
        self._hovered = False
        self._black_image = _control_image(
            self,
            f"settings-pill-black-{width}x40.png",
        )
        self._hover_image = _control_image(
            self,
            f"settings-pill-black-hover-{width}x40.png",
        )
        self._soft_image = _control_image(
            self,
            f"settings-pill-soft-{width}x40.png",
        )
        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._invoke)
        self.bind("<Return>", self._invoke)
        self.bind("<space>", self._invoke)

    def set_state(self, text: str, *, enabled: bool) -> None:
        self._text = text
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def _invoke(self, _event: tk.Event | None = None) -> None:
        if self._enabled:
            self._command()

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
        image = (
            self._hover_image
            if self._enabled and self._hovered
            else self._black_image if self._enabled else self._soft_image
        )
        self.create_image(width // 2, height // 2, image=image)
        self.create_text(
            width // 2,
            height // 2,
            text=self._text,
            fill=ON_PRIMARY if self._enabled else INK,
            font=(FONT_FAMILY, 9, "bold"),
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
        self._off_image = _control_image(
            self,
            "settings-toggle-off-104x38.png",
        )
        self._on_image = _control_image(
            self,
            "settings-toggle-on-104x38.png",
        )
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
        self.create_image(
            width // 2,
            height // 2,
            image=self._on_image if enabled else self._off_image,
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
        self._background_image = _control_image(
            self,
            "settings-pill-soft-104x36.png",
        )
        self.bind("<Configure>", lambda _event: self._draw())

    def _draw(self) -> None:
        width = max(2, self.winfo_width())
        height = max(2, self.winfo_height())
        self.delete("all")
        self.create_image(width // 2, height // 2, image=self._background_image)
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
        language: tk.StringVar,
        command: Callable[[], None],
    ) -> None:
        super().__init__(
            master,
            width=176,
            height=40,
            bg=CANVAS,
            borderwidth=0,
            highlightthickness=0,
            cursor="hand2",
            takefocus=True,
        )
        self._theme_key = theme_key
        self._variable = variable
        self._language = language
        self._command = command
        self._selected_image = _control_image(
            self,
            "settings-option-black-176x40.png",
        )
        self._default_image = _control_image(
            self,
            "settings-option-soft-176x40.png",
        )
        self._swatch_image = _control_image(
            self,
            f"settings-swatch-{theme_key}-30x30.png",
        )
        self.bind("<Configure>", lambda _event: self.refresh())
        self.bind("<Button-1>", self._select)
        self.bind("<Return>", self._select)
        self.bind("<space>", self._select)

    def _select(self, _event: tk.Event | None = None) -> None:
        self._variable.set(self._theme_key)
        self._command()

    def refresh(self) -> None:
        selected = self._variable.get() == self._theme_key
        width = max(2, self.winfo_width())
        height = max(2, self.winfo_height())
        self.delete("all")
        self.create_image(
            width // 2,
            height // 2,
            image=self._selected_image if selected else self._default_image,
        )
        self.create_image(25, height // 2, image=self._swatch_image)
        self.create_text(
            52,
            height // 2,
            text=theme_label(self._theme_key, self._language.get()),
            anchor="w",
            fill=ON_PRIMARY if selected else INK,
            font=(FONT_FAMILY, 9, "bold" if selected else "normal"),
        )


class ThemeSelector(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        variable: tk.StringVar,
        language: tk.StringVar,
        command: Callable[[], None],
    ) -> None:
        super().__init__(master, bg=CANVAS, borderwidth=0)
        self._variable = variable
        self._command = command
        self.options: list[ThemeOption] = []
        for index, key in enumerate(THEME_KEYS):
            option = ThemeOption(self, key, variable, language, self._select)
            option.grid(
                row=index // 3,
                column=index % 3,
                padx=4,
                pady=2,
            )
            self.options.append(option)
        self.grid_anchor("center")

    def _select(self) -> None:
        self.refresh()
        self._command()

    def refresh(self) -> None:
        for option in self.options:
            option.refresh()


class LanguageSelector(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        variable: tk.StringVar,
        command: Callable[[], None],
    ) -> None:
        super().__init__(master, bg=CANVAS, borderwidth=0)
        self._variable = variable
        self._command = command
        self._buttons: dict[str, PillButton] = {}
        for code, label in (
            ("zh-CN", tr("language_chinese", variable.get())),
            ("en", tr("language_english", variable.get())),
        ):
            button = PillButton(
                self,
                label,
                command=lambda value=code: self._select(value),
            )
            button.pack(side="left", padx=(0, 8) if code == "zh-CN" else 0)
            self._buttons[code] = button
        self.refresh()

    def _select(self, language: str) -> None:
        self._variable.set(language)
        self.refresh()
        self._command()

    def refresh(self) -> None:
        for code, button in self._buttons.items():
            button.set_selected(code == self._variable.get())


class SettingsWindow(tk.Toplevel):
    """Taskbar-visible settings window with automatically persisted changes."""

    def __init__(
        self,
        master: tk.Misc,
        settings: AppSettings,
        on_change: Callable[[AppSettings], bool],
        on_close: Callable[[], None],
        on_activate: Callable[[], None],
        update_check: Callable[[], UpdateResult] | None = None,
        download_update: (
            Callable[[UpdateResult, Callable[[int, int], None] | None], DownloadedUpdate]
            | None
        ) = None,
        install_update: Callable[[DownloadedUpdate], None] | None = None,
        open_url: Callable[[str], object] | None = None,
    ) -> None:
        super().__init__(master)
        self.resizable(False, False)
        self.configure(bg=CANVAS)
        self._on_change = on_change
        self._on_close = on_close
        self._on_activate = on_activate
        self._update_check = update_check or (lambda: check_for_updates(__version__))
        self._download_update = download_update or download_release_update
        self._install_update = install_update or launch_update_installer
        self._open_url = open_url or webbrowser.open
        self._update_events: queue.SimpleQueue[tuple[str, object]] = (
            queue.SimpleQueue()
        )
        self._update_checking = False
        self._accepted = replace(settings)
        self._restoring = False
        self._open_at_login = tk.BooleanVar(value=settings.open_at_login)
        self._default_color = tk.StringVar(value=settings.default_color)
        self._notes_pinned = tk.BooleanVar(value=settings.notes_pinned)
        self._language = tk.StringVar(value=settings.language)
        self._pages: dict[str, tk.Frame] = {}
        self._nav_buttons: dict[str, PillButton] = {}
        self._refreshables: list[object] = []
        self._current_page = "general"

        self._build_ui()
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

    def _build_ui(self) -> None:
        self.title(tr("settings_title", self._language.get()))
        self._pages.clear()
        self._nav_buttons.clear()
        self._refreshables.clear()
        self._build_navigation()
        content = tk.Frame(self, bg=CANVAS, padx=28, pady=22)
        content.pack(fill="both", expand=True, side="top")
        self._pages["general"] = self._build_general_page(content)
        self._pages["notes"] = self._build_notes_page(content)
        self._pages["about"] = self._build_about_page(content)

        footer = tk.Frame(self, bg=CANVAS, height=38)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Frame(footer, bg=HAIRLINE, height=1).pack(fill="x", side="top")
        tk.Label(
            footer,
            text=tr("changes_saved", self._language.get()),
            bg=CANVAS,
            fg=INK,
            font=(MONO_FONT, 9),
        ).pack(side="right", padx=28, pady=(9, 0))

    def _rebuild_ui(self) -> None:
        if not self.winfo_exists():
            return
        page = self._current_page
        for child in self.winfo_children():
            child.destroy()
        self._build_ui()
        self._show_page(page)

    def _build_navigation(self) -> None:
        navigation = tk.Frame(self, bg=CANVAS, height=72)
        navigation.pack(fill="x", side="top")
        navigation.pack_propagate(False)
        brand = tk.Frame(navigation, bg=CANVAS)
        brand.pack(side="left", padx=(28, 0), pady=14)
        tk.Label(
            brand,
            text=tr("settings", self._language.get()),
            bg=CANVAS,
            fg=INK,
            anchor="w",
            font=(MONO_FONT, 8),
        ).pack(anchor="w")
        tk.Label(
            brand,
            text=tr("app_name", self._language.get()),
            bg=CANVAS,
            fg=INK,
            anchor="w",
            font=(FONT_FAMILY, 14, "bold"),
        ).pack(anchor="w")
        tabs = tk.Frame(navigation, bg=CANVAS)
        tabs.pack(side="right", padx=28, pady=17)
        for key, label in (
            ("general", tr("general", self._language.get())),
            ("notes", tr("notes", self._language.get())),
            ("about", tr("about", self._language.get())),
        ):
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
            tr("general", self._language.get()),
            tr("general_description", self._language.get()),
        )
        self._setting_card(
            body,
            BLOCK_LIME,
            tr("autostart", self._language.get()),
            tr("autostart_description", self._language.get()),
            lambda row: self._toggle(row, self._open_at_login),
        )
        self._setting_card(
            body,
            BLOCK_LIME,
            tr("language", self._language.get()),
            tr("language_description", self._language.get()),
            self._language_control,
        )
        return page

    def _language_control(self, master: tk.Misc) -> LanguageSelector:
        control = LanguageSelector(master, self._language, self._commit)
        self._refreshables.append(control)
        return control

    def _build_notes_page(self, master: tk.Misc) -> tk.Frame:
        page, body = self._page(
            master,
            BLOCK_LILAC,
            tr("notes", self._language.get()),
            tr("notes_description", self._language.get()),
        )
        color_card = RoundedPanel(
            body,
            outer=BLOCK_LILAC,
            fill=CANVAS,
            radius=24,
            padding=14,
            height=218,
            outline=HAIRLINE,
        )
        color_card.pack(fill="x", pady=(0, 12))
        tk.Label(
            color_card.content,
            text=tr("note_color", self._language.get()),
            bg=CANVAS,
            fg=INK,
            anchor="w",
            font=(FONT_FAMILY, 11, "bold"),
        ).pack(fill="x")
        tk.Label(
            color_card.content,
            text=tr("note_color_description", self._language.get()),
            bg=CANVAS,
            fg=INK,
            anchor="w",
            font=(FONT_FAMILY, 9),
        ).pack(fill="x", pady=(2, 6))
        selector = ThemeSelector(
            color_card.content,
            self._default_color,
            self._language,
            self._commit,
        )
        selector.pack(fill="x")
        self._refreshables.append(selector)
        self._setting_card(
            body,
            BLOCK_LILAC,
            tr("notes_pinned", self._language.get()),
            tr("notes_pinned_description", self._language.get()),
            lambda row: self._toggle(row, self._notes_pinned),
        )
        return page

    def _build_about_page(self, master: tk.Misc) -> tk.Frame:
        page, body = self._page(
            master,
            BLOCK_CREAM,
            tr("about", self._language.get()),
            tr("about_description", self._language.get()),
        )
        self._setting_card(
            body,
            BLOCK_CREAM,
            tr("current_version", self._language.get()),
            tr("current_version_description", self._language.get()),
            lambda row: StatusPill(row, f"v{__version__}"),
        )

        update_card = RoundedPanel(
            body,
            outer=BLOCK_CREAM,
            fill=CANVAS,
            radius=24,
            padding=14,
            height=138,
            outline=HAIRLINE,
        )
        update_card.pack(fill="x", pady=(0, 12))
        text = tk.Frame(update_card.content, bg=CANVAS)
        text.pack(side="left", fill="both", expand=True)
        tk.Label(
            text,
            text=tr("software_update", self._language.get()),
            bg=CANVAS,
            fg=INK,
            anchor="w",
            font=(FONT_FAMILY, 11, "bold"),
        ).pack(fill="x")
        self._update_status_label = tk.Label(
            text,
            text=tr("update_idle", self._language.get()),
            bg=CANVAS,
            fg=INK,
            anchor="w",
            font=(FONT_FAMILY, 10, "bold"),
        )
        self._update_status_label.pack(fill="x", pady=(8, 0))
        self._update_detail_label = tk.Label(
            text,
            text=tr("update_idle_detail", self._language.get()),
            bg=CANVAS,
            fg=INK,
            anchor="w",
            justify="left",
            wraplength=390,
            font=(FONT_FAMILY, 9),
        )
        self._update_detail_label.pack(fill="x", pady=(3, 0))
        self._update_button = PrimaryButton(
            update_card.content,
            tr("check_update", self._language.get()),
            self._handle_update_action,
        )
        self._update_button.pack(side="right", padx=(22, 0), pady=30)

        source = tk.Frame(body, bg=BLOCK_CREAM)
        source.pack(fill="x", padx=6, pady=(2, 0))
        tk.Label(
            source,
            text=tr("open_source_prefix", self._language.get()),
            bg=BLOCK_CREAM,
            fg=INK,
            font=(FONT_FAMILY, 8),
        ).pack(side="left")
        link = tk.Label(
            source,
            text="github.com/LLYYXX/my-sticky-notes",
            bg=BLOCK_CREAM,
            fg=INK,
            cursor="hand2",
            font=(FONT_FAMILY, 8, "underline"),
        )
        link.pack(side="left")
        link.bind("<Button-1>", lambda _event: self._open_url(PROJECT_URL))
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
            padding=22,
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
        ).pack(fill="x", pady=(3, 12))
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
            padding=14,
            height=78,
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
        control_factory(card.content).pack(side="right", padx=(18, 0), pady=4)

    def _toggle(self, master: tk.Misc, variable: tk.BooleanVar) -> ToggleSwitch:
        control = ToggleSwitch(master, variable, self._commit)
        self._refreshables.append(control)
        return control

    def _show_page(self, key: str) -> None:
        self._current_page = key
        for page in self._pages.values():
            page.pack_forget()
        self._pages[key].pack(fill="both", expand=True)
        for page_key, button in self._nav_buttons.items():
            button.set_selected(page_key == key)

    def _current_settings(self) -> AppSettings:
        return AppSettings(
            default_color=self._default_color.get(),
            notes_pinned=self._notes_pinned.get(),
            open_at_login=self._open_at_login.get(),
            language=self._language.get(),
        )

    def _commit(self) -> None:
        if self._restoring:
            return
        settings = self._current_settings()
        if self._on_change(settings):
            language_changed = settings.language != self._accepted.language
            self._accepted = replace(settings)
            self._refresh_controls()
            if language_changed:
                self.after_idle(self._rebuild_ui)
            return
        self._restoring = True
        try:
            self._open_at_login.set(self._accepted.open_at_login)
            self._default_color.set(self._accepted.default_color)
            self._notes_pinned.set(self._accepted.notes_pinned)
            self._language.set(self._accepted.language)
            self._refresh_controls()
        finally:
            self._restoring = False

    def _refresh_controls(self) -> None:
        for control in self._refreshables:
            control.refresh()

    def _handle_update_action(self) -> None:
        self._start_update_check()

    def _start_update_check(self) -> None:
        if self._update_checking:
            return
        self._update_checking = True
        language = self._language.get()
        self._update_status_label.configure(text=tr("update_checking", language))
        self._update_detail_label.configure(text=tr("update_connecting", language))
        self._update_button.set_state(tr("checking", language), enabled=False)

        def worker() -> None:
            try:
                result = self._update_check()
                if not result.update_available:
                    self._update_events.put(("current", result))
                    return
                self._update_events.put(("available", result))
                last_percent = -1

                def report_progress(downloaded: int, expected: int) -> None:
                    nonlocal last_percent
                    if expected <= 0:
                        return
                    percent = min(100, int(downloaded * 100 / expected))
                    if percent != last_percent:
                        last_percent = percent
                        self._update_events.put(("progress", percent))

                downloaded = self._download_update(result, report_progress)
                self._update_events.put(("downloaded", downloaded))
            except UpdateCheckError as exc:
                self._update_events.put(("error", exc))
            except Exception:
                self._update_events.put(
                    ("error", UpdateCheckError("update_error_unknown"))
                )

        threading.Thread(
            target=worker,
            name="sticky-notes-update-check",
            daemon=True,
        ).start()
        self.after(80, self._poll_update_check)

    def _poll_update_check(self) -> None:
        if not self.winfo_exists():
            return
        try:
            kind, payload = self._update_events.get_nowait()
        except queue.Empty:
            if self._update_checking:
                self.after(80, self._poll_update_check)
            return

        language = self._language.get()
        if kind == "error":
            self._update_checking = False
            error = payload
            detail = (
                tr(error.code, language, **error.values)
                if isinstance(error, UpdateCheckError)
                else tr("update_error_unknown", language)
            )
            self._update_status_label.configure(text=tr("update_failed", language))
            self._update_detail_label.configure(text=detail)
            self._update_button.set_state(tr("retry", language), enabled=True)
            return

        if kind == "available" and isinstance(payload, UpdateResult):
            self._update_status_label.configure(
                text=tr(
                    "update_downloading",
                    language,
                    version=payload.latest_version,
                )
            )
            self._update_detail_label.configure(
                text=tr("update_download_progress", language, percent=0)
            )
            self.after(80, self._poll_update_check)
            return

        if kind == "progress":
            self._update_detail_label.configure(
                text=tr("update_download_progress", language, percent=int(payload))
            )
            self.after(80, self._poll_update_check)
            return

        if kind == "downloaded" and isinstance(payload, DownloadedUpdate):
            self._update_status_label.configure(text=tr("update_installing", language))
            self._update_detail_label.configure(
                text=payload.installer_path.name
            )
            try:
                self._install_update(payload)
            except UpdateCheckError as exc:
                self._update_events.put(("error", exc))
                self.after(0, self._poll_update_check)
                return
            except Exception:
                self._update_events.put(
                    ("error", UpdateCheckError("update_error_launch"))
                )
                self.after(0, self._poll_update_check)
                return
            self._update_checking = False
            self._update_status_label.configure(
                text=tr("update_installer_started", language)
            )
            self._update_detail_label.configure(
                text=tr("update_installer_started_detail", language)
            )
            self._update_button.set_state(tr("check_again", language), enabled=True)
            return

        if kind == "current" and isinstance(payload, UpdateResult):
            self._update_checking = False
            self._update_status_label.configure(text=tr("update_current", language))
            self._update_detail_label.configure(
                text=tr(
                    "update_current_detail",
                    language,
                    current=payload.current_version,
                    latest=payload.latest_version,
                )
            )
            self._update_button.set_state(tr("check_again", language), enabled=True)
            return

        self._update_events.put(
            ("error", UpdateCheckError("update_error_invalid_info"))
        )
        self.after(0, self._poll_update_check)

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
