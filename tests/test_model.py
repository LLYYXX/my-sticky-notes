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
                    collapsed=True,
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
        self.assertTrue(restored.notes[0].collapsed)
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
                open_at_login=True,
                language="en",
            ),
        )

        restored = AppState.from_dict(state.to_dict())
        legacy = AppState.from_dict({"notes": [{"title": "旧数据"}]})

        self.assertTrue(restored.settings.open_at_login)
        self.assertEqual(restored.settings.language, "en")
        self.assertFalse(hasattr(restored.settings, "default_color"))
        self.assertFalse(hasattr(restored.settings, "notes_pinned"))
        self.assertFalse(hasattr(restored.settings, "show_notes_on_autostart"))
        self.assertEqual(legacy.settings, AppSettings())

    def test_legacy_global_note_style_settings_are_ignored(self) -> None:
        restored = AppState.from_dict(
            {
                "notes": [{"title": "旧数据"}],
                "settings": {
                    "default_color": "pink",
                    "notes_pinned": True,
                    "new_notes_pinned": True,
                },
            }
        )

        self.assertEqual(restored.notes[0].color, "yellow")
        self.assertFalse(restored.notes[0].pinned)

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

    def test_reorder_todo_moves_to_insertion_slot_and_updates_order(self) -> None:
        first = Todo(text="first")
        second = Todo(text="second")
        third = Todo(text="third")
        note = Note(todos=[first, second, third])

        changed = note.reorder_todo(first.id, 3)

        self.assertTrue(changed)
        self.assertEqual([todo.text for todo in note.todos], ["second", "third", "first"])
        self.assertEqual([todo.order for todo in note.todos], [0, 1, 2])

        restored = Note.from_dict(note.to_dict())
        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(
            [todo.text for todo in restored.todos],
            ["second", "third", "first"],
        )

    def test_reorder_todo_ignores_missing_or_unchanged_move(self) -> None:
        first = Todo(text="first")
        second = Todo(text="second")
        note = Note(todos=[first, second])

        self.assertFalse(note.reorder_todo("missing", 1))
        self.assertFalse(note.reorder_todo(first.id, 1))
        self.assertEqual([todo.text for todo in note.todos], ["first", "second"])

    def test_reorder_todo_handles_reverse_middle_and_bounded_slots(self) -> None:
        todos = [Todo(text=str(index), order=index) for index in range(4)]
        note = Note(todos=todos)
        zero_id = todos[0].id
        one_id = todos[1].id
        three_id = todos[3].id

        self.assertTrue(note.reorder_todo(three_id, -20))
        self.assertEqual([todo.text for todo in note.todos], ["3", "0", "1", "2"])

        self.assertTrue(note.reorder_todo(zero_id, 3))
        self.assertEqual([todo.text for todo in note.todos], ["3", "1", "0", "2"])

        self.assertTrue(note.reorder_todo(one_id, 99))
        self.assertEqual([todo.text for todo in note.todos], ["3", "0", "2", "1"])
        self.assertEqual([todo.order for todo in note.todos], [0, 1, 2, 3])

    def test_unchanged_reorder_repairs_non_contiguous_order_values(self) -> None:
        first = Todo(text="first", order=10)
        second = Todo(text="second", order=20)
        note = Note(todos=[first, second])

        self.assertFalse(note.reorder_todo(first.id, 1))

        self.assertEqual([todo.order for todo in note.todos], [0, 1])


if __name__ == "__main__":
    unittest.main()
