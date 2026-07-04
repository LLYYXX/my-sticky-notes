from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from .model import AppState


APP_DIRECTORY = "MyStickyNotes"


def default_data_directory() -> Path:
    override = os.environ.get("MY_STICKY_NOTES_DATA_DIR")
    if override:
        return Path(override).expanduser()
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_DIRECTORY
    return Path.home() / ".my_sticky_notes"


class StateStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_data_directory() / "state.json"
        self.backup_path = self.path.with_suffix(".json.bak")

    def load(self) -> AppState:
        if not self.path.exists():
            return AppState.default()
        try:
            return self._read(self.path)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
            self._preserve_corrupt_file()
            if self.backup_path.exists():
                try:
                    return self._read(self.backup_path)
                except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
                    pass
            return AppState.default()

    def save(self, state: AppState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".json.tmp")
        payload = json.dumps(
            state.to_dict(), ensure_ascii=False, indent=2, sort_keys=True
        )
        with temp_path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if self.path.exists():
            shutil.copy2(self.path, self.backup_path)
        os.replace(temp_path, self.path)

    @staticmethod
    def _read(path: Path) -> AppState:
        with path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
        return AppState.from_dict(data)

    def _preserve_corrupt_file(self) -> None:
        if not self.path.exists():
            return
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        destination = self.path.with_name(f"state.corrupt-{timestamp}.json")
        try:
            os.replace(self.path, destination)
        except OSError:
            pass
