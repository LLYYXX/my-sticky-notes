from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sticky_notes.controller import StickyNotesController
from sticky_notes.platform.windows import enable_dpi_awareness
from sticky_notes.store import StateStore
from sticky_notes.theme import THEMES
from sticky_notes.update_checker import DownloadedUpdate, UpdateCheckError, UpdateResult


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic visual QA states.")
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--settings", action="store_true")
    parser.add_argument(
        "--settings-page",
        choices=("general", "about"),
        default="general",
    )
    parser.add_argument("--palette", action="store_true")
    parser.add_argument("--theme", choices=tuple(THEMES), default=None)
    parser.add_argument("--language", choices=("zh-CN", "en"), default=None)
    parser.add_argument(
        "--update-state",
        choices=("idle", "current", "available", "error"),
        default="idle",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    enable_dpi_awareness()
    controller = StickyNotesController(StateStore(args.state))
    if args.language is not None:
        controller.state.settings.language = args.language
    if args.theme is not None:
        for note in controller.state.notes:
            note.color = args.theme
    for note in list(controller.state.notes):
        controller._open_note(note)
    if args.settings:
        def open_settings() -> None:
            controller.open_settings()
            if controller.settings_window is not None:
                window = controller.settings_window
                window._show_page(args.settings_page)
                if args.update_state == "current":
                    window._update_check = lambda: UpdateResult(
                        current_version="0.2.0",
                        latest_version="0.2.0",
                        release_url=(
                            "https://github.com/LLYYXX/my-sticky-notes/"
                            "releases/tag/v0.2.0"
                        ),
                        update_available=False,
                    )
                    window._start_update_check()
                elif args.update_state == "available":
                    window._update_check = lambda: UpdateResult(
                        current_version="0.2.0",
                        latest_version="0.3.0",
                        release_url=(
                            "https://github.com/LLYYXX/my-sticky-notes/"
                            "releases/tag/v0.3.0"
                        ),
                        update_available=True,
                    )
                    window._download_update = (
                        lambda result, progress: DownloadedUpdate(
                            result.latest_version,
                            args.state.parent
                            / f"My Sticky Notes Setup {result.latest_version}.exe",
                        )
                    )
                    window._install_update = lambda _update: None
                    window._start_update_check()
                elif args.update_state == "error":
                    def fail_update_check() -> UpdateResult:
                        raise UpdateCheckError("无法连接 GitHub，请检查网络后重试")

                    window._update_check = fail_update_check
                    window._start_update_check()

        controller.root.after(200, open_settings)
    elif args.palette:
        def open_palette() -> None:
            first = next(iter(controller.windows.values()), None)
            if first is not None:
                first.title_bar._toggle_palette()

        controller.root.after(200, open_palette)
    controller.root.mainloop()


if __name__ == "__main__":
    main()
