from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from typing import Protocol

from ..model import Todo
from ..theme import NoteTheme


FRAME_INTERVAL_MS = 16
DRAG_THRESHOLD_PX = 5
EDGE_SCROLL_ZONE_PX = 24


class PointerEvent(Protocol):
    y_root: int


GhostFactory = Callable[[tk.Misc, Todo, NoteTheme], tk.Widget]
RowsProvider = Callable[[], Sequence[tuple[str, tk.Widget]]]
TodosProvider = Callable[[], Sequence[Todo]]
ThemeProvider = Callable[[], NoteTheme | None]


class TodoDragController:
    """Own the complete lifecycle and presentation of todo reordering.

    ``TodoList`` supplies live providers instead of mutable snapshots because a
    render can replace every row.  The controller owns no application data; its
    only domain-side effect is ``on_reorder`` after a completed drag.
    """

    def __init__(
        self,
        host: tk.Widget,
        canvas: tk.Canvas,
        content: tk.Widget,
        *,
        rows: RowsProvider,
        todos: TodosProvider,
        theme: ThemeProvider,
        ghost_factory: GhostFactory,
        on_reorder: Callable[[str, int], None],
        frame_interval_ms: int = FRAME_INTERVAL_MS,
    ) -> None:
        self._host = host
        self._canvas = canvas
        self._content = content
        self._rows = rows
        self._todos = todos
        self._theme = theme
        self._ghost_factory = ghost_factory
        self._on_reorder = on_reorder
        self._frame_interval_ms = frame_interval_ms

        self._todo_id: str | None = None
        self._start_y = 0
        self._pointer_y = 0
        self._offset_y = 0
        self._target_index: int | None = None
        self._active = False
        self._dirty = False
        self._frame_job: str | None = None
        self._ghost: tk.Widget | None = None
        self._indicator: tk.Frame | None = None

    @property
    def active(self) -> bool:
        return self._active

    def press(self, event: PointerEvent, todo_id: str) -> None:
        """Start tracking a possible drag without displaying anything yet."""
        self.reset()
        self._todo_id = todo_id
        self._start_y = event.y_root
        self._pointer_y = event.y_root

    def motion(self, event: PointerEvent) -> bool:
        """Record pointer motion and return whether the gesture is a drag."""
        if self._todo_id is None:
            return False
        self._pointer_y = event.y_root
        if not self._active:
            if abs(self._pointer_y - self._start_y) < DRAG_THRESHOLD_PX:
                return False
            self._activate()
        self._dirty = True
        self._schedule_frame()
        return True

    def release(self, event: PointerEvent | None = None) -> bool:
        """Finish the gesture, painting its final pointer position first."""
        if event is not None:
            self._pointer_y = event.y_root
            self._dirty = True
        was_active = self._active
        todo_id = self._todo_id
        if was_active:
            self._cancel_frame()
            self._paint_frame()
        target_index = self._target_index
        self.reset()
        if was_active and todo_id is not None and target_index is not None:
            self._on_reorder(todo_id, target_index)
            return True
        return False

    def reset(self) -> None:
        """Cancel scheduling and remove all transient drag presentation."""
        self._cancel_frame()
        self._destroy_ghost()
        self._destroy_indicator()
        self._todo_id = None
        self._target_index = None
        self._active = False
        self._dirty = False
        self._offset_y = 0

    def _activate(self) -> None:
        self._active = True
        row = self._row_for(self._todo_id)
        if row is not None:
            self._offset_y = max(
                0,
                min(self._pointer_y - row.winfo_rooty(), row.winfo_height()),
            )

    def _schedule_frame(self) -> None:
        if self._frame_job is None and self._active:
            self._frame_job = self._host.after(
                self._frame_interval_ms, self._on_frame
            )

    def _cancel_frame(self) -> None:
        if self._frame_job is not None:
            try:
                self._host.after_cancel(self._frame_job)
            except tk.TclError:
                pass
            self._frame_job = None

    def _on_frame(self) -> None:
        self._frame_job = None
        if not self._active:
            return
        self._paint_frame()
        # A stationary pointer in an edge zone must keep scrolling.  Away from
        # an edge, a new raw motion event is what schedules the next frame.
        if self._edge_scroll_direction() != 0:
            self._dirty = True
            self._schedule_frame()

    def _paint_frame(self) -> None:
        if not self._active or self._todo_id is None:
            return
        if not self._dirty and self._edge_scroll_direction() == 0:
            return
        self._ensure_ghost()
        self._scroll_at_edge()
        self._target_index = self._drop_index(self._pointer_y)
        self._show_indicator(self._target_index)
        self._position_ghost(self._pointer_y)
        self._dirty = False

    def _ensure_ghost(self) -> None:
        if self._ghost_exists():
            return
        theme = self._theme()
        todo = self._todo_for(self._todo_id)
        if theme is None or todo is None:
            return
        self._ghost = self._ghost_factory(self._host, todo, theme)

    def _position_ghost(self, pointer_y: int) -> None:
        if not self._ghost_exists():
            return
        ghost = self._ghost
        assert ghost is not None
        height = max(1, ghost.winfo_reqheight())
        y = pointer_y - self._host.winfo_rooty() - self._offset_y
        y = max(0, min(y, max(0, self._host.winfo_height() - height)))
        ghost.place(
            x=12,
            y=y,
            width=max(80, self._host.winfo_width() - 24),
            height=height,
        )
        ghost.lift()

    def _drop_index(self, pointer_y: int) -> int:
        rows = self._rows()
        for index, (_todo_id, row) in enumerate(rows):
            center = row.winfo_rooty() + row.winfo_height() // 2
            if pointer_y < center:
                return index
        return len(rows)

    def _show_indicator(self, target_index: int) -> None:
        theme = self._theme()
        if theme is None:
            return
        if not self._indicator_exists():
            self._indicator = tk.Frame(
                self._content,
                bg=theme.text,
                height=2,
                borderwidth=0,
                highlightthickness=0,
            )
        rows = self._rows()
        if target_index < len(rows):
            y = rows[target_index][1].winfo_y()
        elif rows:
            last_row = rows[-1][1]
            y = last_row.winfo_y() + last_row.winfo_height()
        else:
            y = 0
        assert self._indicator is not None
        self._indicator.place(
            x=4, y=max(0, y - 1), relwidth=1, width=-8, height=2
        )
        self._indicator.lift()

    def _edge_scroll_direction(self) -> int:
        top = self._canvas.winfo_rooty()
        bottom = top + self._canvas.winfo_height()
        if self._pointer_y < top + EDGE_SCROLL_ZONE_PX:
            return -1
        if self._pointer_y > bottom - EDGE_SCROLL_ZONE_PX:
            return 1
        return 0

    def _scroll_at_edge(self) -> None:
        direction = self._edge_scroll_direction()
        if direction:
            self._canvas.yview_scroll(direction, "units")

    def _row_for(self, todo_id: str | None) -> tk.Widget | None:
        return next(
            (row for current_id, row in self._rows() if current_id == todo_id),
            None,
        )

    def _todo_for(self, todo_id: str | None) -> Todo | None:
        return next(
            (todo for todo in self._todos() if todo.id == todo_id),
            None,
        )

    def _ghost_exists(self) -> bool:
        return self._ghost is not None and bool(self._ghost.winfo_exists())

    def _indicator_exists(self) -> bool:
        return self._indicator is not None and bool(self._indicator.winfo_exists())

    def _destroy_ghost(self) -> None:
        if self._ghost_exists():
            assert self._ghost is not None
            self._ghost.destroy()
        self._ghost = None

    def _destroy_indicator(self) -> None:
        if self._indicator_exists():
            assert self._indicator is not None
            self._indicator.destroy()
        self._indicator = None
