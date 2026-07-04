from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "assets" / "icons"


def main() -> None:
    source = Image.open(ICON_DIR / "pin.png").convert("RGBA")
    canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        (18, 18, 238, 238),
        radius=48,
        fill="#FFF0A0",
        outline="#D9C35F",
        width=8,
    )
    pin = source.resize((142, 142), Image.Resampling.LANCZOS)
    canvas.alpha_composite(pin, ((256 - pin.width) // 2, 48))
    canvas.save(
        ICON_DIR / "tray.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)],
    )


if __name__ == "__main__":
    main()
