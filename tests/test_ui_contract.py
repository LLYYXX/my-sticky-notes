from __future__ import annotations

import inspect
import unittest

from sticky_notes.ui.title_bar import TitleBar


class TitleBarContractTests(unittest.TestCase):
    def test_title_bar_does_not_expose_obsolete_more_action(self) -> None:
        parameters = inspect.signature(TitleBar.__init__).parameters

        self.assertNotIn("on_more", parameters)
        self.assertNotIn("on_hide", parameters)


if __name__ == "__main__":
    unittest.main()
