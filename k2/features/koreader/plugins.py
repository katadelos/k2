"""Install KOReader's native plugin folders without involving opkg or Lua."""

import json
import os
import re
import shutil
import stat
import tempfile
import time
from pathlib import Path, PurePosixPath

from .archive import PLUGIN_NAME, PluginArchive, archive_source
from .lua_settings import SettingsSyntaxError, plugin_flags, set_plugin_flag
from .ownership import modified_owned_code, owned_files, preserve_local_files, tree_size
from .ports import Progress
from .transactions import PluginTransaction, sync_directory

MAX_METADATA = 128 * 1024


def _read_text(path, limit=MAX_METADATA):
    try:
        if path.is_symlink() or path.stat().st_size > limit:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _read_json(path):
    try:
        data = json.loads(_read_text(path, 2 * 1024 * 1024))
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


def _save_json(path, data):
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=".k2-plugins-state-",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(data, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            temporary.replace(path)
            sync_directory(path.parent)
        finally:
            temporary.unlink(missing_ok=True)


def _save_settings(path, text):
    if path.is_symlink():
        raise SettingsSyntaxError(
            "The settings file is linked elsewhere. Change plugin states in KOReader."
        )
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=path.parent, prefix=".k2-reader-settings-", delete=False
    ) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(text.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            temporary.chmod(mode)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def _plugin_version(path, metadata):
    version = _lua_string(metadata, "version")
    if version:
        return version
    for filename in ("VERSION", "version.lua", path.name[:-9] + "_version.lua"):
        text = _read_text(path / filename, 8192).strip()
        if filename == "VERSION" and re.fullmatch(r"v?\d[\w.+-]*", text):
            return text
        if filename.endswith(".lua"):
            version = _lua_string(text, "version")
            if version:
                return version
            match = re.fullmatch(r"return\s+([\"'])(v?\d[\w.+-]*)\1\s*;?", text)
            if match:
                return match.group(2)
    return ""


def _lua_string(text, name):
    """Read a literal metadata value; plugin Lua is never evaluated by k2."""
    pattern = (
        r"\b" + re.escape(name) + r"\s*=\s*(?:_\s*\(\s*)?([\"'])((?:\\.|(?!\1).)*)\1"
    )
    match = re.search(pattern, text)
    if match:
        value = re.sub(r"\\([\\\"'])", r"\1", match.group(2))
        value = value.replace(r"\n", " ").replace(r"\t", " ")
    else:
        match = re.search(
            r"\b" + re.escape(name) + r"\s*=\s*(?:_\s*\(\s*)?\[\[(.*?)\]\]", text, re.S
        )
        value = match.group(1) if match else ""
    return " ".join(value.split())[:1024]


class PluginManager:
    """Worker-thread API for KOReader's plugins/ directory, with staged replacement."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.plugins = self.root / "plugins"
        self.state_path = self.root / ".k2-plugins.json"

    def _state(self) -> dict:
        state = _read_json(self.state_path)
        plugins = state.get("plugins", {})
        return plugins if state.get("schema") == 1 and isinstance(plugins, dict) else {}

    def _builtins(self) -> tuple[set[str], bool]:
        text = _read_text(self.root / "frontend/pluginloader.lua", 512 * 1024)
        table = re.search(r"\blocal\s+BUILTIN_PLUGINS\s*=\s*\{(.*?)\}", text, re.S)
        if table:
            names = re.findall(
                r"\[\s*[\"']([^\"']+)[\"']\s*\]\s*=\s*true", table.group(1)
            )
            if names:
                return {name + ".koplugin" for name in names}, True
        manifest = _read_json(self.root / ".k2-install.json")
        version = _read_text(self.root / "git-rev").strip()
        names = manifest.get("builtinPlugins")
        if (
            version
            and manifest.get("gitRev", manifest.get("version")) == version
            and isinstance(names, list)
            and names
            and all(
                isinstance(name, str) and PLUGIN_NAME.fullmatch(name) for name in names
            )
        ):
            return set(names), True
        return set(), False

    def _settings_text(self):
        path = self.root / "settings.reader.lua"
        if path.is_symlink():
            raise SettingsSyntaxError(
                "The settings file is linked elsewhere. Change plugin states in KOReader."
            )
        if not path.exists():
            return "return {\n}\n"
        if path.stat().st_size > 4 * 1024 * 1024:
            raise SettingsSyntaxError("The settings file is too large to edit safely.")
        return path.read_bytes().decode("utf-8")

    def settings_status(self) -> dict:
        from .manager import is_running

        try:
            flags = plugin_flags(self._settings_text())
            paths = []
            for value in flags["extraPluginPaths"]:
                if not value or "\0" in value:
                    raise SettingsSyntaxError("An extra-plugin path is invalid.")
                path = Path(value)
                paths.append(
                    str((path if path.is_absolute() else self.root / path).resolve())
                )
            running = is_running(self.root)
            return {
                "editable": not running,
                "reason": "Close KOReader before changing plugin states."
                if running
                else "",
                "disabled": sorted(flags["disabled"]),
                "externalDisabled": flags["externalDisabled"],
                "extraPluginPaths": paths,
            }
        except (OSError, ValueError, RecursionError) as error:
            return {
                "editable": False,
                "reason": str(error) or "KOReader settings could not be read safely.",
                "disabled": [],
                "externalDisabled": None,
                "extraPluginPaths": [],
            }

    def list_installed(self) -> list[dict]:
        state, (builtins, known) = self._state(), self._builtins()
        settings = self.settings_status()
        rows: list[dict] = []
        if self.plugins.is_symlink():
            return rows
        locations = [(self.plugins, False)]
        seen = {self.plugins.resolve()}
        for value in settings["extraPluginPaths"]:
            folder = Path(value)
            if folder not in seen:
                locations.append((folder, True))
                seen.add(folder)
        for path, external in [
            (path, external)
            for folder, external in locations
            for path in sorted(folder.glob("*.koplugin"))
        ]:
            if not path.is_dir() and not path.is_symlink():
                continue
            linked = path.is_symlink()
            metadata = "" if linked else _read_text(path / "_meta.lua")
            version = "" if linked else _plugin_version(path, metadata)
            record = state.get(path.name, {}) if not external else {}
            if not isinstance(record, dict):
                record = {}
            managed = path.name in state and not external
            owned = owned_files(record)
            ownership = bool(owned)
            current = bool(
                ownership
                and version
                and record.get("version")
                and version.lstrip("v") == str(record["version"]).lstrip("v")
            )
            modified_code = (
                modified_owned_code(path, owned) if current and not linked else ""
            )
            current = current and not modified_code
            builtin = path.name in builtins
            removable = (
                not linked
                and not external
                and not builtin
                and (known or managed)
                and bool(PLUGIN_NAME.fullmatch(path.name))
            )
            reason = (
                "Bundled plugins are updated with KOReader."
                if builtin
                else "This plugin uses an extra plugin folder. Manage its files in KOReader."
                if external
                else "This plugin is linked to another folder. Manage it in KOReader."
                if linked
                else "k2 cannot identify bundled plugins in this installation. Update KOReader to identify its bundled plugins before replacing or removing this folder."
                if not known and not managed
                else ""
            )
            state_reason = settings["reason"]
            if not state_reason and external:
                state_reason = (
                    "This plugin uses an extra folder. Change its state in KOReader."
                )
            if not state_reason and linked:
                state_reason = (
                    "This plugin is linked elsewhere. Change its state in KOReader."
                )
            if not state_reason and settings["externalDisabled"] and not builtin:
                state_reason = (
                    "User plugins are disabled globally. Enable them in KOReader first."
                )
            enabled = (
                None
                if settings["externalDisabled"] is None
                else not (
                    path.name[:-9] in settings["disabled"]
                    or (settings["externalDisabled"] and not builtin)
                )
            )
            rows.append(
                {
                    "id": path.name,
                    "name": _lua_string(metadata, "fullname") or path.name[:-9],
                    "description": _lua_string(metadata, "description"),
                    "version": version,
                    "path": str(path),
                    "builtin": builtin,
                    "managed": managed,
                    "removable": removable,
                    "canUpdate": removable,
                    "protectionReason": reason,
                    "enabled": enabled,
                    "stateEditable": not bool(state_reason),
                    "stateReason": state_reason,
                    "external": external,
                    "globalExternalDisabled": settings["externalDisabled"],
                    "sourceVersion": record.get("version", ""),
                    "sourceRepository": record.get("repository", ""),
                    "ownershipKnown": ownership,
                    "ownershipCurrent": current,
                    "updateReason": "Plugin code was changed outside k2. Use its own updater to keep your changes."
                    if modified_code
                    else ""
                    if current
                    else "This existing plugin has no k2 file record. Use its own updater."
                    if not ownership
                    else "This plugin was changed outside k2. Use its own updater.",
                    "status": "Bundled with KOReader"
                    if builtin
                    else "Extra plugin folder"
                    if external
                    else "External link"
                    if linked
                    else "Installed"
                    if removable
                    else "Existing plugin",
                }
            )
        for row in rows:
            if sum(other["id"] == row["id"] for other in rows) > 1:
                row.update(
                    stateEditable=False,
                    stateReason="More than one copy of this plugin is installed. Change its state in KOReader.",
                )
        return sorted(rows, key=lambda row: (row["builtin"], row["name"].casefold()))

    def set_enabled(self, plugin_id: str, enabled: bool) -> dict:
        from .manager import installation_lock

        if (
            not isinstance(plugin_id, str)
            or not PLUGIN_NAME.fullmatch(plugin_id)
            or type(enabled) is not bool
        ):
            raise ValueError("Choose a plugin and a valid enabled state.")
        self._ready()
        with installation_lock(self.root):
            self._ready()
            PluginTransaction(self.root).recover()
            row = next(
                (item for item in self.list_installed() if item["id"] == plugin_id),
                None,
            )
            if not row or not row["stateEditable"]:
                raise ValueError(
                    row["stateReason"] if row else "This plugin is no longer installed."
                )
            original = self._settings_text()
            modified = set_plugin_flag(original, plugin_id[:-9], enabled)
            if modified != original:
                if self._settings_text() != original:
                    raise OSError(
                        "KOReader settings changed during this operation. Try again."
                    )
                self._ready()
                _save_settings(self.root / "settings.reader.lua", modified)
        return {
            "message": "Plugin enabled. Restart KOReader to apply it."
            if enabled
            else "Plugin disabled. Restart KOReader to apply it.",
            "restartRequired": True,
        }

    def _ready(self) -> None:
        from .manager import is_running

        if not (self.root / "koreader.sh").is_file() or self.root.is_symlink():
            raise ValueError("Install KOReader before adding plugins.")
        if self.plugins.is_symlink():
            raise ValueError(
                "The plugins folder is linked elsewhere. Manage this installation in KOReader."
            )
        if is_running(self.root):
            raise ValueError("Close KOReader before changing its plugins.")

    def install(
        self,
        source: str,
        progress: Progress | None = None,
        expected_plugin: str | None = None,
        receipt: dict[str, str] | None = None,
    ) -> dict:
        from .manager import installation_lock

        if expected_plugin is not None:
            if isinstance(expected_plugin, str) and not expected_plugin.endswith(
                ".koplugin"
            ):
                expected_plugin += ".koplugin"
            if not isinstance(expected_plugin, str) or not PLUGIN_NAME.fullmatch(
                expected_plugin
            ):
                raise ValueError("The expected plugin identifier is invalid.")
        receipt = {} if receipt is None else receipt
        if (
            not isinstance(receipt, dict)
            or set(receipt) - {"version", "repository"}
            or not isinstance(receipt.get("version", ""), str)
            or len(receipt.get("version", "")) > 128
            or not isinstance(receipt.get("repository", ""), str)
            or (
                receipt.get("repository")
                and not re.fullmatch(
                    r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", receipt["repository"]
                )
            )
        ):
            raise ValueError("The plugin's release information is invalid.")
        progress = progress or (lambda message, fraction: None)
        self._ready()
        with installation_lock(self.root):
            self._ready()
            PluginTransaction(self.root).recover()
            with tempfile.TemporaryDirectory(
                prefix=".k2-plugins-", dir=self.root
            ) as temporary:
                workspace = Path(temporary)
                with (
                    archive_source(source, workspace, progress) as (path, saved_source),
                    PluginArchive.open(path) as archive,
                ):
                    candidates = archive.plugins()
                    if expected_plugin is not None and set(candidates.values()) != {
                        expected_plugin
                    }:
                        raise ValueError(
                            "The archive does not contain exactly the selected plugin. Nothing was installed."
                        )
                    progress("Checking plugin files", 0.5)
                    preserved = self._install(
                        archive,
                        candidates,
                        workspace,
                        saved_source,
                        progress,
                        expected_plugin,
                        receipt,
                    )
        names = set(candidates.values())
        rows = [row for row in self.list_installed() if row["id"] in names]
        progress("Plugins installed", 1.0)
        message = (
            "Plugin installed. Restart KOReader to load it."
            if len(rows) == 1
            else "Plugins installed. Restart KOReader to load them."
        )
        if preserved:
            message += " Your modified plugin files were kept."
        return {
            "plugins": rows,
            "message": message,
            "preservedFiles": preserved,
            "restartRequired": True,
        }

    def _install(
        self,
        archive: PluginArchive,
        candidates: dict[PurePosixPath, str],
        workspace: Path,
        source: str,
        progress: Progress,
        expected_plugin: str | None,
        receipt: dict[str, str],
    ) -> list[str]:
        state = self._state()
        self._check_targets(candidates, state, archive.total, expected_plugin, receipt)
        staged = workspace / "staged"
        staged.mkdir()
        preserved: list[str] = []
        for archive_root, name in candidates.items():
            state[name], kept = self._stage_plugin(
                archive,
                archive_root,
                name,
                staged,
                state.get(name, {}),
                source,
                expected_plugin,
                receipt,
            )
            preserved.extend(kept)
        self._commit_plugins(candidates.values(), staged, state, progress)
        return preserved

    def _check_targets(self, candidates, state, archive_size, expected_plugin, receipt):
        builtins, known = self._builtins()
        existing = {path.name.casefold(): path.name for path in self.plugins.glob("*")}
        required = archive_size
        for name in candidates.values():
            if name in builtins:
                raise ValueError(
                    f"{name[:-9]} is bundled with KOReader. Update it through KOReader."
                )
            actual = existing.get(name.casefold())
            if actual and actual != name:
                raise ValueError(
                    f"{name} conflicts with an existing plugin's spelling."
                )
            target = self.plugins / name
            if target.is_symlink() or (target.exists() and not target.is_dir()):
                raise ValueError(
                    f"{name} is not a regular plugin folder. Manage it in KOReader."
                )
            if target.exists():
                if not known and name not in state:
                    raise ValueError(
                        f"k2 cannot confirm whether {name[:-9]} is bundled with this KOReader version. The existing plugin was kept."
                    )
                if expected_plugin:
                    self._check_owned_update(target, state.get(name, {}), receipt)
                required += tree_size(target)
        if shutil.disk_usage(self.root).free < required + 4 * 1024 * 1024:
            raise OSError(
                "There is not enough free storage to install these plugins safely."
            )

    def _check_owned_update(
        self, target: Path, record: dict, receipt: dict[str, str]
    ) -> None:
        owned = owned_files(record)
        if not owned:
            raise ValueError(
                "This existing plugin has no k2 file record. Use its own updater to preserve the installation."
            )
        actual = _plugin_version(target, _read_text(target / "_meta.lua"))
        if (
            not actual
            or not record.get("version")
            or actual.lstrip("v") != str(record["version"]).lstrip("v")
            or (
                receipt.get("repository")
                and record.get("repository") != receipt["repository"]
            )
        ):
            raise ValueError(
                "This plugin was installed or updated outside this catalogue. Use its own updater to preserve the installation."
            )
        if modified_owned_code(target, owned):
            raise ValueError(
                "Plugin code was changed outside k2. Use its own updater to keep your changes. Nothing was installed."
            )

    def _stage_plugin(
        self,
        archive,
        archive_root,
        name,
        staged,
        record,
        source,
        expected_plugin,
        receipt,
    ):
        target, new = self.plugins / name, staged / name
        if target.exists():
            shutil.copytree(target, new)
        else:
            new.mkdir()
        old_record = record
        old_files = owned_files(old_record)
        incoming = archive.plugin_files(archive_root)
        keep, retained = preserve_local_files(new, old_files, incoming)
        preserved = [
            name + "/" + relative for relative in sorted(keep | retained.keys())
        ]
        files = archive.extract_plugin(
            archive_root, new, keep, reject_modified_code=bool(expected_plugin)
        )
        files.update(retained)
        version = _plugin_version(new, _read_text(new / "_meta.lua"))
        if (
            receipt.get("version")
            and version
            and version.lstrip("v") != receipt["version"].lstrip("v")
        ):
            raise ValueError(
                "The plugin's version does not match the selected release. Nothing was installed."
            )
        return {
            "source": source,
            "installedAt": int(time.time()),
            "files": files,
            "version": receipt.get("version") or version,
            "repository": receipt.get(
                "repository",
                old_record.get("repository", "")
                if isinstance(old_record, dict)
                else "",
            ),
        }, preserved

    def _commit_plugins(self, names, staged, state, progress):
        self.plugins.mkdir(exist_ok=True)
        completed = []
        if hasattr(os, "sync"):
            os.sync()
        self._ready()
        progress("Installing plugins", 0.9)
        transaction = PluginTransaction(self.root)
        transaction.prepare(names)
        try:
            for name in names:
                target = self.plugins / name
                if target.exists():
                    target.rename(transaction.previous / name)
                    sync_directory(self.plugins)
                    sync_directory(transaction.previous)
                (staged / name).rename(target)
                completed.append(name)
                sync_directory(self.plugins)
                sync_directory(staged)
            if hasattr(os, "sync"):
                os.sync()
            _save_json(
                self.state_path,
                {"schema": 1, "plugins": state, "transaction": transaction.identifier},
            )
        except BaseException as error:
            try:
                transaction.rollback(reversed(completed))
            except OSError as recovery_error:
                raise recovery_error from error
            raise
        transaction.recover()

    def remove(self, plugin_id: str) -> dict:
        from .manager import installation_lock

        if not isinstance(plugin_id, str) or not PLUGIN_NAME.fullmatch(plugin_id):
            raise ValueError("Choose an installed plugin to remove.")
        self._ready()
        with installation_lock(self.root):
            self._ready()
            PluginTransaction(self.root).recover()
            target = self.plugins / plugin_id
            row = next(
                (
                    row
                    for row in self.list_installed()
                    if row["id"] == plugin_id
                    and row["path"] == str(target)
                    and not row["external"]
                ),
                None,
            )
            if not row or not row["removable"]:
                raise ValueError(
                    "This plugin is supplied by KOReader or belongs to an existing installation k2 cannot change."
                )
            state = self._state()
            state.pop(plugin_id, None)
            transaction = PluginTransaction(self.root)
            transaction.prepare([plugin_id])
            try:
                target.rename(transaction.previous / plugin_id)
                sync_directory(self.plugins)
                sync_directory(transaction.previous)
                _save_json(
                    self.state_path,
                    {
                        "schema": 1,
                        "plugins": state,
                        "transaction": transaction.identifier,
                    },
                )
            except BaseException as error:
                try:
                    transaction.recover()
                except OSError as recovery_error:
                    raise recovery_error from error
                raise
            transaction.recover()
        return {
            "message": "Plugin removed. Restart KOReader to apply it.",
            "restartRequired": True,
        }
