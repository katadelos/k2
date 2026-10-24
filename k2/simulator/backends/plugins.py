from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ...features.koreader.ports import Progress


@dataclass(frozen=True)
class PluginFixture:
    name: str
    title: str
    builtin: bool = False
    enabled: bool = True
    version: str = ""
    repository: str = ""

    def row(self, root: Path) -> dict:
        plugin_id = self.name + ".koplugin"
        return {
            "id": plugin_id,
            "name": self.title,
            "description": "Simulator plugin",
            "version": self.version,
            "path": str(root / "plugins" / plugin_id),
            "builtin": self.builtin,
            "managed": not self.builtin,
            "removable": not self.builtin,
            "canUpdate": not self.builtin,
            "protectionReason": "Bundled plugins are updated with KOReader."
            if self.builtin
            else "",
            "enabled": self.enabled,
            "stateEditable": True,
            "stateReason": "",
            "external": False,
            "globalExternalDisabled": False,
            "sourceVersion": self.version,
            "sourceRepository": self.repository,
            "ownershipKnown": not self.builtin,
            "ownershipCurrent": not self.builtin,
            "updateReason": "",
            "status": "Bundled with KOReader" if self.builtin else "Installed",
        }


_DEFAULT_PLUGINS = (
    PluginFixture("calibre", "Calibre", builtin=True),
    PluginFixture("kosync", "Progress sync", builtin=True),
    PluginFixture("example", "Example plugin"),
)


class SimulatedPluginManager:
    """In-memory plugins initialized through public, immutable fixtures."""

    def __init__(
        self, root: str | Path, fixtures: Sequence[PluginFixture] = _DEFAULT_PLUGINS
    ) -> None:
        self.root = Path(root)
        self._rows = [fixture.row(self.root) for fixture in fixtures]

    def list_installed(self) -> list[dict]:
        return [dict(row) for row in self._rows]

    def settings_status(self) -> dict:
        return {
            "editable": True,
            "reason": "",
            "disabled": [row["id"][:-9] for row in self._rows if not row["enabled"]],
            "externalDisabled": False,
            "extraPluginPaths": [],
        }

    def set_enabled(self, plugin_id: str, enabled: bool) -> dict:
        row = next((row for row in self._rows if row["id"] == plugin_id), None)
        if not row or type(enabled) is not bool:
            raise ValueError("Choose a plugin and a valid enabled state.")
        if not row["stateEditable"]:
            raise ValueError(row["stateReason"])
        row["enabled"] = enabled
        return {
            "message": "Plugin enabled. Restart KOReader to apply it."
            if enabled
            else "Plugin disabled. Restart KOReader to apply it.",
            "restartRequired": True,
        }

    def install(
        self,
        source: str,
        progress: Progress | None = None,
        expected_plugin: str | None = None,
        receipt: dict[str, str] | None = None,
    ) -> dict:
        if not str(source).strip():
            raise ValueError("Enter a plugin archive URL or local path.")
        name = (expected_plugin or "preview").removesuffix(".koplugin")
        row = PluginFixture(name, name.replace("_", " ").title()).row(self.root)
        receipt = receipt or {}
        row.update(
            version=receipt.get("version", ""),
            sourceVersion=receipt.get("version", ""),
            sourceRepository=receipt.get("repository", ""),
        )
        previous = next((item for item in self._rows if item["id"] == row["id"]), None)
        if previous:
            if previous["builtin"]:
                raise ValueError("Bundled plugins are managed by KOReader.")
            row["enabled"] = previous["enabled"]
        self._rows = [item for item in self._rows if item["id"] != row["id"]] + [row]
        if progress:
            progress("Plugin installed", 1.0)
        return {
            "plugins": [dict(row)],
            "message": "Plugin installed. Restart KOReader to load it.",
            "restartRequired": True,
        }

    def remove(self, plugin_id: str) -> dict:
        row = next((row for row in self._rows if row["id"] == plugin_id), None)
        if not row or not row["removable"]:
            raise ValueError("Bundled plugins are managed by KOReader.")
        self._rows.remove(row)
        return {
            "message": "Plugin removed. Restart KOReader to apply it.",
            "restartRequired": True,
        }
