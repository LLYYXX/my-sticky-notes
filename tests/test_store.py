from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sticky_notes.model import AppState, Note, Todo
from sticky_notes.store import StateStore, default_data_directory


class StateStoreTests(unittest.TestCase):
    def test_installed_build_uses_local_app_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict(
                os.environ, {"LOCALAPPDATA": str(root / "local")}, clear=True
            ):
                self.assertEqual(
                    default_data_directory(), root / "local" / "MyStickyNotes"
                )

    def test_data_directory_override_takes_priority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(
                os.environ,
                {"MY_STICKY_NOTES_DATA_DIR": directory},
                clear=True,
            ):
                self.assertEqual(default_data_directory(), Path(directory))

    def test_save_and_load_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            store = StateStore(path)
            state = AppState(notes=[Note(todos=[Todo("买牛奶")])])

            store.save(state)
            restored = store.load()

            self.assertEqual(restored.notes[0].todos[0].text, "买牛奶")
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_second_save_creates_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            store = StateStore(path)
            store.save(AppState(notes=[Note(color="yellow")]))
            store.save(AppState(notes=[Note(color="navy")]))

            with store.backup_path.open("r", encoding="utf-8") as stream:
                backup = json.load(stream)

            self.assertEqual(backup["notes"][0]["color"], "yellow")
            self.assertNotIn("title", backup["notes"][0])

    def test_corrupt_primary_recovers_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            store = StateStore(path)
            store.save(AppState(notes=[Note(color="mint")]))
            store.backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            path.write_text("{broken", encoding="utf-8")

            restored = store.load()

            self.assertEqual(restored.notes[0].color, "mint")
            self.assertTrue(list(Path(directory).glob("state.corrupt-*.json")))


if __name__ == "__main__":
    unittest.main()
