from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PALETTE = (
    ("LIME", "#DCEEB1"),
    ("LILAC", "#C5B0F4"),
    ("CREAM", "#F4ECD6"),
    ("PINK", "#EFD4D4"),
    ("MINT", "#C8E6CD"),
    ("CORAL", "#F3C9B6"),
    ("NAVY", "#1F1D3D"),
)
RULES = (
    "WHITE EDITORIAL FRAME",
    "ONE PASTEL BLOCK PER VIEW",
    "BLACK SELECTED PILL",
    "24 PX PANEL RADIUS",
    "HAIRLINE CARD BORDERS",
    "NO SHADOWS OR GRADIENTS",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("implementation", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--focused-output", type=Path)
    return parser.parse_args()


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(Path("C:/Windows/Fonts") / name, size)


def draw_source_panel(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.text((x, y), "SOURCE DESIGN TOKENS", fill="#000000", font=font("consola.ttf", 20))
    draw.text((x, y + 40), "MONOCHROME CORE", fill="#000000", font=font("seguisb.ttf", 34))
    draw.rounded_rectangle((x, y + 96, x + 180, y + 142), radius=23, fill="#000000")
    draw.text((x + 38, y + 106), "SELECTED", fill="#FFFFFF", font=font("segoeui.ttf", 19))
    draw.rounded_rectangle(
        (x + 194, y + 96, x + 374, y + 142),
        radius=23,
        fill="#FFFFFF",
        outline="#E6E6E6",
        width=2,
    )
    draw.text((x + 241, y + 106), "DEFAULT", fill="#000000", font=font("segoeui.ttf", 19))
    draw.text((x, y + 178), "PASTEL COLOR BLOCKS", fill="#000000", font=font("consola.ttf", 17))
    for index, (label, color) in enumerate(PALETTE):
        row = index // 2
        column = index % 2
        left = x + column * 208
        top = y + 214 + row * 80
        draw.rounded_rectangle((left, top, left + 62, top + 56), radius=10, fill=color)
        label_color = "#FFFFFF" if label == "NAVY" else "#000000"
        draw.text((left + 13, top + 18), label[:1], fill=label_color, font=font("seguisb.ttf", 18))
        draw.text((left + 76, top + 16), label, fill="#000000", font=font("segoeui.ttf", 17))
        draw.text((left + 76, top + 37), color, fill="#000000", font=font("consola.ttf", 12))
    draw.text((x, y + 552), "IMPLEMENTATION RULES", fill="#000000", font=font("consola.ttf", 17))
    for index, rule in enumerate(RULES):
        draw.ellipse((x, y + 590 + index * 39, x + 10, y + 600 + index * 39), fill="#000000")
        draw.text((x + 24, y + 580 + index * 39), rule, fill="#000000", font=font("segoeui.ttf", 16))


def fit(image: Image.Image, width: int, height: int) -> Image.Image:
    scale = min(width / image.width, height / image.height)
    return image.resize(
        (round(image.width * scale), round(image.height * scale)),
        Image.Resampling.LANCZOS,
    )


def main() -> int:
    args = parse_args()
    implementation = Image.open(args.implementation).convert("RGB")
    board = Image.new("RGB", (1600, 960), "#FFFFFF")
    draw = ImageDraw.Draw(board)
    draw_source_panel(draw, 54, 42)
    draw.line((520, 0, 520, board.height), fill="#E6E6E6", width=2)
    draw.text((566, 42), "RENDERED IMPLEMENTATION", fill="#000000", font=font("consola.ttf", 20))
    rendered = fit(implementation, 980, 850)
    board.paste(rendered, (566 + (980 - rendered.width) // 2, 92))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    board.save(args.output)

    if args.focused_output is not None:
        focused = Image.new("RGB", (1500, 560), "#FFFFFF")
        focus_draw = ImageDraw.Draw(focused)
        focus_draw.text((48, 34), "SOURCE PALETTE", fill="#000000", font=font("consola.ttf", 18))
        for index, (label, color) in enumerate(PALETTE):
            top = 78 + index * 62
            focus_draw.rounded_rectangle((48, top, 108, top + 46), radius=8, fill=color)
            focus_draw.text((126, top + 4), label, fill="#000000", font=font("seguisb.ttf", 17))
            focus_draw.text((126, top + 25), color, fill="#000000", font=font("consola.ttf", 12))
        focus_draw.line((360, 0, 360, focused.height), fill="#E6E6E6", width=2)
        focus_draw.text((402, 34), "IMPLEMENTED THEME SELECTOR", fill="#000000", font=font("consola.ttf", 18))
        crop = implementation.crop(
            (
                round(implementation.width * 0.075),
                round(implementation.height * 0.34),
                round(implementation.width * 0.93),
                round(implementation.height * 0.75),
            )
        )
        crop = fit(crop, 1040, 450)
        focused.paste(crop, (402 + (1040 - crop.width) // 2, 82))
        args.focused_output.parent.mkdir(parents=True, exist_ok=True)
        focused.save(args.focused_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
