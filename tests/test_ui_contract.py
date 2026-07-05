from __future__ import annotations

import inspect
import unittest

from sticky_notes.ui.settings_window import (
    PillButton,
    PrimaryButton,
    RoundedPanel,
    ScrollablePageHost,
    SettingsWindow,
    responsive_column_count,
    should_stack_control,
)
from sticky_notes.ui.title_bar import TitleBar


class TitleBarContractTests(unittest.TestCase):
    def test_title_bar_does_not_expose_obsolete_more_action(self) -> None:
        parameters = inspect.signature(TitleBar.__init__).parameters

        self.assertNotIn("on_more", parameters)
        self.assertNotIn("on_hide", parameters)


class SettingsWindowContractTests(unittest.TestCase):
    def test_responsive_layout_rules_cover_narrow_and_wide_widths(self) -> None:
        self.assertEqual(responsive_column_count(700), 3)
        self.assertEqual(responsive_column_count(400), 2)
        self.assertEqual(responsive_column_count(240), 1)
        self.assertTrue(should_stack_control(400, 104))
        self.assertFalse(should_stack_control(640, 104))

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
        self.assertIn("work_area", parameters)

    def test_settings_layout_is_content_driven_and_scrollable(self) -> None:
        source = inspect.getsource(SettingsWindow)

        self.assertIn("ScrollablePageHost", source)
        self.assertNotIn("self.resizable(False, False)", source)

    def test_natural_height_changes_reach_the_scroll_host(self) -> None:
        panel_source = inspect.getsource(RoundedPanel)
        host_source = inspect.getsource(ScrollablePageHost)

        self.assertIn("_propagate_natural_size_change", panel_source)
        self.assertIn("ancestor.refresh()", panel_source)
        self.assertIn("self.content.winfo_reqheight()", host_source)


if __name__ == "__main__":
    unittest.main()
