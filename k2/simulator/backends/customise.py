import time
from collections.abc import Mapping
from pathlib import Path

from ...features.koreader.catalogue import ENTRIES
from ...features.koreader.customise import CustomiseManager
from .plugins import PluginFixture, SimulatedPluginManager


class SimulatedCustomiseManager(CustomiseManager):
    """The same catalogue and plans, with device-independent preview fixtures."""

    def __init__(self, root: str | Path, device_info: Mapping[str, object]) -> None:
        fixtures = [
            PluginFixture("coverbrowser", "Cover browser", builtin=True),
            PluginFixture("statistics", "Statistics", builtin=True),
        ]
        for item_id in ("bookshelf", "bookends"):
            entry = ENTRIES[item_id]
            fixtures.append(
                PluginFixture(
                    item_id,
                    entry.name,
                    enabled=item_id != "bookends",
                    version="5.2.0" if item_id == "bookshelf" else entry.version,
                    repository=entry.repository,
                )
            )
        info = dict(device_info, kernel="4.9.77", architecture="armv7l")
        super().__init__(root, info, backend=SimulatedPluginManager(root, fixtures))
        self._memory_cache: dict = {
            "schema": 1,
            "checkedAt": 0,
            "releases": {},
            "error": "",
        }

    def _cache(self):
        return self._memory_cache

    def apply(self, action: str, item_id: str) -> dict:
        if action == "install" and self.info.get("scenario") in {
            "offline",
            "koreader-offline",
        }:
            raise OSError("Could not download the plugin. Check Wi-Fi and try again.")
        return super().apply(action, item_id)

    def _save_cache(self, value):
        self._memory_cache = value

    def _refresh(self, cache):
        if self.info.get("scenario") in {"offline", "koreader-offline"}:
            cache["error"] = (
                "Release information could not be refreshed. Check your connection and try again."
            )
        else:
            cache.update(checkedAt=int(time.time()), error="")
        return cache

    def _reader_version(self):
        return "v2026.07"

    def _installation_problem(self):
        return ""

    def _patches(self):
        return set()
