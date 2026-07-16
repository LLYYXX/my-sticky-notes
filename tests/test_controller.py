from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import Mock, patch

from sticky_notes.controller import StickyNotesController
from sticky_notes.model import AppSettings, AppState, Note


class ControllerActivationTests(unittest.TestCase):
    def test_activate_workspace_raises_notes_then_settings(self) -> None:
        controller = StickyNotesController.__new__(StickyNotesController)
        note = Mock()
        note.window = Mock()
        settings = Mock()
        settings.winfo_exists.return_value = True
        controller.windows = {"note": note}
        controller.settings_window = settings

        with patch("sticky_notes.controller.bring_windows_to_front") as bring:
            controller.activate_workspace()

        self.assertEqual(bring.call_args.args[0], [note.window, settings])
        note.sync_topmost.assert_called_once_with()

    def test_settings_preserve_each_notes_color_and_pin(self) -> None:
        controller = StickyNotesController.__new__(StickyNotesController)
        first = Note(color="yellow", pinned=False)
        second = Note(color="navy", pinned=False)
        first_window = Mock()
        second_window = Mock()
        controller.state = AppState(notes=[first, second])
        controller.windows = {
            first.id: first_window,
            second.id: second_window,
        }
        controller.system_integration = False
        controller.settings_window = None
        controller.save_now = Mock()
        controller._update_tray_state = Mock()

        accepted = controller._save_settings(
            replace(AppSettings(), language="en")
        )

        self.assertTrue(accepted)
        self.assertEqual([note.color for note in controller.state.notes], ["yellow", "navy"])
        self.assertEqual([note.pinned for note in controller.state.notes], [False, False])
        first_window.apply_theme.assert_not_called()
        second_window.apply_theme.assert_not_called()
        first_window.set_pinned.assert_not_called()
        second_window.set_pinned.assert_not_called()
        first_window.refresh_language.assert_called_once_with()
        second_window.refresh_language.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
