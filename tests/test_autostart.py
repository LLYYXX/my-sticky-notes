from __future__ import annotations

import unittest

from sticky_notes.platform.autostart import AutostartManager


class MemoryBackend:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def read(self, name: str) -> str | None:
        return self.values.get(name)

    def write(self, name: str, command: str) -> None:
        self.values[name] = command

    def delete(self, name: str) -> None:
        self.values.pop(name, None)


class AutostartTests(unittest.TestCase):
    def test_enable_disable_and_status_use_exact_command(self) -> None:
        backend = MemoryBackend()
        manager = AutostartManager(backend=backend, command='"app.exe" --autostart')

        self.assertFalse(manager.is_enabled())
        manager.set_enabled(True)
        self.assertTrue(manager.is_enabled())
        backend.values[manager.entry_name] = '"old.exe" --autostart'
        self.assertFalse(manager.is_enabled())
        manager.set_enabled(False)
        self.assertNotIn(manager.entry_name, backend.values)


if __name__ == "__main__":
    unittest.main()
