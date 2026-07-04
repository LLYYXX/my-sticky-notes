from __future__ import annotations

import unittest
from unittest.mock import patch

from sticky_notes.platform.windows import (
    WS_EX_APPWINDOW,
    WS_EX_TOOLWINDOW,
    taskbar_extended_style,
    top_right_geometry,
)


class WindowGeometryTests(unittest.TestCase):
    def test_note_and_settings_use_opposite_taskbar_styles(self) -> None:
        note_style = taskbar_extended_style(WS_EX_APPWINDOW, visible=False)
        settings_style = taskbar_extended_style(WS_EX_TOOLWINDOW, visible=True)

        self.assertTrue(note_style & WS_EX_TOOLWINDOW)
        self.assertFalse(note_style & WS_EX_APPWINDOW)
        self.assertTrue(settings_style & WS_EX_APPWINDOW)
        self.assertFalse(settings_style & WS_EX_TOOLWINDOW)

    def test_new_note_uses_primary_work_area_top_right(self) -> None:
        with patch(
            "sticky_notes.platform.windows._monitor_work_areas",
            return_value=[(0, 0, 1920, 1040)],
        ):
            geometry = top_right_geometry(320, 360, (0, 0, 800, 600))

        self.assertEqual(geometry, (1584, 16, 320, 360))

    def test_new_note_fits_inside_small_work_area(self) -> None:
        with patch(
            "sticky_notes.platform.windows._monitor_work_areas",
            return_value=[(100, 50, 500, 350)],
        ):
            x, y, width, height = top_right_geometry(
                900, 700, (0, 0, 1920, 1080)
            )

        self.assertEqual((x, y), (100, 50))
        self.assertEqual((width, height), (400, 300))


if __name__ == "__main__":
    unittest.main()
