from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image

from sticky_notes.theme import THEMES


class AssetTests(unittest.TestCase):
    def test_settings_button_backgrounds_are_antialiased(self) -> None:
        icon_dir = Path(__file__).resolve().parents[1] / "assets" / "icons"
        names = (
            "settings-pill-black-86x38.png",
            "settings-pill-black-hover-86x38.png",
            "settings-pill-soft-86x38.png",
            "settings-pill-black-128x40.png",
            "settings-pill-black-hover-128x40.png",
            "settings-pill-soft-128x40.png",
            "settings-pill-soft-104x36.png",
            "settings-toggle-off-104x38.png",
            "settings-toggle-on-104x38.png",
            "settings-option-soft-176x40.png",
            "settings-option-black-176x40.png",
        )

        for name in names:
            with self.subTest(name=name):
                image = Image.open(icon_dir / name).convert("RGBA")
                alphas = {
                    image.getpixel((x, y))[3]
                    for y in range(image.height)
                    for x in range(image.width)
                }
                self.assertTrue(any(0 < alpha < 255 for alpha in alphas))

    def test_toggle_assets_include_a_round_knob(self) -> None:
        icon_dir = Path(__file__).resolve().parents[1] / "assets" / "icons"
        off = Image.open(icon_dir / "settings-toggle-off-104x38.png").convert("RGBA")
        on = Image.open(icon_dir / "settings-toggle-on-104x38.png").convert("RGBA")

        self.assertEqual(off.getpixel((19, 19))[:3], (0, 0, 0))
        self.assertEqual(on.getpixel((85, 19))[:3], (255, 255, 255))

    def test_settings_theme_swatches_match_theme_tokens(self) -> None:
        icon_dir = Path(__file__).resolve().parents[1] / "assets" / "icons"

        for key, theme in THEMES.items():
            with self.subTest(theme=key):
                image = Image.open(
                    icon_dir / f"settings-swatch-{key}-30x30.png"
                ).convert("RGBA")
                self.assertEqual(
                    image.getpixel((image.width // 2, image.height // 2))[:3],
                    tuple(bytes.fromhex(theme.background.removeprefix("#"))),
                )

    def test_dark_note_theme_has_complete_light_icon_set(self) -> None:
        icon_dir = Path(__file__).resolve().parents[1] / "assets" / "icons"
        expected = {
            "add-light.png",
            "delete-light.png",
            "pin-light.png",
            "checkbox-off-light.png",
            "checkbox-on-light.png",
            "resize-corner-light.png",
        }

        self.assertTrue(expected.issubset({path.name for path in icon_dir.iterdir()}))

    def test_resize_grip_has_no_horizontal_bottom_edge(self) -> None:
        path = (
            Path(__file__).resolve().parents[1]
            / "assets"
            / "icons"
            / "resize-corner.png"
        )
        image = Image.open(path).convert("RGBA")

        widest_row = max(
            sum(image.getpixel((x, y))[3] >= 40 for x in range(image.width))
            for y in range(image.height)
        )

        self.assertLessEqual(widest_row, image.width // 2)


if __name__ == "__main__":
    unittest.main()
