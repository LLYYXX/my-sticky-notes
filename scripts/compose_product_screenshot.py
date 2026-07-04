from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compose the README product image.")
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--light-note", type=Path, required=True)
    parser.add_argument("--dark-note", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def resize(image: Image.Image, width: int) -> Image.Image:
    height = round(image.height * width / image.width)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def main() -> int:
    args = parse_args()
    canvas = Image.new("RGB", (1440, 900), "#F7F7F5")
    settings = resize(Image.open(args.settings).convert("RGB"), 820)
    light_note = resize(Image.open(args.light_note).convert("RGB"), 360)
    dark_note = resize(Image.open(args.dark_note).convert("RGB"), 360)

    canvas.paste(settings, (48, 52))
    canvas.paste(light_note, (1018, 60))
    canvas.paste(dark_note, (928, 474))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output, optimize=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
