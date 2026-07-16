from __future__ import annotations

import queue
import threading
import tkinter as tk
import webbrowser
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from .. import __version__
from ..i18n import tr
from ..model import AppSettings
from ..platform.windows import (
    primary_work_area,
    set_taskbar_visibility,
    settings_window_geometry,
)
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
BLOCK_CREAM = "#F4ECD6"
MONO_FONT = "Cascadia Mono"
CONTROL_ASSET_DIR = Path(__file__).resolve().parents[2] / "assets" / "icons"


def should_stack_control(
    available_width: int,
    control_width: int,
    *,
    minimum_text_width: int = 300,
    gap: int = 24,
) -> bool:
    return available_width < control_width + minimum_text_width + gap


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
        min_height: int | None = None,
        outline: str | None = None,
    ) -> None:
        super().__init__(
            master,
            bg=outer,
            borderwidth=0,
            highlightthickness=0,
            height=min_height or 1,
        )
        self._fill = fill
        self._radius = radius
        self._padding = padding
        self._outline = outline
        self._minimum_height = min_height or 1
        self.content = tk.Frame(self, bg=fill, borderwidth=0)
        self._content_window = self.create_window(
            (padding, padding),
            window=self.content,
            anchor="nw",
        )
        self.bind("<Configure>", self._redraw)
        self.content.bind("<Configure>", self._sync_natural_height, add="+")

    def _sync_natural_height(self, _event: tk.Event | None = None) -> None:
        required = max(
            self._minimum_height,
            self.content.winfo_reqheight() + self._padding * 2,
        )
        changed = int(float(self.cget("height"))) != required
        if changed:
            self.configure(height=required)
        self.after_idle(self._redraw)
        if changed:
            self._propagate_natural_size_change()

    def _propagate_natural_size_change(self) -> None:
        """Carry a changed size request through clipped canvas allocations.

        Tk emits ``<Configure>`` for allocated sizes, not for every requested-size
        change.  A panel inside a viewport can therefore ask for more height while
        its ancestors remain allocated to the old viewport height.  Walk to the
        nearest containing panel first, then let the page host recompute its
        scroll region from the fully propagated natural height.
        """
        ancestor = self.master
        while ancestor is not None:
            if isinstance(ancestor, RoundedPanel):
                ancestor.after_idle(ancestor._sync_natural_height)
                return
            if isinstance(ancestor, ScrollablePageHost):
                ancestor.refresh()
                return
            ancestor = getattr(ancestor, "master", None)

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
            height=max(
                self.content.winfo_reqheight(),
                height - self._padding * 2,
                1,
            ),
        )


class ScrollablePageHost(tk.Frame):
    """A page viewport that expands naturally and scrolls only when needed."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(
            master,
            bg=CANVAS,
            borderwidth=0,
            highlightthickness=0,
            padx=28,
            pady=22,
        )
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            self,
            bg=CANVAS,
            borderwidth=0,
            highlightthickness=0,
            yscrollincrement=24,
        )
        self.scrollbar = tk.Scrollbar(
            self,
            orient="vertical",
            command=self.canvas.yview,
            borderwidth=0,
            highlightthickness=0,
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.content = tk.Frame(
            self.canvas,
            bg=CANVAS,
            borderwidth=0,
            highlightthickness=0,
        )
        self._content_window = self.canvas.create_window(
            (0, 0),
            window=self.content,
            anchor="nw",
        )
        self._scrollbar_visible = False
        self.canvas.bind("<Configure>", self._sync_layout, add="+")
        self.content.bind("<Configure>", self._sync_layout, add="+")

    @property
    def overflow(self) -> bool:
        return self._scrollbar_visible

    def refresh(self) -> None:
        self.after_idle(self._sync_layout)

    def _sync_layout(self, _event: tk.Event | None = None) -> None:
        if not self.canvas.winfo_exists():
            return
        width = max(1, self.canvas.winfo_width())
        viewport_height = max(1, self.canvas.winfo_height())
        visible_pages = [
            child
            for child in self.content.winfo_children()
            if child.winfo_manager()
        ]
        natural_height = max(
            [self.content.winfo_reqheight()]
            + [page.winfo_reqheight() for page in visible_pages]
        )
        content_height = max(viewport_height, natural_height)
        self.canvas.itemconfigure(
            self._content_window,
            width=width,
            height=content_height,
        )
        self.canvas.configure(scrollregion=(0, 0, width, content_height))
        needs_scrollbar = content_height > viewport_height + 1
        if needs_scrollbar and not self._scrollbar_visible:
            self.scrollbar.grid(row=0, column=1, sticky="ns", padx=(6, 0))
            self._scrollbar_visible = True
        elif not needs_scrollbar and self._scrollbar_visible:
            self.scrollbar.grid_remove()
            self.canvas.yview_moveto(0.0)
            self._scrollbar_visible = False

    def on_mousewheel(self, event: tk.Event) -> str | None:
        if not self._scrollbar_visible:
            return None
        self.canvas.yview_scroll(int(-event.delta / 120), "units")
        return "break"


class PillButton(tk.Canvas):
    def __init__(
        self,
        master: tk.Misc,
        text: str,
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
        self._text = text
        self._command = command
        self._selected = False
        self._hovered = False
        self._black_image = _control_image(
            self,
            "settings-pill-black-104x38.png",
        )
        self._hover_image = _control_image(
            self,
            "settings-pill-black-hover-104x38.png",
        )
        self._soft_image = _control_image(
            self,
            "settings-pill-soft-104x38.png",
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
        work_area: tuple[int, int, int, int] | None = None,
    ) -> None:
        super().__init__(master)
        self.resizable(True, True)
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
        self._language = tk.StringVar(value=settings.language)
        self._pages: dict[str, tk.Frame] = {}
        self._nav_buttons: dict[str, PillButton] = {}
        self._refreshables: list[object] = []
        self._current_page = "general"
        self._work_area_override = work_area

        self._build_ui()
        self._show_page("general")
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda _event: self._close())
        self.bind("<Map>", self._on_map, add="+")
        self.bind("<FocusIn>", self._handle_activate, add="+")
        self.bind("<MouseWheel>", self._handle_mousewheel, add="+")
        self.update_idletasks()
        fallback = (
            0,
            0,
            self.winfo_screenwidth(),
            self.winfo_screenheight(),
        )
        area = self._work_area_override or primary_work_area(fallback)
        tk_scaling = float(self.tk.call("tk", "scaling"))
        ui_scale = tk_scaling / (96 / 72)
        x, y, width, height = settings_window_geometry(
            area,
            ui_scale=ui_scale,
        )
        min_width = min(width, max(360, round(560 * ui_scale)))
        min_height = min(height, max(320, round(420 * ui_scale)))
        self.minsize(min_width, min_height)
        self.maxsize(
            max(1, area[2] - area[0] - 32 - round(10 * ui_scale)),
            max(1, area[3] - area[1] - 32 - round(38 * ui_scale)),
        )
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
        footer = tk.Frame(self, bg=CANVAS)
        footer.pack(fill="x", side="bottom")
        tk.Frame(footer, bg=HAIRLINE, height=1).pack(fill="x", side="top")
        tk.Label(
            footer,
            text=tr("changes_saved", self._language.get()),
            bg=CANVAS,
            fg=INK,
            font=(MONO_FONT, 9),
        ).pack(side="right", padx=28, pady=(9, 9))
        self._content_host = ScrollablePageHost(self)
        self._content_host.pack(fill="both", expand=True, side="top")
        content = self._content_host.content
        self._pages["general"] = self._build_general_page(content)
        self._pages["about"] = self._build_about_page(content)

    def _rebuild_ui(self) -> None:
        if not self.winfo_exists():
            return
        page = self._current_page
        for child in self.winfo_children():
            child.destroy()
        self._build_ui()
        self._show_page(page)

    def _handle_mousewheel(self, event: tk.Event) -> str | None:
        return self._content_host.on_mousewheel(event)

    def _build_navigation(self) -> None:
        navigation = tk.Frame(self, bg=CANVAS)
        navigation.pack(fill="x", side="top")
        navigation.grid_columnconfigure(0, weight=1)
        brand = tk.Frame(navigation, bg=CANVAS)
        brand.grid(row=0, column=0, sticky="w", padx=(28, 0), pady=14)
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
        tabs.grid(row=0, column=1, sticky="e", padx=28, pady=17)
        for key, label in (
            ("general", tr("general", self._language.get())),
            ("about", tr("about", self._language.get())),
        ):
            button = PillButton(
                tabs,
                label,
                command=lambda page=key: self._show_page(page),
            )
            button.pack(side="left", padx=(8, 0))
            self._nav_buttons[key] = button

        def reflow(event: tk.Event) -> None:
            inline_width = brand.winfo_reqwidth() + tabs.winfo_reqwidth() + 84
            if event.width < inline_width:
                brand.grid_configure(
                    row=0,
                    column=0,
                    columnspan=2,
                    sticky="w",
                    pady=(12, 4),
                )
                tabs.grid_configure(
                    row=1,
                    column=0,
                    columnspan=2,
                    sticky="e",
                    pady=(0, 10),
                )
            else:
                brand.grid_configure(
                    row=0,
                    column=0,
                    columnspan=1,
                    sticky="w",
                    pady=14,
                )
                tabs.grid_configure(
                    row=0,
                    column=1,
                    columnspan=1,
                    sticky="e",
                    pady=17,
                )

        navigation.bind("<Configure>", reflow, add="+")
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
            min_height=138,
            outline=HAIRLINE,
        )
        update_card.pack(fill="x", pady=(0, 12))
        text = tk.Frame(update_card.content, bg=CANVAS)
        update_card.content.grid_columnconfigure(0, weight=1)
        text.grid(row=0, column=0, sticky="nsew")
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
        self._update_button.grid(
            row=0,
            column=1,
            sticky="e",
            padx=(22, 0),
            pady=30,
        )

        def reflow_update(event: tk.Event) -> None:
            stacked = should_stack_control(
                event.width,
                self._update_button.winfo_reqwidth(),
                minimum_text_width=340,
            )
            if stacked:
                self._update_button.grid_configure(
                    row=1,
                    column=0,
                    sticky="e",
                    padx=0,
                    pady=(12, 0),
                )
                self._update_detail_label.configure(
                    wraplength=max(180, event.width - 4)
                )
            else:
                self._update_button.grid_configure(
                    row=0,
                    column=1,
                    sticky="e",
                    padx=(22, 0),
                    pady=30,
                )
                self._update_detail_label.configure(
                    wraplength=max(
                        180,
                        event.width - self._update_button.winfo_reqwidth() - 30,
                    )
                )
            update_card.after_idle(update_card._sync_natural_height)

        update_card.content.bind("<Configure>", reflow_update, add="+")

        source = tk.Frame(body, bg=BLOCK_CREAM)
        source.pack(fill="x", padx=6, pady=(2, 0))
        source_prefix = tk.Label(
            source,
            text=tr("open_source_prefix", self._language.get()),
            bg=BLOCK_CREAM,
            fg=INK,
            font=(FONT_FAMILY, 8),
        )
        source_prefix.grid(row=0, column=0, sticky="w")
        link = tk.Label(
            source,
            text="github.com/LLYYXX/my-sticky-notes",
            bg=BLOCK_CREAM,
            fg=INK,
            cursor="hand2",
            font=(FONT_FAMILY, 8, "underline"),
        )
        link.grid(row=0, column=1, sticky="w")
        link.bind("<Button-1>", lambda _event: self._open_url(PROJECT_URL))

        def reflow_source(event: tk.Event) -> None:
            if event.width < source_prefix.winfo_reqwidth() + link.winfo_reqwidth():
                link.grid_configure(row=1, column=0, sticky="w", pady=(2, 0))
            else:
                link.grid_configure(row=0, column=1, sticky="w", pady=0)

        source.bind("<Configure>", reflow_source, add="+")
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
        description_label = tk.Label(
            panel.content,
            text=description,
            bg=block_color,
            fg=INK,
            anchor="w",
            justify="left",
            font=(FONT_FAMILY, 10),
        )
        description_label.pack(fill="x", pady=(3, 12))
        body = tk.Frame(panel.content, bg=block_color)
        body.pack(fill="both", expand=True)

        def wrap_description(event: tk.Event) -> None:
            description_label.configure(wraplength=max(180, event.width - 4))
            panel.after_idle(panel._sync_natural_height)

        panel.content.bind("<Configure>", wrap_description, add="+")
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
            min_height=78,
            outline=HAIRLINE,
        )
        card.pack(fill="x", pady=(0, 12))
        text = tk.Frame(card.content, bg=CANVAS)
        card.content.grid_columnconfigure(0, weight=1)
        text.grid(row=0, column=0, sticky="nsew")
        tk.Label(
            text,
            text=title,
            bg=CANVAS,
            fg=INK,
            anchor="w",
            font=(FONT_FAMILY, 11, "bold"),
        ).pack(fill="x")
        description_label = tk.Label(
            text,
            text=description,
            bg=CANVAS,
            fg=INK,
            anchor="w",
            justify="left",
            font=(FONT_FAMILY, 9),
        )
        description_label.pack(fill="x", pady=(3, 0))
        control = control_factory(card.content)
        control.grid(row=0, column=1, sticky="e", padx=(18, 0), pady=4)

        def reflow(event: tk.Event) -> None:
            stacked = should_stack_control(
                event.width,
                control.winfo_reqwidth(),
            )
            if stacked:
                control.grid_configure(
                    row=1,
                    column=0,
                    sticky="e",
                    padx=0,
                    pady=(10, 0),
                )
                description_label.configure(wraplength=max(160, event.width - 4))
            else:
                control.grid_configure(
                    row=0,
                    column=1,
                    sticky="e",
                    padx=(18, 0),
                    pady=4,
                )
                description_label.configure(
                    wraplength=max(
                        160,
                        event.width - control.winfo_reqwidth() - 24,
                    )
                )
            card.after_idle(card._sync_natural_height)

        card.content.bind("<Configure>", reflow, add="+")

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
        self._content_host.canvas.yview_moveto(0.0)
        self._content_host.refresh()

    def _current_settings(self) -> AppSettings:
        return AppSettings(
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
