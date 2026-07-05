from __future__ import annotations

import unittest
from unittest.mock import patch

from sticky_notes.platform.windows import (
    WS_EX_APPWINDOW,
    WS_EX_TOOLWINDOW,
    settings_window_geometry,
    taskbar_extended_style,
    top_right_geometry,
)


class WindowGeometryTests(unittest.TestCase):
    def test_settings_geometry_scales_up_but_never_exceeds_work_area(self) -> None:
        scenarios = (
            ((0, 0, 1920, 1040), 1.0),
            ((0, 0, 1366, 728), 1.5),
            ((0, 0, 1024, 560), 1.25),
            ((0, 0, 800, 560), 1.0),
            ((1920, -200, 3200, 700), 2.0),
        )

        for work_area, scale in scenarios:
            with self.subTest(work_area=work_area, scale=scale):
                x, y, width, height = settings_window_geometry(
                    work_area,
                    ui_scale=scale,
                )
                left, top, right, bottom = work_area
                self.assertGreaterEqual(x, left)
                self.assertGreaterEqual(y, top)
                self.assertLessEqual(x + width, right)
                self.assertLessEqual(y + height, bottom)

    def test_settings_geometry_keeps_preferred_size_at_100_percent(self) -> None:
        self.assertEqual(
            settings_window_geometry((0, 0, 1920, 1040)),
            (565, 171, 780, 660),
        )

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
