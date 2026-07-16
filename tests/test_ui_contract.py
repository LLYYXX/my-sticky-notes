from __future__ import annotations

import inspect
import unittest

from sticky_notes.ui.settings_window import (
    PillButton,
    PrimaryButton,
    RoundedPanel,
    ScrollablePageHost,
    SettingsWindow,
    should_stack_control,
)
from sticky_notes.ui.title_bar import TitleBar
from sticky_notes.ui.todo_list import TodoList


class TitleBarContractTests(unittest.TestCase):
    def test_title_bar_exposes_the_requested_note_actions(self) -> None:
        parameters = inspect.signature(TitleBar.__init__).parameters

        self.assertIn("on_new", parameters)
        self.assertIn("on_color", parameters)
        self.assertIn("color_key", parameters)
        self.assertIn("on_collapse", parameters)
        self.assertNotIn("title", parameters)
        self.assertNotIn("on_title_change", parameters)
        self.assertNotIn("on_more", parameters)
        self.assertNotIn("on_hide", parameters)


class TodoListContractTests(unittest.TestCase):
    def test_rows_can_wrap_and_the_add_field_stays_in_the_list(self) -> None:
        row_source = inspect.getsource(TodoList._create_row)
        render_source = inspect.getsource(TodoList.render)

        self.assertIn("wraplength", row_source)
        self.assertNotIn("pack_propagate(False)", row_source)
        self.assertIn("self._create_add_row()", render_source)


class SettingsWindowContractTests(unittest.TestCase):
    def test_responsive_layout_rules_cover_narrow_and_wide_widths(self) -> None:
        self.assertTrue(should_stack_control(400, 104))
        self.assertFalse(should_stack_control(640, 104))

    def test_settings_contains_only_general_and_about_pages(self) -> None:
        build_source = inspect.getsource(SettingsWindow._build_ui)
        navigation_source = inspect.getsource(SettingsWindow._build_navigation)

        self.assertNotIn('self._pages["notes"]', build_source)
        self.assertNotIn('tr("notes"', navigation_source)

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
