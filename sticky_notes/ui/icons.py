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
