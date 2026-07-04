from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image


class AssetTests(unittest.TestCase):
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
