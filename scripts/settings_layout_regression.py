from __future__ import annotations

import json
import sys
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sticky_notes.model import AppSettings
from sticky_notes.platform.windows import enable_dpi_awareness
from sticky_notes.ui.settings_window import RoundedPanel, SettingsWindow


def _descendants(widget: tk.Misc) -> list[tk.Misc]:
    children: list[tk.Misc] = []
    for child in widget.winfo_children():
        children.append(child)
        children.extend(_descendants(child))
    return children


def main() -> int:
    enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    window = SettingsWindow(
        root,
        AppSettings(),
        lambda _settings: True,
        lambda: None,
        lambda: None,
    )
    try:
        window.geometry("780x660+20+20")
        evidence: dict[str, list[dict[str, int]]] = {}
        for page_name in ("general", "notes", "about"):
            window._show_page(page_name)
            window.update()
            panels = [
                child
                for child in _descendants(window._pages[page_name])
                if isinstance(child, RoundedPanel)
            ]
            cards = panels[1:]
            allocations = [
                {
                    "requested": int(card.cget("height")),
                    "actual": card.winfo_height(),
                }
                for card in cards
            ]
            evidence[page_name] = allocations
            clipped = [
                item for item in allocations if item["actual"] < item["requested"] - 1
            ]
            if clipped:
                raise AssertionError(
                    f"{page_name} contains vertically clipped cards: {clipped}"
                )
        print(json.dumps({"result": "passed", "pages": evidence}))
        return 0
    finally:
        if window.winfo_exists():
            window.destroy()
        root.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
