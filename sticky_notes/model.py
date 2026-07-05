from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable
from uuid import uuid4

from .i18n import DEFAULT_LANGUAGE, normalize_language


STATE_VERSION = 5
NOTE_COLORS = {
    "yellow",
    "offwhite",
    "lime",
    "lilac",
    "cream",
    "pink",
    "mint",
    "coral",
    "navy",
}


def _new_id() -> str:
    return uuid4().hex


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(slots=True)
class AppSettings:
    default_color: str = "yellow"
    notes_pinned: bool = False
    open_at_login: bool = False
    language: str = DEFAULT_LANGUAGE

    def normalize(self) -> None:
        if self.default_color not in NOTE_COLORS:
            self.default_color = "yellow"
        self.language = normalize_language(self.language)

    def to_dict(self) -> dict[str, Any]:
        self.normalize()
        return {
            "default_color": self.default_color,
            "notes_pinned": self.notes_pinned,
            "open_at_login": self.open_at_login,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "AppSettings":
        if not isinstance(value, dict):
            return cls()
        settings = cls(
            default_color=str(value.get("default_color", "yellow")),
            notes_pinned=bool(
                value.get("notes_pinned", value.get("new_notes_pinned", False))
            ),
            open_at_login=bool(value.get("open_at_login", False)),
            language=str(value.get("language", DEFAULT_LANGUAGE)),
        )
        settings.normalize()
        return settings


@dataclass(slots=True)
class Todo:
    text: str
    completed: bool = False
    order: int = 0
    id: str = field(default_factory=_new_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "completed": self.completed,
            "order": self.order,
        }

    @classmethod
    def from_dict(cls, value: Any, fallback_order: int = 0) -> "Todo | None":
        if not isinstance(value, dict):
            return None
        text = str(value.get("text", "")).strip()
        if not text:
            return None
        return cls(
            id=str(value.get("id") or _new_id()),
            text=text,
            completed=bool(value.get("completed", False)),
            order=_as_int(value.get("order"), fallback_order),
        )


@dataclass(slots=True)
class Note:
    title: str = "新便签"
    color: str = "yellow"
    pinned: bool = False
    x: int = 120
    y: int = 120
    width: int = 320
    height: int = 360
    todos: list[Todo] = field(default_factory=list)
    id: str = field(default_factory=_new_id)

    def normalize(self) -> None:
        self.title = self.title.strip() or "新便签"
        if self.color not in NOTE_COLORS:
            self.color = "yellow"
        self.width = max(260, self.width)
        self.height = max(210, self.height)
        self.todos.sort(key=lambda item: item.order)
        for index, todo in enumerate(self.todos):
            todo.order = index

    def to_dict(self) -> dict[str, Any]:
        self.normalize()
        return {
            "id": self.id,
            "title": self.title,
            "color": self.color,
            "pinned": self.pinned,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "todos": [todo.to_dict() for todo in self.todos],
        }

    @classmethod
    def from_dict(cls, value: Any) -> "Note | None":
        if not isinstance(value, dict):
            return None
        raw_todos = value.get("todos", [])
        todos: list[Todo] = []
        if isinstance(raw_todos, Iterable) and not isinstance(raw_todos, (str, bytes, dict)):
            for index, raw_todo in enumerate(raw_todos):
                todo = Todo.from_dict(raw_todo, index)
                if todo is not None:
                    todos.append(todo)
        note = cls(
            id=str(value.get("id") or _new_id()),
            title=str(value.get("title", "新便签")),
            color=str(value.get("color", "yellow")),
            pinned=bool(value.get("pinned", False)),
            x=_as_int(value.get("x"), 120),
            y=_as_int(value.get("y"), 120),
            width=_as_int(value.get("width"), 320),
            height=_as_int(value.get("height"), 360),
            todos=todos,
        )
        note.normalize()
        return note


@dataclass(slots=True)
class AppState:
    notes: list[Note] = field(default_factory=list)
    settings: AppSettings = field(default_factory=AppSettings)
    version: int = STATE_VERSION

    @classmethod
    def default(cls) -> "AppState":
        return cls(notes=[Note(title="今天")])

    def ensure_note(self) -> Note:
        if not self.notes:
            self.notes.append(Note(title="今天"))
        return self.notes[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": STATE_VERSION,
            "notes": [note.to_dict() for note in self.notes],
            "settings": self.settings.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Any) -> "AppState":
        if not isinstance(value, dict):
            return cls.default()
        raw_notes = value.get("notes", [])
        notes: list[Note] = []
        if isinstance(raw_notes, list):
            for raw_note in raw_notes:
                note = Note.from_dict(raw_note)
                if note is not None:
                    notes.append(note)
        state = cls(
            notes=notes,
            settings=AppSettings.from_dict(value.get("settings")),
            version=STATE_VERSION,
        )
        state.ensure_note()
        return state
