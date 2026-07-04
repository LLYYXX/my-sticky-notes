from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from sticky_notes.controller import StickyNotesController


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


if __name__ == "__main__":
    unittest.main()
