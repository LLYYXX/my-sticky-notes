from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sticky_notes.controller import StickyNotesController
from sticky_notes.store import StateStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic visual QA states.")
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--settings", action="store_true")
    parser.add_argument(
        "--settings-page",
        choices=("general", "notes"),
        default="general",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    controller = StickyNotesController(StateStore(args.state))
    for note in list(controller.state.notes):
        controller._open_note(note)
    if args.settings:
        def open_settings() -> None:
            controller.open_settings()
            if controller.settings_window is not None:
                controller.settings_window._show_page(args.settings_page)

        controller.root.after(200, open_settings)
    controller.root.mainloop()


if __name__ == "__main__":
    main()
