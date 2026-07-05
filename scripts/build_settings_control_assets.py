from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "assets" / "icons"
SCALE = 4
SWATCHES = {
    "yellow": "#FFF1A8",
    "offwhite": "#F0F0EC",
    "lime": "#DCEEB1",
    "lilac": "#C5B0F4",
    "cream": "#F4ECD6",
    "pink": "#EFD4D4",
    "mint": "#C8E6CD",
    "coral": "#F3C9B6",
    "navy": "#1F1D3D",
}


def rounded_asset(
    name: str,
    width: int,
    height: int,
    fill: str,
) -> None:
    size = (width * SCALE, height * SCALE)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        (0, 0, size[0] - 1, size[1] - 1),
        radius=height * SCALE // 2,
        fill=fill,
    )
    canvas = canvas.resize((width, height), Image.Resampling.LANCZOS)
    canvas.save(ICON_DIR / name)


def toggle_asset(name: str, *, enabled: bool) -> None:
    width, height = 104, 38
    size = (width * SCALE, height * SCALE)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    track = "#000000" if enabled else "#F7F7F5"
    knob = "#FFFFFF" if enabled else "#000000"
    draw.rounded_rectangle(
        (0, 0, size[0] - 1, size[1] - 1),
        radius=height * SCALE // 2,
        fill=track,
    )
    margin = 5 * SCALE
    diameter = 28 * SCALE
    left = (width - 5 - 28) * SCALE if enabled else margin
    draw.ellipse(
        (left, margin, left + diameter, margin + diameter),
        fill=knob,
    )
    canvas = canvas.resize((width, height), Image.Resampling.LANCZOS)
    canvas.save(ICON_DIR / name)


def main() -> None:
    for width, height in ((86, 38), (128, 40)):
        rounded_asset(
            f"settings-pill-black-{width}x{height}.png",
            width,
            height,
            "#000000",
        )
        rounded_asset(
            f"settings-pill-black-hover-{width}x{height}.png",
            width,
            height,
            "#292929",
        )
        rounded_asset(
            f"settings-pill-soft-{width}x{height}.png",
            width,
            height,
            "#F7F7F5",
        )
    rounded_asset(
        "settings-pill-soft-104x36.png",
        104,
        36,
        "#F7F7F5",
    )
    toggle_asset("settings-toggle-off-104x38.png", enabled=False)
    toggle_asset("settings-toggle-on-104x38.png", enabled=True)
    rounded_asset("settings-option-soft-176x40.png", 176, 40, "#F7F7F5")
    rounded_asset("settings-option-black-176x40.png", 176, 40, "#000000")
    for key, color in SWATCHES.items():
        rounded_asset(f"settings-swatch-{key}-30x30.png", 30, 30, color)


if __name__ == "__main__":
    main()
