from __future__ import annotations

import unittest

from sticky_notes.model import AppSettings, AppState, Note, Todo


class ModelTests(unittest.TestCase):
    def test_round_trip_preserves_note_and_todo_state(self) -> None:
        state = AppState(
            notes=[
                Note(
                    title="今天",
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

        self.assertEqual(restored.notes[0].title, "今天")
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
        self.assertEqual(note.title, "新便签")
        self.assertEqual(note.color, "yellow")
        self.assertGreaterEqual(note.width, 260)
        self.assertGreaterEqual(note.height, 210)
        self.assertEqual([todo.text for todo in note.todos], ["有效事项"])

    def test_empty_state_always_has_one_note(self) -> None:
        state = AppState.from_dict({"notes": []})
        self.assertEqual(len(state.notes), 1)

    def test_settings_round_trip_and_legacy_defaults(self) -> None:
        state = AppState(
            notes=[Note(title="设置")],
            settings=AppSettings(
                default_color="offwhite",
                new_notes_pinned=True,
                open_at_login=True,
            ),
        )

        restored = AppState.from_dict(state.to_dict())
        legacy = AppState.from_dict({"notes": [{"title": "旧数据"}]})

        self.assertEqual(restored.settings.default_color, "offwhite")
        self.assertTrue(restored.settings.new_notes_pinned)
        self.assertTrue(restored.settings.open_at_login)
        self.assertFalse(hasattr(restored.settings, "show_notes_on_autostart"))
        self.assertEqual(legacy.settings, AppSettings())


if __name__ == "__main__":
    unittest.main()
