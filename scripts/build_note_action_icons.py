from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "assets" / "icons"
VIEWBOX = 24
OUTPUT_SIZE = 20
SCALE = 12
STROKE = 2 * SCALE


def _round_line(points: tuple[tuple[int, int], ...]) -> Image.Image:
    image = Image.new("RGBA", (VIEWBOX * SCALE, VIEWBOX * SCALE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    scaled = [(x * SCALE, y * SCALE) for x, y in points]
    draw.line(scaled, fill=(0, 0, 0, 255), width=STROKE, joint="curve")
    radius = STROKE // 2
    for x, y in scaled:
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=(0, 0, 0, 255),
        )
    return image.resize((OUTPUT_SIZE, OUTPUT_SIZE), Image.Resampling.LANCZOS)


def main() -> None:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    icons = {
        "chevron-down": ((6, 9), (12, 15), (18, 9)),
        "minus": ((5, 12), (19, 12)),
    }
    for name, points in icons.items():
        _round_line(points).save(ICON_DIR / f"{name}.png")


if __name__ == "__main__":
    main()
