from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class InputMode(Enum):
    """The mutually exclusive modes of a todo input session."""

    IDLE = auto()
    CREATING = auto()
    EDITING = auto()


@dataclass(frozen=True, slots=True)
class InputCommit:
    """A UI-independent command produced by committing the active session."""

    mode: InputMode
    text: str
    target_id: str | None = None

    def __post_init__(self) -> None:
        if self.mode is InputMode.IDLE:
            raise ValueError("an input commit cannot use IDLE mode")
        if not self.text:
            raise ValueError("an input commit requires non-empty text")
        if self.mode is InputMode.CREATING and self.target_id is not None:
            raise ValueError("a create commit cannot have a target_id")
        if self.mode is InputMode.EDITING and not self.target_id:
            raise ValueError("an edit commit requires a target_id")


class TodoInputSession:
    """Owns the complete state machine for one todo input interaction.

    Starting the already-active session is idempotent and preserves its draft.
    Starting a different session while one is active is rejected so callers
    cannot silently discard user input; they must commit or cancel first.
    """

    __slots__ = ("_draft", "_mode", "_target_id")

    def __init__(self) -> None:
        self._mode = InputMode.IDLE
        self._target_id: str | None = None
        self._draft = ""

    @property
    def mode(self) -> InputMode:
        return self._mode

    @property
    def target_id(self) -> str | None:
        return self._target_id

    @property
    def draft(self) -> str:
        return self._draft

    @property
    def is_active(self) -> bool:
        return self._mode is not InputMode.IDLE

    def begin_create(self, draft: str = "") -> None:
        if self._mode is InputMode.CREATING:
            return
        self._require_idle("begin creating")
        self._mode = InputMode.CREATING
        self._draft = draft

    def begin_edit(self, target_id: str, draft: str) -> None:
        if not target_id:
            raise ValueError("target_id must be non-empty")
        if self._mode is InputMode.EDITING and self._target_id == target_id:
            return
        self._require_idle(f"begin editing {target_id!r}")
        self._mode = InputMode.EDITING
        self._target_id = target_id
        self._draft = draft

    def update_draft(self, draft: str) -> None:
        if self._mode is InputMode.IDLE:
            raise RuntimeError("cannot update a draft while the session is idle")
        self._draft = draft

    def commit(self) -> InputCommit | None:
        if self._mode is InputMode.IDLE:
            return None

        mode = self._mode
        target_id = self._target_id
        text = self._draft.strip()
        self._reset()
        if not text:
            return None
        return InputCommit(mode=mode, target_id=target_id, text=text)

    def cancel(self) -> bool:
        if self._mode is InputMode.IDLE:
            return False
        self._reset()
        return True

    def _require_idle(self, action: str) -> None:
        if self._mode is not InputMode.IDLE:
            raise RuntimeError(
                f"cannot {action} while {self._mode.name.lower()} is active; "
                "commit or cancel it first"
            )

    def _reset(self) -> None:
        self._mode = InputMode.IDLE
        self._target_id = None
        self._draft = ""
