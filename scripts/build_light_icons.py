from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "assets" / "icons"
SOURCE_NAMES = (
    "add",
    "chevron-down",
    "delete",
    "minus",
    "palette",
    "pin",
    "checkbox-off",
    "checkbox-on",
    "resize-corner",
)
LIGHT = (255, 255, 255)


def main() -> None:
    for name in SOURCE_NAMES:
        source = Image.open(ICON_DIR / f"{name}.png").convert("RGBA")
        for y in range(source.height):
            for x in range(source.width):
                alpha = source.getpixel((x, y))[3]
                source.putpixel(
                    (x, y),
                    (*LIGHT, alpha) if alpha else (0, 0, 0, 0),
                )
        source.save(ICON_DIR / f"{name}-light.png")


if __name__ == "__main__":
    main()
