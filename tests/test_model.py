from __future__ import annotations

import unittest

from sticky_notes.model import AppSettings, AppState, Note, Todo


class ModelTests(unittest.TestCase):
    def test_round_trip_preserves_note_and_todo_state(self) -> None:
        state = AppState(
            notes=[
                Note(
                    color="offwhite",
                    pinned=True,
                    x=11,
                    y=22,
                    width=333,
                    height=444,
                    todos=[Todo(text="完成项目草稿", completed=True)],
                )
            ]
        )

        restored = AppState.from_dict(state.to_dict())

        self.assertEqual(restored.notes[0].color, "offwhite")
        self.assertTrue(restored.notes[0].pinned)
        self.assertEqual(restored.notes[0].width, 333)
        self.assertTrue(restored.notes[0].todos[0].completed)

    def test_invalid_values_are_normalized(self) -> None:
        restored = AppState.from_dict(
            {
                "notes": [
                    {
                        "title": "  ",
                        "color": "blue",
                        "width": 10,
                        "height": 20,
                        "todos": [{"text": ""}, {"text": "有效事项"}],
                    }
                ]
            }
        )

        note = restored.notes[0]
        self.assertEqual(note.color, "yellow")
        self.assertGreaterEqual(note.width, 260)
        self.assertGreaterEqual(note.height, 210)
        self.assertEqual([todo.text for todo in note.todos], ["有效事项"])

    def test_empty_state_always_has_one_note(self) -> None:
        state = AppState.from_dict({"notes": []})
        self.assertEqual(len(state.notes), 1)

    def test_settings_round_trip_and_legacy_defaults(self) -> None:
        state = AppState(
            notes=[Note()],
            settings=AppSettings(
                open_at_login=True,
                language="en",
            ),
        )

        restored = AppState.from_dict(state.to_dict())
        legacy = AppState.from_dict({"notes": [{"title": "旧数据"}]})

        self.assertTrue(restored.settings.open_at_login)
        self.assertEqual(restored.settings.language, "en")
        self.assertFalse(hasattr(restored.settings, "show_notes_on_autostart"))
        self.assertEqual(legacy.settings, AppSettings())

    def test_removed_title_and_global_note_settings_are_not_read_or_written(self) -> None:
        restored = AppState.from_dict(
            {
                "notes": [{"title": "旧数据", "color": "mint", "pinned": True}],
                "settings": {
                    "default_color": "pink",
                    "notes_pinned": True,
                    "new_notes_pinned": True,
                },
            }
        )

        payload = restored.to_dict()

        self.assertFalse(hasattr(restored.notes[0], "title"))
        self.assertFalse(hasattr(restored.settings, "default_color"))
        self.assertFalse(hasattr(restored.settings, "notes_pinned"))
        self.assertNotIn("title", payload["notes"][0])
        self.assertNotIn("default_color", payload["settings"])
        self.assertNotIn("notes_pinned", payload["settings"])
        self.assertEqual(restored.notes[0].color, "mint")
        self.assertTrue(restored.notes[0].pinned)

    def test_invalid_language_falls_back_to_chinese(self) -> None:
        settings = AppSettings.from_dict({"language": "fr"})

        self.assertEqual(settings.language, "zh-CN")

    def test_all_editorial_palette_colors_round_trip(self) -> None:
        colors = (
            "yellow",
            "offwhite",
            "lime",
            "lilac",
            "cream",
            "pink",
            "mint",
            "coral",
            "navy",
        )

        for color in colors:
            with self.subTest(color=color):
                restored = AppState.from_dict(
                    AppState(
                        notes=[Note(color=color)],
                    ).to_dict()
                )
                self.assertEqual(restored.notes[0].color, color)


if __name__ == "__main__":
    unittest.main()
