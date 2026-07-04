from __future__ import annotations

import unittest

from sticky_notes.theme import THEMES


class ThemeTests(unittest.TestCase):
    def test_editorial_palette_matches_design_tokens(self) -> None:
        expected = {
            "lime": "#DCEEB1",
            "lilac": "#C5B0F4",
            "cream": "#F4ECD6",
            "pink": "#EFD4D4",
            "mint": "#C8E6CD",
            "coral": "#F3C9B6",
            "navy": "#1F1D3D",
        }

        self.assertEqual(
            {key: THEMES[key].background for key in expected},
            expected,
        )

    def test_navy_uses_light_icons(self) -> None:
        self.assertEqual(THEMES["navy"].icon_tone, "light")


if __name__ == "__main__":
    unittest.main()
