from __future__ import annotations

import sys

from sticky_notes.controller import StickyNotesController
from sticky_notes.platform.single_instance import SingleInstance
from sticky_notes.platform.windows import enable_dpi_awareness


def main() -> None:
    enable_dpi_awareness()
    instance = SingleInstance()
    if not instance.acquire():
        instance.signal_existing()
        return
    try:
        StickyNotesController(
            launched_at_login="--autostart" in sys.argv,
            instance=instance,
        ).run()
    finally:
        instance.close()


if __name__ == "__main__":
    main()
