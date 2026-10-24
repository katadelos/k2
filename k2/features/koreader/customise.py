"""A reviewed selection of native KOReader extensions, separate from opkg."""

import json
import os
import re
import tempfile
import time
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote

from .catalogue import CATALOGUE, ENTRIES, CatalogueEntry
from .http import open_https
from .plugins import PluginManager
from .ports import PluginBackend

# From ZenOS v4.0.1 modules/filebrowser/patches/incompatible_plugins_check.lua.
_ZEN_PLUGINS = {
    "simpleui",
    "vos",
    "quickmenu",
    "appearance",
    "burrow",
    "quickui",
    "zzz-readermenuredesign",
    "shortcutstoolbar",
    "neo_quicksetting",
}
_ZEN_PATCHES = {
    "2---stretched-covers.lua",
    "2--disable-all-CB-widgets.lua",
    "2--disable-all-PT-widgets.lua",
    "2--rounded-covers.lua",
    "2--stretched-rounded-covers.lua",
    "2-navbar-vos.lua",
    "2-new-collections-star.lua",
    "2-new-progress-bar-colored.lua",
    "2-new-progress-bar.lua",
    "2-pages-badge.lua",
    "2-percent-badge.lua",
    "2-rounded-folder-covers.lua",
    "2-series-indicator.lua",
    "20-faded-finished-books.lua",
    "2-quick-settings.lua",
    "2-automatic-book-series.lua",
    "2-ui-font.lua",
    "2-custom-navbar.lua",
    "2-browser-double-tap.lua",
    "2-browser-hide-underline.lua",
    "2-browser-up-folder.lua",
    "2-coverimage-eink-optimize.lua",
    "2-disable-top-menu-zones.lua",
    "2-filemanager-titlebar.lua",
    "2-menu-size.lua",
    "2-new-status-icons.lua",
    "2-non-blocking-wifi.lua",
    "2-screensaver-chapter.lua",
    "2-screensaver-cover.lua",
    "2-series-badge-numbered.lua",
    "2-statusbar-better-compact.lua",
    "2-statusbar-cycle-presets.lua",
}
_PATCH_CONFLICTS = {
    "simpleui": {
        "2-custom-navbar.lua",
        "2-filemanager-titlebar.lua",
        "2-navbar-vos.lua",
    },
    "readinginsights": {"2-reading-insights-popup.lua", "2-reading-stats-popup.lua"},
    "customisablesleepscreen": {
        "2-customisable-sleep-screen.lua",
        "2-screensaver-chapter.lua",
        "2-screensaver-cover.lua",
    },
    "bookends": {
        "2-statusbar-better-compact.lua",
        "2-statusbar-cycle-presets.lua",
        "2-new-progress-bar.lua",
        "2-new-progress-bar-colored.lua",
    },
}


def _text(path: Path, limit: int = 1024 * 1024) -> str:
    try:
        if path.is_symlink() or path.stat().st_size > limit:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _version(value: str) -> tuple[int, ...]:
    match = re.fullmatch(
        r"v?(\d+(?:\.\d+){1,3})(?:-\d+(?:-g[0-9a-f]+)?)?", str(value).strip()
    )
    if not match:
        return ()
    parts = tuple(int(part) for part in match.group(1).split("."))
    return parts + (0,) * (4 - len(parts))


def _asset_url(entry: CatalogueEntry, asset: str) -> str:
    return f"https://github.com/{entry.repository}/releases/download/{quote(entry.tag, safe='')}/{quote(asset, safe='')}"


@dataclass(frozen=True)
class Compatibility:
    reason: str
    label: str
    detail: str


@dataclass(frozen=True)
class InstallAvailability:
    allowed: bool
    update: bool
    reason: str
    newer: bool


class CustomiseManager:
    """Synchronous worker API; reads local state unless refresh is explicit."""

    def __init__(
        self,
        root: str | Path,
        device_info: Mapping[str, object],
        *,
        backend: PluginBackend | None = None,
    ) -> None:
        self.root = Path(root)
        self.info = dict(device_info)
        self.backend: PluginBackend = (
            backend if backend is not None else PluginManager(self.root)
        )
        self.cache_path = self.root / ".k2-customise.json"

    def _cache(self) -> dict:
        try:
            value = json.loads(_text(self.cache_path))
            if value.get("schema") == 1 and isinstance(value.get("releases"), dict):
                releases = {
                    key: item
                    for key, item in value["releases"].items()
                    if key in ENTRIES
                    and isinstance(item, dict)
                    and isinstance(item.get("version"), str)
                    and isinstance(item.get("assets"), list)
                    and all(isinstance(name, str) for name in item["assets"])
                }
                checked = value.get("checkedAt", 0)
                return {
                    "schema": 1,
                    "releases": releases,
                    "checkedAt": checked
                    if isinstance(checked, int) and checked >= 0
                    else 0,
                    "error": value.get("error", "")
                    if isinstance(value.get("error", ""), str)
                    else "",
                }
        except ValueError, AttributeError:
            pass
        return {"schema": 1, "checkedAt": 0, "releases": {}, "error": ""}

    def _save_cache(self, value: dict) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.root,
            prefix=".k2-customise-",
            delete=False,
        ) as stream:
            path = Path(stream.name)
            try:
                json.dump(value, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
                stream.close()
                path.replace(self.cache_path)
            finally:
                path.unlink(missing_ok=True)

    def _release(self, entry: CatalogueEntry) -> dict:
        with open_https(
            f"https://api.github.com/repos/{entry.repository}/releases/latest",
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "k2 KOReader customisation",
            },
            timeout=12,
        ) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("GitHub returned too much release information.")
        value = json.loads(raw)
        if not isinstance(value, dict) or not isinstance(value.get("assets"), list):
            raise ValueError("GitHub returned invalid release information.")
        tag = value.get("tag_name")
        if (
            value.get("draft")
            or value.get("prerelease")
            or not isinstance(tag, str)
            or not _version(tag)
        ):
            raise ValueError(
                "The latest release could not be identified as a stable version."
            )
        assets = [
            item["name"]
            for item in value.get("assets", [])
            if isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and item.get("state") == "uploaded"
        ]
        return {
            "version": tag.removeprefix("v"),
            "assets": assets,
            "checkedAt": int(time.time()),
        }

    def _refresh(self, cache: dict) -> dict:
        errors = []

        def fetch(entry: CatalogueEntry) -> tuple[CatalogueEntry, dict | None, str]:
            try:
                return entry, self._release(entry), ""
            except HTTPError as error:
                reason = (
                    "GitHub is limiting requests."
                    if error.code in {403, 429}
                    else "GitHub could not provide release information."
                )
            except OSError, ValueError, URLError:
                reason = "Check your connection and try again."
            return entry, None, reason

        with ThreadPoolExecutor(max_workers=3) as pool:
            for entry, release, error in pool.map(fetch, CATALOGUE):
                if release:
                    cache["releases"][entry.id] = release
                else:
                    errors.append(entry.name + ": " + error)
        if not errors:
            cache["checkedAt"] = int(time.time())
        if not errors:
            cache["error"] = ""
        elif len(errors) == len(CATALOGUE):
            cache["error"] = (
                "GitHub is limiting requests. Try again later."
                if any("limiting requests" in error for error in errors)
                else "Could not check releases. Check Wi-Fi and try again."
            ) + " Saved release information is still available."
        else:
            cache["error"] = (
                f"Checked {len(CATALOGUE) - len(errors)} of {len(CATALOGUE)} releases. Some release information could not be refreshed."
            )
        try:
            self._save_cache(cache)
        except OSError:
            cache["error"] = (
                cache["error"] + " Release information could not be saved."
            ).strip()
        return cache

    def _reader_version(self) -> str:
        return _text(self.root / "git-rev", 1024).strip()

    def _installation_problem(self) -> str:
        from .manager import is_running

        if self.root.is_symlink() or not (self.root / "koreader.sh").is_file():
            return "Install KOReader before customising it."
        if (self.root / "plugins").is_symlink():
            return "KOReader’s plugins directory is linked elsewhere. Manage this installation inside KOReader."
        if is_running(self.root):
            return "Close KOReader before changing its customisations."
        return ""

    def _native_variant(self) -> tuple[str, str]:
        architecture = str(self.info.get("architecture", "")).lower()
        kernel = re.match(r"^(\d+)\.(\d+)", str(self.info.get("kernel", "")))
        if not kernel:
            return (
                "",
                "The running kernel could not be identified. No LocalSend executable has been selected.",
            )
        if tuple(map(int, kernel.groups())) < (3, 2):
            return (
                "",
                "LocalSend’s old-kernel support needs a transfer test on this device. Selecting arm-legacy does not fix missing Linux syscalls; installation is unavailable here.",
            )
        if architecture in {"armv7", "armv7l", "armv7hl"}:
            return "armv7", ""
        if architecture in {"armv5", "armv5l", "armv5tel", "armv6", "armv6l"}:
            return "arm-legacy", ""
        return (
            "",
            f"No reviewed LocalSend executable is selected for {architecture or 'this architecture'}.",
        )

    def _patches(self) -> set[str]:
        directory = self.root / "patches"
        if (directory / ".patches_disabled").is_file():
            return set()
        return {path.name for path in directory.glob("*.lua") if path.is_file()}

    def _conflict(
        self, entry: CatalogueEntry, installed: list[dict], patches: set[str]
    ) -> str:
        plugin_id = entry.plugin_id
        active = {
            row["id"][:-9]: row.get("name") or row["id"][:-9]
            for row in installed
            if row["id"] != plugin_id and row.get("enabled") is not False
        }
        all_ids = {row["id"] for row in installed}
        if entry.id == "zenos" and "zen_ui.koplugin" in all_ids:
            return "Zen UI is already installed. Update it from Zen UI settings; its updater preserves settings and migrates to ZenOS through two restarts. Do not install zenos.koplugin beside zen_ui.koplugin."
        conflicts = set()
        if entry.id == "simpleui":
            conflicts.update({"zenos", "zen_ui"} & active.keys())
        if entry.id == "zenos":
            conflicts.update(_ZEN_PLUGINS & active.keys())
            conflicts.update({"projecttitle", "ProjectTitle"} & active.keys())
        if conflicts:
            return (
                "Disable "
                + ", ".join(sorted(active[name] for name in conflicts))
                + " in KOReader or k2 first, then refresh. Existing interface settings will be kept."
            )
        matching = patches & (
            _ZEN_PATCHES
            if entry.id == "zenos"
            else _PATCH_CONFLICTS.get(entry.id, set())
        )
        if matching:
            return (
                "Disable these existing patches in KOReader before continuing: "
                + ", ".join(sorted(matching))
                + ". k2 will not rename or remove them."
            )
        dependency = {
            "bookshelf": "coverbrowser.koplugin",
            "readinginsights": "statistics.koplugin",
        }.get(entry.id)
        if dependency:
            required = next((row for row in installed if row["id"] == dependency), None)
            label = "Cover browser" if entry.id == "bookshelf" else "Statistics"
            if not required or required.get("enabled") is not True:
                return f"Enable KOReader’s built-in {label} plugin first, then refresh."
        return ""

    def snapshot(self, refresh: bool = False) -> dict:
        cache = self._cache()
        if refresh:
            cache = self._refresh(cache)
        problem = self._installation_problem()
        installed = self.backend.list_installed()
        state = self.backend.settings_status()
        reader_version = _version(self._reader_version())
        patches = self._patches()
        rows = [
            self._entry_snapshot(
                entry, cache, problem, installed, state, reader_version, patches
            )
            for entry in CATALOGUE
        ]
        return {
            "items": rows,
            "checkedAt": cache.get("checkedAt", 0),
            "error": cache.get("error", ""),
        }

    def _compatibility(
        self,
        entry: CatalogueEntry,
        reader_version: tuple[int, ...],
        native: str,
        native_problem: str,
        problem: str,
    ) -> Compatibility:
        reason = problem
        compatibility = "Reviewed release"
        detail = (
            "No upstream device matrix or minimum KOReader version is published. This release has not been tested on this device."
            if entry.id == "readinginsights"
            else "Kindle and Kobo are documented upstream; this release has not been tested on this device."
        )
        if self.info.get("family") not in {"kindle", "kobo"}:
            reason = reason or "This selection is for Kindle and Kobo installations."
        minimum = entry.minimum
        if minimum and (not reader_version or reader_version < _version(minimum)):
            reason = reason or (
                f"This release needs KOReader {minimum} or newer. Update KOReader first."
                if reader_version
                else f"KOReader’s installed version could not be read. This release needs {minimum} or newer."
            )
            compatibility = "Needs newer KOReader"
        elif minimum:
            detail = f"Requires KOReader {minimum} or newer. " + detail
        elif entry.id not in {"readinginsights", "localsend"}:
            detail += " No upstream minimum KOReader version is published."
        if native_problem:
            reason = reason or native_problem
            compatibility = "Device not verified"
        elif native:
            detail = f"Uses the {native} executable; Linux 3.2 or newer. A physical transfer has not been verified by k2."
        return Compatibility(reason, compatibility, detail)

    def _installation_policy(
        self,
        entry: CatalogueEntry,
        present: bool,
        existing: dict | None,
        current_version: tuple[int, ...],
        reviewed_version: tuple[int, ...],
        reason: str,
    ) -> InstallAvailability:
        managed = bool(existing and existing.get("managed"))
        newer = False
        can_install = not reason
        update = False
        if present:
            if not existing:
                can_install = False
            elif existing.get("external") or not existing.get("canUpdate"):
                can_install = False
                reason = (
                    reason
                    or existing.get("protectionReason")
                    or "Manage this existing plugin through its own updater."
                )
            elif not managed or existing.get("sourceRepository") != entry.repository:
                can_install = False
                reason = (
                    reason
                    or "This existing installation has no reviewed k2 file receipt. Use the plugin’s own updater; its settings and local changes will be kept."
                )
            elif not existing.get("ownershipCurrent"):
                can_install = False
                reason = (
                    reason
                    or existing.get("updateReason")
                    or "This plugin changed outside k2. Use its own updater to preserve the installation."
                )
            elif not current_version:
                can_install = False
                reason = (
                    reason
                    or "The installed plugin version could not be read. Use its own updater to avoid replacing a newer or modified installation."
                )
            elif current_version >= reviewed_version:
                can_install = False
                if current_version > reviewed_version:
                    newer = True
            else:
                update = can_install
        return InstallAvailability(can_install, update, reason, newer)

    def _entry_snapshot(
        self,
        entry: CatalogueEntry,
        cache: dict,
        problem: str,
        installed: list[dict],
        state: dict,
        reader_version: tuple[int, ...],
        patches: set[str],
    ) -> dict:
        matches = [row for row in installed if row["id"] == entry.plugin_id]
        existing = matches[0] if len(matches) == 1 else None
        present = bool(matches)
        current = existing.get("version", "") if existing else ""
        current_version, reviewed_version = (
            _version(current),
            _version(entry.version),
        )
        native, native_problem = (
            self._native_variant() if entry.id == "localsend" else ("", "")
        )
        suitability = self._compatibility(
            entry, reader_version, native, native_problem, problem
        )
        reason, compatibility, detail = (
            suitability.reason,
            suitability.label,
            suitability.detail,
        )
        if not state.get("editable"):
            reason = (
                reason
                or state.get("reason")
                or "KOReader’s plugin settings could not be read safely. Manage this setup inside KOReader."
            )
        if state.get("externalDisabled"):
            reason = (
                reason
                or "External plugins are disabled in KOReader. Enable them in KOReader’s plugin management first."
            )
        reason = reason or self._conflict(entry, installed, patches)
        if len(matches) > 1:
            reason = "More than one copy of this plugin is installed. Resolve the duplicate folders in KOReader before changing it."
        if reason and compatibility == "Reviewed release":
            compatibility = "Check setup"
        release = cache["releases"].get(entry.id, {})
        upstream = release.get("version", "")
        upstream_newer = bool(
            _version(upstream) and _version(upstream) > reviewed_version
        )
        if upstream_newer:
            detail += f" Upstream {upstream} is newer and has not been reviewed for this catalogue. k2 keeps the reviewed {entry.version} download."
        asset = entry.asset.format(variant=native)
        if release.get("version") == entry.version and asset not in release.get(
            "assets", []
        ):
            reason = (
                reason
                or "The reviewed release asset is no longer listed upstream. No replacement download has been selected."
            )
        activation_reason = reason
        managed = bool(existing and existing.get("managed"))
        availability = self._installation_policy(
            entry, present, existing, current_version, reviewed_version, reason
        )
        reason = availability.reason
        if availability.newer:
            compatibility = "Newer installed"
            detail += " The installed plugin is newer than k2’s reviewed release and will not be downgraded."
        enabled = existing.get("enabled") if existing else None
        editable = bool(existing and existing.get("stateEditable"))
        return {
            "id": entry.id,
            "name": entry.name,
            "summary": entry.summary,
            "description": entry.description,
            "category": entry.category,
            "repository": "https://github.com/" + entry.repository,
            "pluginId": entry.plugin_id,
            "installed": present,
            "version": current,
            "availableVersion": entry.version,
            "upstreamVersion": upstream,
            "update": availability.update,
            "enabled": enabled,
            "managed": managed,
            "canInstall": availability.allowed,
            "canRemove": bool(existing and existing.get("removable") and not problem),
            "canEnable": bool(
                existing and enabled is False and editable and not activation_reason
            ),
            "canDisable": bool(
                existing and enabled is True and editable and not problem
            ),
            "compatibility": compatibility,
            "compatibilityDetail": detail,
            "reason": reason,
            "instructions": entry.instructions,
        }

    def plan(self, action: str, item_id: str) -> dict:
        if item_id not in ENTRIES or action not in {
            "install",
            "remove",
            "enable",
            "disable",
        }:
            raise ValueError("Choose a customisation and an available action.")
        row = next(item for item in self.snapshot()["items"] if item["id"] == item_id)
        key = {
            "install": "canInstall",
            "remove": "canRemove",
            "enable": "canEnable",
            "disable": "canDisable",
        }[action]
        verb = (
            "Update"
            if action == "install" and row["installed"]
            else action.capitalize()
        )
        body = {
            "install": f"Download the reviewed {row['availableVersion']} release from its upstream project. Existing plugin settings are kept. Restart KOReader to load it.",
            "remove": "Remove this plugin’s folder. KOReader’s books and reading history are kept; configuration outside the plugin folder is kept. Restart KOReader to apply the change.",
            "enable": "Enable this plugin in KOReader’s plugin settings. Restart KOReader to load it.",
            "disable": "Disable this plugin in KOReader’s plugin settings. Its files and settings are kept. Restart KOReader to apply the change.",
        }[action]
        if not row[key]:
            body = (
                row["reason"]
                or "This action is not needed or is unavailable for the current installation."
            )
        return {
            "title": f"{verb} {row['name']}?",
            "label": verb,
            "body": body,
            "ready": row[key],
        }

    def apply(self, action: str, item_id: str) -> dict:
        plan = self.plan(action, item_id)
        if not plan["ready"]:
            raise ValueError(plan["body"])
        entry = ENTRIES[item_id]
        if action == "install":
            variant, _ = self._native_variant() if item_id == "localsend" else ("", "")
            result = self.backend.install(
                _asset_url(entry, entry.asset.format(variant=variant)),
                expected_plugin=entry.plugin_id,
                receipt={
                    "version": entry.version,
                    "repository": entry.repository,
                },
            )
        elif action == "remove":
            result = self.backend.remove(entry.plugin_id)
        else:
            result = self.backend.set_enabled(entry.plugin_id, action == "enable")
        snapshot = self.snapshot()
        snapshot["message"] = result["message"]
        return snapshot
