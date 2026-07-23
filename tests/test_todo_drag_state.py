from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

from sticky_notes.model import Todo
from sticky_notes.ui.todo_drag import FRAME_INTERVAL_MS, TodoDragController


@dataclass
class Event:
    y_root: int


class Widget:
    def __init__(
        self,
        *_args: Any,
        root_y: int = 0,
        y: int = 0,
        width: int = 300,
        height: int = 40,
        **_kwargs: Any,
    ) -> None:
        self.root_y = root_y
        self.y = y
        self.width = width
        self.height = height
        self.exists = True
        self.placed: list[dict[str, Any]] = []
        self.destroyed = False

    def winfo_rooty(self) -> int:
        return self.root_y

    def winfo_y(self) -> int:
        return self.y

    def winfo_width(self) -> int:
        return self.width

    def winfo_height(self) -> int:
        return self.height

    def winfo_reqheight(self) -> int:
        return self.height

    def winfo_exists(self) -> bool:
        return self.exists

    def place(self, **kwargs: Any) -> None:
        self.placed.append(kwargs)

    def lift(self) -> None:
        pass

    def destroy(self) -> None:
        self.exists = False
        self.destroyed = True


class Host(Widget):
    def __init__(self) -> None:
        super().__init__(root_y=100, width=300, height=300)
        self.jobs: dict[str, Any] = {}
        self.delays: list[int] = []
        self.cancelled: list[str] = []
        self._next_job = 0

    def after(self, delay: int, callback: Any) -> str:
        self._next_job += 1
        job = f"job-{self._next_job}"
        self.jobs[job] = callback
        self.delays.append(delay)
        return job

    def after_cancel(self, job: str) -> None:
        self.cancelled.append(job)
        self.jobs.pop(job, None)

    def run_next(self) -> None:
        job, callback = next(iter(self.jobs.items()))
        self.jobs.pop(job)
        callback()


class Canvas(Widget):
    def __init__(self) -> None:
        super().__init__(root_y=100, height=200)
        self.scrolls: list[tuple[int, str]] = []

    def yview_scroll(self, amount: int, unit: str) -> None:
        self.scrolls.append((amount, unit))


class TodoDragControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.host = Host()
        self.canvas = Canvas()
        self.content = Widget()
        self.rows = [
            ("a", Widget(root_y=110, y=0)),
            ("b", Widget(root_y=150, y=40)),
        ]
        self.todos = [Todo(id="a", text="A"), Todo(id="b", text="B")]
        self.ghosts: list[Widget] = []
        self.reorders: list[tuple[str, int]] = []

        def ghost_factory(_parent: Any, _todo: Todo, _theme: Any) -> Widget:
            ghost = Widget(height=40)
            self.ghosts.append(ghost)
            return ghost

        self.frame_patch = patch("sticky_notes.ui.todo_drag.tk.Frame", Widget)
        self.frame_patch.start()
        self.addCleanup(self.frame_patch.stop)
        self.controller = TodoDragController(
            self.host,
            self.canvas,
            self.content,
            rows=lambda: self.rows,
            todos=lambda: self.todos,
            theme=lambda: type("Theme", (), {"text": "#111"})(),
            ghost_factory=ghost_factory,
            on_reorder=lambda todo_id, index: self.reorders.append((todo_id, index)),
        )

    def test_motion_is_coalesced_into_a_sixteen_millisecond_frame(self) -> None:
        self.controller.press(Event(120), "a")
        self.assertFalse(self.controller.motion(Event(123)))
        self.assertTrue(self.controller.motion(Event(130)))
        self.assertTrue(self.controller.motion(Event(140)))
        self.assertEqual(self.host.delays, [FRAME_INTERVAL_MS])

        self.host.run_next()

        self.assertEqual(len(self.ghosts), 1)
        self.assertEqual(len(self.ghosts[0].placed), 1)

    def test_stationary_pointer_at_edge_keeps_scrolling(self) -> None:
        self.controller.press(Event(140), "a")
        self.controller.motion(Event(298))
        self.host.run_next()

        self.assertEqual(self.canvas.scrolls, [(1, "units")])
        self.assertEqual(self.host.delays, [FRAME_INTERVAL_MS, FRAME_INTERVAL_MS])
        self.assertEqual(len(self.host.jobs), 1)

        self.host.run_next()
        self.assertEqual(self.canvas.scrolls, [(1, "units"), (1, "units")])
        self.assertEqual(len(self.host.jobs), 1)

    def test_release_paints_final_position_reorders_and_cleans_up(self) -> None:
        self.controller.press(Event(120), "a")
        self.controller.motion(Event(130))

        self.assertTrue(self.controller.release(Event(190)))

        self.assertEqual(self.reorders, [("a", 2)])
        self.assertFalse(self.controller.active)
        self.assertEqual(self.host.jobs, {})
        self.assertTrue(self.ghosts[0].destroyed)

    def test_reset_reliably_cancels_without_reordering(self) -> None:
        self.controller.press(Event(120), "a")
        self.controller.motion(Event(140))
        self.controller.reset()

        self.assertFalse(self.controller.active)
        self.assertEqual(self.host.jobs, {})
        self.assertEqual(self.reorders, [])


if __name__ == "__main__":
    unittest.main()
