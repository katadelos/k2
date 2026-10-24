"""Install upstream KOReader releases beside, rather than inside, the SDK."""

import fcntl
import hashlib
import json
import os
import pwd
import re
import shlex
import shutil
import stat
import struct
import tempfile
import time
import zipfile
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError

from ..files.service import FileService
from .http import open_https
from .ports import ReaderDevice
from .transactions import PluginTransaction

RELEASE_API = "https://api.github.com/repos/koreader/koreader/releases/latest"
MAX_DOWNLOAD = 256 * 1024 * 1024
MAX_UNPACKED = 512 * 1024 * 1024
VARIANT_LABELS = {
    "kindlehf": "Kindle · hard float",
    "kindlepw2": "Kindle · PW2 and newer",
    "kindle": "Kindle · Touch / first Paperwhite",
    "kindle-legacy": "Kindle · keyboard models",
    "kobo": "Kobo",
    "kobov5": "Kobo · firmware 5",
}
LAUNCHER_MARKER = "# Managed by k2: KOReader launcher"


def read_text(path, limit=65536):
    try:
        with Path(path).open(errors="replace") as stream:
            return stream.read(limit).strip()
    except OSError:
        return ""


def device_variant(family, system=Path("/")):
    """Use the stock ABI and board checks used by KOReader's otaModel()."""
    system = Path(system)
    if family == "kobo":
        return (
            "kobov5"
            if any(
                (system / p).exists()
                for p in ("usr/bin/hwdetect", "usr/bin/hwdetect.sh")
            )
            else "kobo"
        )
    if family != "kindle":
        return ""
    if (system / "lib/ld-linux-armhf.so.3").exists():
        return "kindlehf"
    serial = read_text(system / "proc/usid")
    if serial[:1] in {"B", "9"}:
        code = serial[2:4]
        if code in {"02", "03", "04", "05", "09", "08", "06", "0A"}:
            return "kindle-legacy"
        if code in {
            "0E",
            "23",
            "0F",
            "11",
            "10",
            "12",
            "24",
            "1B",
            "1D",
            "1F",
            "1C",
            "20",
        }:
            return "kindle"
    hardware = re.search(
        r"^Hardware\s*:\s*(.+)$", read_text(system / "proc/cpuinfo"), re.M
    )
    if hardware and re.search(r"i\.MX\s?[6-7]|MT8110", hardware[1]):
        return "kindlepw2"
    return ""


def is_running(root):
    root = Path(root).resolve()
    for process in Path("/proc").glob("[0-9]*"):
        try:
            command = (process / "cmdline").read_bytes().split(b"\0")
            if not any(
                part.endswith((b"reader.lua", b"koreader.sh")) for part in command
            ):
                continue
            if (process / "cwd").resolve() == root or any(
                str(root).encode() in part for part in command
            ):
                return True
        except OSError:
            continue
    return False


@contextmanager
def installation_lock(root):
    root = Path(root)
    root.parent.mkdir(parents=True, exist_ok=True)
    with (root.parent / ("." + root.name + ".k2.lock")).open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise OSError("Another KOReader installation is in progress.") from error
        yield


def _open_request(url: str, *, timeout: float):
    return open_https(
        url,
        headers={
            "User-Agent": "k2/0.1 KOReader installer",
            "Accept": "application/vnd.github+json",
        },
        timeout=timeout,
    )


def _network_error(error):
    if isinstance(error, HTTPError) and error.code in (403, 429):
        return OSError("GitHub's download limit was reached. Try again later.")
    return OSError(
        "Could not contact KOReader's release server. Check Wi-Fi and try again."
    )


def _version(value):
    match = re.match(r"v?(\d{4})\.(\d+)(?:\.(\d+))?", value or "")
    return tuple(int(part or 0) for part in match.groups()) if match else ()


def _installed_variant(root, family):
    try:
        record = json.loads(read_text(root / ".k2-install.json"))
        if (
            record.get("gitRev") == read_text(root / "git-rev", 256)
            and record.get("variant") in VARIANT_LABELS
        ):
            return record["variant"]
    except ValueError, AttributeError:
        pass
    # Read the native executable, not the SDK ABI or an old install receipt.
    if family == "kindle":
        try:
            with (root / "luajit").open("rb") as binary:
                header = binary.read(52)
            if header[:6] == b"\x7fELF\x01\x01" and len(header) >= 52:
                flags = struct.unpack_from("<I", header, 36)[0]
                return "kindlehf" if flags & 0x400 else "kindle-softfloat"
        except OSError:
            pass
    return ""


def _size(root):
    return (
        sum(
            path.stat().st_size
            for path in Path(root).rglob("*")
            if path.is_file() and not path.is_symlink()
        )
        if root.exists()
        else 0
    )


def _sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    size: int
    digest: str


class KOReaderManager:
    def __init__(self, device: ReaderDevice) -> None:
        self.family = device.family
        self.store = Path(device.store)
        self.variant = device_variant(self.family)
        self.release: Release | None = None
        self.selected = ""
        self.checked = 0
        self.restart_needed = False

    def _locations(self):
        if self.family == "kobo":
            locations = [
                self.store / ".adds/koreader",
                self.store / "koreader",
                self.store / ".kobo/koreader",
            ]
            launchers = list((self.store / ".adds/nm").glob("*"))
            launchers += list((self.store / ".adds/kfmon/config").glob("*.ini"))
        else:
            locations = [self.store / "koreader", self.store / ".adds/koreader"]
            launchers = [self.store / "extensions/koreader/menu.json"]
            launchers += list((self.store / "documents").glob("*koreader*.sh"))
            launchers += list((self.store / "documents").glob("*KOReader*.sh"))
            launchers += list((self.store / "applications").glob("*KOReader*.sh"))
        if self.family == "kindle":
            for managed in self._launcher_paths():
                root = self._launcher_root(managed)
                if root and (root / "koreader.sh").is_file():
                    locations.append(root)
        # Respect explicitly configured custom locations without crawling books.
        # These files only contribute existing paths; no shell or Lua is run.
        pattern = re.compile(
            re.escape(str(self.store)) + r"/[^\n\r\"';]*?/koreader\.sh"
        )
        for launcher in launchers[:64]:
            for match in pattern.finditer(read_text(launcher)):
                if len(match[0]) > 1024:
                    continue
                path = Path(match[0]).parent
                try:
                    if (
                        path not in locations
                        and path.is_dir()
                        and (path / "koreader.sh").is_file()
                    ):
                        locations.append(path)
                except OSError:
                    continue
        return locations

    def _discover(self):
        found, seen = [], set()
        for path in self._locations():
            resolved = path.resolve()
            if resolved in seen or not resolved.is_relative_to(self.store.resolve()):
                continue
            seen.add(resolved)
            previous = resolved.with_name("." + resolved.name + ".k2-previous")
            # Finish the interrupted rename before exposing a missing install.
            # The complete previous copy stays intact until the new one exists.
            if (
                not resolved.exists()
                and previous.is_dir()
                and not previous.is_symlink()
            ):
                with installation_lock(resolved):
                    if not resolved.exists() and previous.is_dir():
                        previous.rename(resolved)
                        _sync_directory(resolved.parent)
            # Include incomplete installs: never silently install a second copy.
            if resolved.is_dir():
                found.append(
                    {
                        "path": str(resolved),
                        "version": read_text(resolved / "git-rev", 256),
                        "complete": all(
                            (resolved / file).is_file()
                            for file in ("koreader.sh", "reader.lua", "luajit")
                        ),
                    }
                )
        return found

    def _root(self, found=None):
        found = self._discover() if found is None else found
        if self.selected and any(item["path"] == self.selected for item in found):
            return Path(self.selected)
        return (
            Path(found[0]["path"])
            if len(found) == 1
            else self._locations()[0]
            if not found
            else None
        )

    def status(self) -> dict:
        found = self._discover()
        root = self._root(found)
        installed = root is not None and root.is_dir()
        complete = installed and all(
            (root / file).is_file() for file in ("koreader.sh", "reader.lua", "luajit")
        )
        version = read_text(root / "git-rev", 256) if installed else ""
        installed_variant = _installed_variant(root, self.family) if installed else ""
        compatible = (
            not installed_variant
            or installed_variant == self.variant
            or (
                installed_variant == "kindle-softfloat"
                and self.variant in {"kindle", "kindlepw2", "kindle-legacy"}
            )
        )
        running = bool(root and is_running(root))
        latest = self.release.version if self.release else ""
        safe_root = bool(
            root
            and root.resolve() != self.store.resolve()
            and root.resolve().is_relative_to(self.store.resolve())
            and (not root.exists() or root.is_dir())
        )
        info = root.stat() if installed else None
        identity = (
            [info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns]
            if info
            else []
        )
        scriptlet = self.store / "documents/KOReader.sh"
        reason = (
            ""
            if self.variant
            else "The stock firmware ABI could not be identified. No download has been selected."
        )
        if root is None:
            reason = "More than one KOReader installation was found. Choose the copy to manage."
        elif running:
            reason = "Close KOReader before changing its installation or plugins."
        elif installed and not complete:
            reason = "This installation is incomplete. Reinstalling keeps its settings and plugins."
        if root and not safe_root:
            reason = "KOReader needs a directory inside user storage. Resolve the conflicting path before installing."
        update = bool(
            latest
            and installed
            and _version(version)
            and _version(latest) > _version(version)
        )
        # A nightly or newer manual install must not be downgraded to stable.
        newer = bool(
            latest
            and _version(version)
            and (
                _version(version) > _version(latest)
                or (_version(version) == _version(latest) and "-" in version)
            )
        )
        if newer and compatible:
            reason = "This copy is newer than the stable release. Use KOReader's updater to stay on its current channel."
        if not compatible:
            reason = "This KOReader build does not match the device. Reinstall the matching release to keep your settings."
        return {
            "installed": installed,
            "complete": bool(complete),
            "path": str(root) if root else "",
            "version": version,
            "variant": self.variant,
            "variantLabel": VARIANT_LABELS.get(self.variant, "Unknown device"),
            "installedVariant": installed_variant,
            "compatible": compatible,
            "supported": bool(self.variant),
            "reason": reason,
            "releaseVersion": latest,
            "updateAvailable": update,
            "newerInstalled": newer,
            "running": running,
            "canInstall": bool(
                self.release
                and self.variant
                and safe_root
                and not running
                and (not newer or not compatible)
            ),
            "canOpen": bool(complete and safe_root and compatible and not running),
            "installations": found,
            "lastChecked": self.checked,
            "identity": identity,
            "canRemove": bool(installed and safe_root and not running),
            "canAddScriptlet": bool(
                self.family == "kindle"
                and complete
                and safe_root
                and compatible
                and not running
            ),
            "scriptletInstalled": bool(
                root
                and self._launcher_root(scriptlet) == root
                and scriptlet.with_suffix(".svg").is_file()
            ),
            "restartRequired": self.restart_needed,
            "detail": "Restart the Kobo before your next file transfer so its library skips KOReader's program files."
            if self.restart_needed
            else "",
        }

    def select_installation(self, path: str) -> dict:
        if not any(item["path"] == path for item in self._discover()):
            raise ValueError("That KOReader installation is no longer available.")
        self.selected = path
        return self.status()

    def check_release(self) -> dict:
        if not self.variant:
            raise OSError(self.status()["reason"])
        try:
            with _open_request(RELEASE_API, timeout=20) as response:
                data = response.read(2 * 1024 * 1024 + 1)
            if len(data) > 2 * 1024 * 1024:
                raise ValueError("Release metadata is too large.")
            release = json.loads(data)
            version = release["tag_name"]
            if (
                not re.fullmatch(r"v\d{4}\.\d+(?:\.\d+)?", version)
                or release.get("prerelease")
                or release.get("draft")
            ):
                raise ValueError("The server did not return a stable KOReader release.")
            name = f"koreader-{self.variant}-{version}.zip"
            asset = next(
                (item for item in release["assets"] if item["name"] == name), None
            )
            if not asset:
                raise ValueError(
                    "This release does not include a build for this device."
                )
            url = f"https://github.com/koreader/koreader/releases/download/{version}/{name}"
            if (
                asset["browser_download_url"] != url
                or not 0 < asset["size"] <= MAX_DOWNLOAD
            ):
                raise ValueError("The release download information is invalid.")
            digest = asset.get("digest", "")
            if not isinstance(digest, str) or not re.fullmatch(
                r"sha256:[0-9a-f]{64}", digest
            ):
                raise ValueError("The release is missing its download checksum.")
            self.release = Release(
                version=version, url=url, size=asset["size"], digest=digest[7:]
            )
            self.checked = int(time.time())
        except (HTTPError, URLError, TimeoutError) as error:
            raise _network_error(error) from error
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise OSError(
                "KOReader's release server returned incomplete information."
            ) from error
        return self.status()

    def _download(self, destination: Path, release: Release) -> None:
        digest, count = hashlib.sha256(), 0
        try:
            with (
                _open_request(release.url, timeout=30) as response,
                destination.open("wb") as output,
            ):
                while True:
                    block = response.read(256 * 1024)
                    if not block:
                        break
                    count += len(block)
                    if count > release.size:
                        raise OSError("The KOReader download was larger than expected.")
                    digest.update(block)
                    output.write(block)
                output.flush()
                os.fsync(output.fileno())
        except (HTTPError, URLError, TimeoutError) as error:
            raise _network_error(error) from error
        if count != release.size or digest.hexdigest() != release.digest:
            raise OSError("The KOReader download was incomplete or damaged. Try again.")

    def install(self) -> dict:
        state = self.status()
        release = self.release
        if not state["canInstall"] or release is None:
            raise OSError(
                state["reason"]
                or (
                    "This copy is newer than the stable release."
                    if state["newerInstalled"]
                    else "Check for a KOReader release before installing."
                )
            )
        root = Path(state["path"])
        with installation_lock(root):
            self._recover(root)
            if is_running(root):
                raise OSError("Close KOReader before installing an update.")
            PluginTransaction(root).recover()
            old_size = _size(root)
            if (
                shutil.disk_usage(root.parent).free
                < old_size + release.size + 128 * 1024 * 1024
            ):
                raise OSError(
                    "There is not enough free user storage to safely stage KOReader and keep the existing copy."
                )
            with tempfile.TemporaryDirectory(
                prefix=".k2-koreader-", dir=root.parent
            ) as temporary:
                work = Path(temporary)
                archive, staged = work / "release.zip", work / "koreader"
                self._download(archive, release)
                with zipfile.ZipFile(archive) as package:
                    members = self._validate_archive(package)
                    unpacked = sum(item.file_size for item in members)
                    if (
                        shutil.disk_usage(root.parent).free
                        < old_size + unpacked + 16 * 1024 * 1024
                    ):
                        raise OSError(
                            "There is not enough free user storage to unpack this release."
                        )
                    if root.exists():
                        shutil.copytree(root, staged, symlinks=True)
                    else:
                        staged.mkdir()
                    for member in members:
                        relative = PurePosixPath(member.filename).relative_to(
                            "koreader"
                        )
                        target = staged.joinpath(*relative.parts)
                        if any(
                            parent.is_symlink()
                            for parent in [target, *target.parents]
                            if parent == staged or staged in parent.parents
                        ):
                            raise OSError(
                                "A KOReader program file is redirected by a symbolic link. Resolve it before updating."
                            )
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with (
                            package.open(member) as source,
                            target.open("wb") as output,
                        ):
                            shutil.copyfileobj(source, output, 256 * 1024)
                        target.chmod(
                            0o755 if (member.external_attr >> 16) & 0o111 else 0o644
                        )
                installed_version = read_text(staged / "git-rev", 256)
                if installed_version != release.version:
                    raise OSError(
                        "The downloaded KOReader version does not match its release."
                    )
                manifest = {
                    "schema": 1,
                    "version": installed_version,
                    "gitRev": installed_version,
                    "variant": self.variant,
                    "builtinPlugins": sorted(
                        {
                            PurePosixPath(item.filename).parts[2]
                            for item in members
                            if item.filename.startswith("koreader/plugins/")
                            and len(PurePosixPath(item.filename).parts) > 3
                        }
                    ),
                }
                (staged / ".k2-install.json").write_text(json.dumps(manifest) + "\n")
                # Flush staged data before renaming on FAT/FUSE-backed user storage.
                if hasattr(os, "sync"):
                    os.sync()
                if is_running(root):
                    raise OSError(
                        "KOReader was opened during installation. Close it and try again."
                    )
                if self.family == "kobo":
                    self._exclude_kobo_library(root)
                self._replace(root, staged)
            self.selected = str(root)
        return self.status()

    def uninstall(self, identity: Sequence[int]) -> dict:
        state = self.status()
        if not state["canRemove"]:
            raise OSError(
                state["reason"] or "Choose an installed copy of KOReader to remove."
            )
        root = Path(state["path"])
        with installation_lock(root):
            if is_running(root):
                raise OSError("Close KOReader before uninstalling it.")
            PluginTransaction(root).recover()
            if state["identity"] != list(identity):
                raise OSError(
                    "This installation changed. Refresh and confirm its removal again."
                )
            # Finish cleanup of a previous update before removing the current
            # copy, otherwise discovery could restore that backup afterward.
            self._recover(root)
            # Reuse storage deletion's identity, symlink and nested-mount checks.
            FileService(self.store).delete(
                {
                    "path": root.relative_to(self.store.resolve()).as_posix(),
                    "identity": list(identity),
                }
            )
            for launcher in self._launcher_paths():
                if self._launcher_root(launcher) == root:
                    launcher.unlink()
                    for extension in (".png", ".svg"):
                        launcher.with_suffix(extension).unlink(missing_ok=True)
            self.selected = ""
        return self.status()

    def _validate_archive(self, package):
        members, names, total = [], set(), 0
        if len(package.infolist()) > 20000:
            raise OSError("The KOReader archive contains too many files.")
        for member in package.infolist():
            path = PurePosixPath(member.filename)
            mode = member.external_attr >> 16
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in member.filename
                or "\0" in member.filename
                or stat.S_ISLNK(mode)
                or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR))
            ):
                raise OSError("The KOReader archive contains an unsafe file path.")
            if not path.parts or path.parts[0] != "koreader" or member.is_dir():
                continue
            if member.filename.casefold() in names:
                raise OSError("The KOReader archive contains duplicate files.")
            names.add(member.filename.casefold())
            total += member.file_size
            if total > MAX_UNPACKED or member.flag_bits & 1:
                raise OSError("The KOReader archive cannot be safely unpacked.")
            members.append(member)
        if (
            not {
                "koreader/koreader.sh",
                "koreader/reader.lua",
                "koreader/luajit",
                "koreader/git-rev",
            }
            <= names
        ):
            raise OSError("The download is not a complete KOReader release.")
        return members

    def _exclude_kobo_library(self, root):
        # QSettings uses the same INI quoting and shared-file locking as Nickel.
        # A raw INI replacement could lose a concurrent stock-settings change.
        from PyQt5.QtCore import QSettings

        config = self.store / ".kobo/Kobo/Kobo eReader.conf"
        if not config.is_file():
            raise OSError(
                "The Kobo settings file is missing. Finish stock setup before installing KOReader."
            )
        settings = QSettings(str(config), QSettings.IniFormat)
        settings.setIniCodec("UTF-8")
        settings.sync()
        existing = settings.value("FeatureSettings/ExcludeSyncFolders", "")
        if not isinstance(existing, str):
            raise OSError(
                "The Kobo library exclusion setting is invalid. Check it before installing KOReader."
            )
        relative = root.resolve().relative_to(self.store.resolve()).as_posix()
        exclusion = "(?:^|/)" + re.escape(relative) + "(?:/|$).*"
        if exclusion in existing:
            return
        combined = (
            "(?:" + existing + ")|(?:" + exclusion + ")" if existing else exclusion
        )
        settings.setValue("FeatureSettings/ExcludeSyncFolders", combined)
        settings.sync()
        if settings.status() != QSettings.NoError:
            raise OSError(
                "Could not save the Kobo library exclusion. KOReader has not been replaced."
            )
        self.restart_needed = True

    def _recover(self, root):
        previous = root.with_name("." + root.name + ".k2-previous")
        if previous.exists():
            if previous.is_symlink():
                raise OSError(
                    "The previous KOReader staging folder is a symbolic link. Resolve it before updating."
                )
            if root.exists():
                shutil.rmtree(previous)
            else:
                previous.rename(root)
            _sync_directory(root.parent)

    def _replace(self, root, staged):
        previous = root.with_name("." + root.name + ".k2-previous")
        moved = False
        try:
            if root.exists():
                root.rename(previous)
                moved = True
                _sync_directory(root.parent)
            staged.rename(root)
            _sync_directory(root.parent)
        except OSError:
            if moved and not root.exists():
                previous.rename(root)
                _sync_directory(root.parent)
            raise
        if moved:
            shutil.rmtree(previous)

    def _launcher_paths(self):
        return (
            [
                self.store / "documents/KOReader.sh",
                self.store / "applications/KOReader.sh",
            ]
            if self.family == "kindle"
            else []
        )

    @staticmethod
    def _launcher_root(path):
        marker = LAUNCHER_MARKER + "\nexec "
        if path.is_symlink() or path.parent.is_symlink():
            return None
        text = read_text(path)
        if marker not in text:
            return None
        try:
            argv = shlex.split(text.split(marker, 1)[1])
        except ValueError:
            return None
        return Path(argv[-1]).parent if argv else None

    def add_scriptlet(self) -> dict:
        if not self.status()["canAddScriptlet"]:
            raise OSError(
                "Choose a ready KOReader installation on Kindle before adding its shortcut."
            )
        argv = self.launch_command()
        target = self.store / "documents/KOReader.sh"
        icon = target.with_suffix(".svg")
        if target.parent.is_symlink() or target.is_symlink() or icon.is_symlink():
            raise OSError(
                "The library shortcut path is a symbolic link. Choose a regular documents folder."
            )
        if target.exists() and self._launcher_root(target) is None:
            raise OSError("The existing documents/KOReader.sh is not managed by k2.")
        if not target.exists() and icon.exists():
            raise OSError(
                "An icon already exists at documents/KOReader.svg. Move it before adding the shortcut."
            )
        target.parent.mkdir(exist_ok=True)
        body = (
            "#!/bin/sh\n# Name: KOReader\n# Author: k2\n"
            + LAUNCHER_MARKER
            + "\nexec "
            + shlex.join(argv)
            + "\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", dir=target.parent, prefix=".koreader-", delete=False
        ) as output:
            temporary = Path(output.name)
            output.write(body)
        try:
            temporary.chmod(0o755)
            icon.write_text(
                (Path(__file__).parents[2] / "ui/assets/koreader.svg").read_text()
            )
            temporary.replace(target)
            # A single documents entry is visible to both launchers. Move the
            # previous k2-owned applications shortcut rather than duplicate it.
            previous = self.store / "applications/KOReader.sh"
            if self._launcher_root(previous) is not None:
                previous.unlink()
                for extension in (".png", ".svg"):
                    previous.with_suffix(extension).unlink(missing_ok=True)
        finally:
            temporary.unlink(missing_ok=True)
        return self.status()

    def launch_command(self) -> list[str]:
        state = self.status()
        if not state["canOpen"]:
            raise OSError(state["reason"] or "Install KOReader before opening it.")
        root = Path(state["path"])
        return [
            "/usr/bin/env",
            "-i",
            "HOME=" + pwd.getpwuid(os.getuid()).pw_dir,
            "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "LANG=en_US.UTF-8",
            "DISPLAY=:0",
            "/bin/sh",
            str(root / "koreader.sh"),
        ]
