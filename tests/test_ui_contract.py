from __future__ import annotations

import inspect
import unittest

from sticky_notes.ui.settings_window import PillButton, PrimaryButton, SettingsWindow
from sticky_notes.ui.title_bar import TitleBar


class TitleBarContractTests(unittest.TestCase):
    def test_title_bar_does_not_expose_obsolete_more_action(self) -> None:
        parameters = inspect.signature(TitleBar.__init__).parameters

        self.assertNotIn("on_more", parameters)
        self.assertNotIn("on_hide", parameters)


class SettingsWindowContractTests(unittest.TestCase):
    def test_pill_buttons_use_antialiased_image_backgrounds(self) -> None:
        for button_class in (PillButton, PrimaryButton):
            source = inspect.getsource(button_class._draw)
            self.assertIn("create_image", source)
            self.assertNotIn("_rounded_rectangle", source)

    def test_taskbar_activation_callback_is_part_of_window_contract(self) -> None:
        parameters = inspect.signature(SettingsWindow.__init__).parameters

        self.assertIn("on_activate", parameters)
        self.assertIn("update_check", parameters)
        self.assertIn("download_update", parameters)
        self.assertIn("install_update", parameters)
        self.assertIn("open_url", parameters)


if __name__ == "__main__":
    unittest.main()
