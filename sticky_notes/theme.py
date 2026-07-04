from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NoteTheme:
    key: str
    label: str
    background: str
    header: str
    input_background: str
    hover: str
    pressed: str
    text: str
    muted: str
    completed: str
    border: str
    menu: str
    checkbox: str


THEMES = {
    "yellow": NoteTheme(
        key="yellow",
        label="淡黄",
        background="#FFF1A8",
        header="#FFF0A0",
        input_background="#FFF5BE",
        hover="#F8E58F",
        pressed="#EED878",
        text="#2C2B24",
        muted="#8E865F",
        completed="#A79E78",
        border="#E2CF72",
        menu="#FFF9D8",
        checkbox="#6F684C",
    ),
    "offwhite": NoteTheme(
        key="offwhite",
        label="黯白",
        background="#F0F0EC",
        header="#F2F2EE",
        input_background="#F7F7F4",
        hover="#E5E5DF",
        pressed="#DADAD3",
        text="#2A2A28",
        muted="#85857F",
        completed="#A4A49D",
        border="#CFCFC8",
        menu="#FAFAF7",
        checkbox="#676762",
    ),
}

FONT_FAMILY = "Microsoft YaHei UI"


def get_theme(key: str) -> NoteTheme:
    return THEMES.get(key, THEMES["yellow"])
