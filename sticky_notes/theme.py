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
    icon_tone: str = "dark"


THEMES = {
    "yellow": NoteTheme(
        key="yellow",
        label="淡黄",
        background="#FFF1A8",
        header="#FFF0A0",
        input_background="#FFF5BE",
        hover="#F8E58F",
        pressed="#EED878",
        text="#000000",
        muted="#000000",
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
        text="#000000",
        muted="#000000",
        completed="#A4A49D",
        border="#CFCFC8",
        menu="#FAFAF7",
        checkbox="#676762",
    ),
    "lime": NoteTheme(
        key="lime",
        label="青柠",
        background="#DCEEB1",
        header="#D7E9AA",
        input_background="#E8F4CC",
        hover="#CFE39F",
        pressed="#BCD47F",
        text="#000000",
        muted="#000000",
        completed="#788260",
        border="#B8CE83",
        menu="#F0F7DF",
        checkbox="#3F4931",
    ),
    "lilac": NoteTheme(
        key="lilac",
        label="丁香",
        background="#C5B0F4",
        header="#BEA8EE",
        input_background="#D7C9F8",
        hover="#B59CEB",
        pressed="#9E82DD",
        text="#000000",
        muted="#000000",
        completed="#76678E",
        border="#A68BE0",
        menu="#E9E1FC",
        checkbox="#493C62",
    ),
    "cream": NoteTheme(
        key="cream",
        label="奶油",
        background="#F4ECD6",
        header="#F0E6CC",
        input_background="#FAF5E8",
        hover="#E9DDBE",
        pressed="#DCCDA7",
        text="#000000",
        muted="#000000",
        completed="#918771",
        border="#D9CAA5",
        menu="#FFFBEF",
        checkbox="#554C39",
    ),
    "pink": NoteTheme(
        key="pink",
        label="淡粉",
        background="#EFD4D4",
        header="#EBCACA",
        input_background="#F7E4E4",
        hover="#E4BDBD",
        pressed="#D9A9A9",
        text="#000000",
        muted="#000000",
        completed="#937373",
        border="#D7ADAD",
        menu="#FBEDED",
        checkbox="#594040",
    ),
    "mint": NoteTheme(
        key="mint",
        label="薄荷",
        background="#C8E6CD",
        header="#C1DFC6",
        input_background="#DCF0DF",
        hover="#B4D9BA",
        pressed="#9CC8A4",
        text="#000000",
        muted="#000000",
        completed="#69806D",
        border="#9FCBA7",
        menu="#EAF6EC",
        checkbox="#38503D",
    ),
    "coral": NoteTheme(
        key="coral",
        label="珊瑚",
        background="#F3C9B6",
        header="#EFC1AD",
        input_background="#F9DDD0",
        hover="#E8B49D",
        pressed="#D99E84",
        text="#000000",
        muted="#000000",
        completed="#916F60",
        border="#DCA68D",
        menu="#FCE9E0",
        checkbox="#584034",
    ),
    "navy": NoteTheme(
        key="navy",
        label="深蓝",
        background="#1F1D3D",
        header="#29264B",
        input_background="#302D53",
        hover="#3A3760",
        pressed="#4B4774",
        text="#FFFFFF",
        muted="#FFFFFF",
        completed="#918DAA",
        border="#4A466D",
        menu="#2A274A",
        checkbox="#FFFFFF",
        icon_tone="light",
    ),
}

FONT_FAMILY = "Microsoft YaHei UI"


def get_theme(key: str) -> NoteTheme:
    return THEMES.get(key, THEMES["yellow"])
