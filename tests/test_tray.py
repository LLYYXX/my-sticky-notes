from __future__ import annotations

import unittest

from sticky_notes.platform.tray import build_tray_menu_spec


class TrayMenuTests(unittest.TestCase):
    def test_menu_is_the_application_control_center(self) -> None:
        items = build_tray_menu_spec(open_at_login=True)

        labels = [item.label for item in items]
        self.assertEqual(items[0].label, "新建便签")
        self.assertIn("设置…", labels)
        self.assertNotIn("隐藏全部便签", labels)
        self.assertNotIn("显示全部便签", labels)
        autostart = next(item for item in items if item.action == "autostart")
        self.assertTrue(autostart.checked)


if __name__ == "__main__":
    unittest.main()
