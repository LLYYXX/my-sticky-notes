from __future__ import annotations

import unittest
from unittest.mock import Mock

from sticky_notes.model import Note
from sticky_notes.ui.note_window import NoteWindow


class NoteWindowBehaviorTests(unittest.TestCase):
    def test_per_note_color_change_is_persisted(self) -> None:
        window = NoteWindow.__new__(NoteWindow)
        window.note = Note(color="yellow")
        window.controller = Mock()
        window.apply_theme = Mock()

        window._change_color("navy")

        self.assertEqual(window.note.color, "navy")
        window.apply_theme.assert_called_once_with()
        window.controller.schedule_save.assert_called_once_with()

    def test_invalid_color_is_ignored(self) -> None:
        window = NoteWindow.__new__(NoteWindow)
        window.note = Note(color="yellow")
        window.controller = Mock()
        window.apply_theme = Mock()

        window._change_color("not-a-theme")

        self.assertEqual(window.note.color, "yellow")
        window.apply_theme.assert_not_called()
        window.controller.schedule_save.assert_not_called()

    def test_hide_withdraws_only_this_note(self) -> None:
        window = NoteWindow.__new__(NoteWindow)
        window.window = Mock()
        window.window.winfo_exists.return_value = True
        window.title_bar = Mock()
        window.controller = Mock()
        window.update_geometry_model = Mock()

        window.hide()

        window.title_bar.close_palette.assert_called_once_with()
        window.update_geometry_model.assert_called_once_with()
        window.window.withdraw.assert_called_once_with()
        window.controller.schedule_save.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
