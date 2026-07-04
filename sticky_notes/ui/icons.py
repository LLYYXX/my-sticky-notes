from __future__ import annotations

import tkinter as tk
from pathlib import Path


class IconSet:
    def __init__(self, root: tk.Misc) -> None:
        asset_dir = Path(__file__).resolve().parents[2] / "assets" / "icons"
        self.add = tk.PhotoImage(master=root, file=asset_dir / "add.png")
        self.delete = tk.PhotoImage(master=root, file=asset_dir / "delete.png")
        self.pin = tk.PhotoImage(master=root, file=asset_dir / "pin.png")
        self.checkbox_off = tk.PhotoImage(
            master=root, file=asset_dir / "checkbox-off.png"
        )
        self.checkbox_on = tk.PhotoImage(
            master=root, file=asset_dir / "checkbox-on.png"
        )
        self.resize_corner = tk.PhotoImage(
            master=root, file=asset_dir / "resize-corner.png"
        )
        self.add_light = tk.PhotoImage(
            master=root, file=asset_dir / "add-light.png"
        )
        self.delete_light = tk.PhotoImage(
            master=root, file=asset_dir / "delete-light.png"
        )
        self.pin_light = tk.PhotoImage(
            master=root, file=asset_dir / "pin-light.png"
        )
        self.checkbox_off_light = tk.PhotoImage(
            master=root, file=asset_dir / "checkbox-off-light.png"
        )
        self.checkbox_on_light = tk.PhotoImage(
            master=root, file=asset_dir / "checkbox-on-light.png"
        )
        self.resize_corner_light = tk.PhotoImage(
            master=root, file=asset_dir / "resize-corner-light.png"
        )

    def themed(self, name: str, icon_tone: str) -> tk.PhotoImage:
        if icon_tone == "light":
            return getattr(self, f"{name}_light")
        return getattr(self, name)
