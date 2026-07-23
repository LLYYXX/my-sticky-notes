from __future__ import annotations

import unittest

from sticky_notes.ui.input_session import InputCommit, InputMode, TodoInputSession


class TodoInputSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = TodoInputSession()

    def assert_idle(self) -> None:
        self.assertEqual(self.session.mode, InputMode.IDLE)
        self.assertIsNone(self.session.target_id)
        self.assertEqual(self.session.draft, "")
        self.assertFalse(self.session.is_active)

    def test_starts_idle(self) -> None:
        self.assert_idle()

    def test_create_tracks_and_commits_trimmed_draft(self) -> None:
        self.session.begin_create()
        self.assertEqual(self.session.mode, InputMode.CREATING)
        self.assertTrue(self.session.is_active)
        self.session.update_draft("  buy milk  ")

        result = self.session.commit()

        self.assertEqual(
            result,
            InputCommit(mode=InputMode.CREATING, text="buy milk"),
        )
        self.assert_idle()

    def test_create_can_start_with_initial_draft(self) -> None:
        self.session.begin_create("draft")

        self.assertEqual(self.session.draft, "draft")

    def test_edit_tracks_target_and_commits_trimmed_draft(self) -> None:
        self.session.begin_edit("todo-1", "old")
        self.assertEqual(self.session.mode, InputMode.EDITING)
        self.assertEqual(self.session.target_id, "todo-1")
        self.session.update_draft("  revised  ")

        result = self.session.commit()

        self.assertEqual(
            result,
            InputCommit(
                mode=InputMode.EDITING,
                target_id="todo-1",
                text="revised",
            ),
        )
        self.assert_idle()

    def test_blank_create_commit_returns_none_and_resets(self) -> None:
        self.session.begin_create(" \t ")

        self.assertIsNone(self.session.commit())
        self.assert_idle()

    def test_blank_edit_commit_returns_none_and_resets(self) -> None:
        self.session.begin_edit("todo-1", "\n ")

        self.assertIsNone(self.session.commit())
        self.assert_idle()

    def test_idle_commit_is_an_idempotent_noop(self) -> None:
        self.assertIsNone(self.session.commit())
        self.assertIsNone(self.session.commit())
        self.assert_idle()

    def test_cancel_discards_create_and_reports_transition(self) -> None:
        self.session.begin_create("unsaved")

        self.assertTrue(self.session.cancel())
        self.assert_idle()
        self.assertFalse(self.session.cancel())

    def test_cancel_discards_edit_and_target(self) -> None:
        self.session.begin_edit("todo-1", "unsaved")

        self.assertTrue(self.session.cancel())
        self.assert_idle()

    def test_repeating_same_create_is_idempotent_and_preserves_draft(self) -> None:
        self.session.begin_create("first")
        self.session.update_draft("typed")

        self.session.begin_create("replacement")

        self.assertEqual(self.session.mode, InputMode.CREATING)
        self.assertEqual(self.session.draft, "typed")

    def test_repeating_same_edit_is_idempotent_and_preserves_draft(self) -> None:
        self.session.begin_edit("todo-1", "first")
        self.session.update_draft("typed")

        self.session.begin_edit("todo-1", "replacement")

        self.assertEqual(self.session.target_id, "todo-1")
        self.assertEqual(self.session.draft, "typed")

    def test_cannot_switch_from_create_to_edit_without_resolution(self) -> None:
        self.session.begin_create("unsaved")

        with self.assertRaisesRegex(RuntimeError, "commit or cancel"):
            self.session.begin_edit("todo-1", "text")

        self.assertEqual(self.session.mode, InputMode.CREATING)
        self.assertEqual(self.session.draft, "unsaved")

    def test_cannot_switch_from_edit_to_create_without_resolution(self) -> None:
        self.session.begin_edit("todo-1", "unsaved")

        with self.assertRaisesRegex(RuntimeError, "commit or cancel"):
            self.session.begin_create()

        self.assertEqual(self.session.mode, InputMode.EDITING)
        self.assertEqual(self.session.target_id, "todo-1")

    def test_cannot_switch_edit_target_without_resolution(self) -> None:
        self.session.begin_edit("todo-1", "unsaved")

        with self.assertRaisesRegex(RuntimeError, "commit or cancel"):
            self.session.begin_edit("todo-2", "other")

        self.assertEqual(self.session.target_id, "todo-1")
        self.assertEqual(self.session.draft, "unsaved")

    def test_update_draft_requires_an_active_session(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "session is idle"):
            self.session.update_draft("orphan")

        self.assert_idle()

    def test_edit_requires_a_non_empty_target(self) -> None:
        for target_id in ("", None):
            with self.subTest(target_id=target_id):
                with self.assertRaisesRegex(ValueError, "target_id"):
                    self.session.begin_edit(target_id, "text")  # type: ignore[arg-type]
                self.assert_idle()


class InputCommitTests(unittest.TestCase):
    def test_rejects_invalid_command_shapes(self) -> None:
        invalid = (
            dict(mode=InputMode.IDLE, text="text"),
            dict(mode=InputMode.CREATING, target_id="todo-1", text="text"),
            dict(mode=InputMode.EDITING, text="text"),
            dict(mode=InputMode.CREATING, text=""),
        )

        for kwargs in invalid:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    InputCommit(**kwargs)


if __name__ == "__main__":
    unittest.main()
