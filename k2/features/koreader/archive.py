"""Bounded plugin archive downloads and extraction without links or special files."""

import hashlib
import re
import stat
import tarfile
import zipfile
from collections.abc import Callable, Collection, Iterator
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import IO
from urllib.parse import unquote, urlsplit, urlunsplit

from .http import open_https
from .ownership import MAX_EXTRACTED, MAX_MEMBERS, FileFingerprint, code_file, safe_path

PLUGIN_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+-]*\.koplugin\Z")
MAX_DOWNLOAD = 64 * 1024 * 1024


@contextmanager
def archive_source(
    source: str, workspace: Path, progress: Callable[[str, float], None]
) -> Iterator[tuple[Path, str]]:
    source = str(source).strip()
    if not source:
        raise ValueError("Enter a plugin archive URL or local path.")
    parsed = urlsplit(source)
    if parsed.scheme == "https":
        if not parsed.hostname or parsed.username or parsed.password:
            raise ValueError(
                "Enter an HTTPS download URL without a username or password."
            )
        path = workspace / "download"
        progress("Downloading plugin archive", 0.05)
        with (
            open_https(
                source, headers={"User-Agent": "k2/0.1 KOReader plugins"}, timeout=30
            ) as response,
            path.open("wb") as out,
        ):
            length = response.headers.get("Content-Length", "")
            expected = int(length) if length.isdigit() else 0
            if expected > MAX_DOWNLOAD:
                raise ValueError("Plugin archives must be smaller than 64 MiB.")
            copied = 0
            while True:
                chunk = response.read(128 * 1024)
                if not chunk:
                    break
                copied += len(chunk)
                if copied > MAX_DOWNLOAD:
                    raise ValueError("Plugin archives must be smaller than 64 MiB.")
                out.write(chunk)
                progress(
                    "Downloading plugin archive",
                    0.05 + (0.4 * copied / expected if expected else 0),
                )
            if expected and copied != expected:
                raise OSError("The plugin download was incomplete. Try again.")
        # Signed download credentials and query parameters do not belong in saved state.
        saved_source = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    elif parsed.scheme == "file":
        if parsed.netloc not in {"", "localhost"} or parsed.query or parsed.fragment:
            raise ValueError("Select a local plugin archive.")
        path, saved_source = Path(unquote(parsed.path)), "Local archive"
    elif parsed.scheme:
        raise ValueError("Use an HTTPS download URL or a local ZIP or tar archive.")
    else:
        path, saved_source = Path(source).expanduser(), "Local archive"
    if not path.is_file():
        raise ValueError("The plugin archive could not be found.")
    if path.stat().st_size > MAX_DOWNLOAD:
        raise ValueError("Plugin archives must be smaller than 64 MiB.")
    yield path, saved_source


@dataclass(frozen=True)
class ArchiveEntry:
    path: PurePosixPath
    member: zipfile.ZipInfo | tarfile.TarInfo
    directory: bool
    size: int
    mode: int

    @classmethod
    def from_zip(cls, member: zipfile.ZipInfo) -> ArchiveEntry:
        mode = member.external_attr >> 16
        if (
            stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}
            or member.flag_bits & 1
        ):
            raise ValueError(
                "Plugin archives cannot contain links, special files or encrypted files."
            )
        return cls(
            safe_path(member.filename), member, member.is_dir(), member.file_size, mode
        )

    @classmethod
    def from_tar(cls, member: tarfile.TarInfo) -> ArchiveEntry:
        if not (member.isdir() or member.isfile()):
            raise ValueError("Plugin archives cannot contain links or special files.")
        return cls(
            safe_path(member.name), member, member.isdir(), member.size, member.mode
        )


class PluginArchive:
    """Validated entries and extraction; the caller owns the open archive context."""

    def __init__(self, archive: zipfile.ZipFile | tarfile.TarFile):
        self.archive = archive
        members = (
            (ArchiveEntry.from_zip(member) for member in archive.infolist())
            if isinstance(archive, zipfile.ZipFile)
            else (ArchiveEntry.from_tar(member) for member in archive)
        )
        self.entries: list[ArchiveEntry] = []
        seen: set[str] = set()
        self.total = 0
        for entry in members:
            if len(self.entries) >= MAX_MEMBERS:
                raise ValueError("The plugin archive contains too many files.")
            key = str(entry.path).casefold()
            if key in seen:
                raise ValueError("The plugin archive contains duplicate file paths.")
            seen.add(key)
            self.total += entry.size
            if entry.size < 0 or self.total > MAX_EXTRACTED:
                raise ValueError("The extracted plugins must be smaller than 256 MiB.")
            self.entries.append(entry)

    @classmethod
    @contextmanager
    def open(cls, path: Path) -> Iterator[PluginArchive]:
        try:
            if zipfile.is_zipfile(path):
                with zipfile.ZipFile(path) as archive:
                    yield cls(archive)
            else:
                with tarfile.open(path, "r:*") as archive:
                    yield cls(archive)
        except (tarfile.TarError, zipfile.BadZipFile) as error:
            raise ValueError(
                "Choose a ZIP or tar archive containing a .koplugin folder."
            ) from error

    def _stream(self, entry: ArchiveEntry) -> IO[bytes]:
        if isinstance(self.archive, zipfile.ZipFile) and isinstance(
            entry.member, zipfile.ZipInfo
        ):
            return self.archive.open(entry.member)
        if isinstance(self.archive, tarfile.TarFile) and isinstance(
            entry.member, tarfile.TarInfo
        ):
            stream = self.archive.extractfile(entry.member)
            if stream is not None:
                return stream
        raise ValueError("The plugin archive member could not be read.")

    def plugins(self) -> dict[PurePosixPath, str]:
        candidates: dict[PurePosixPath, str] = {}
        for entry in self.entries:
            path = entry.path
            if entry.directory or path.name != "main.lua":
                continue
            parent, name = path.parent, path.parent.name
            if not PLUGIN_NAME.fullmatch(name) and len(parent.parts) == 1:
                # GitHub source archives append a branch or tag to the repository folder.
                match = re.fullmatch(
                    r"([A-Za-z0-9][A-Za-z0-9_.+-]*\.koplugin)-.+", name
                )
                name = match.group(1) if match else name
            if PLUGIN_NAME.fullmatch(name):
                if name.casefold() in {
                    value.casefold() for value in candidates.values()
                }:
                    raise ValueError(
                        "The archive contains more than one copy of the same plugin."
                    )
                candidates[parent] = name
        if not candidates:
            raise ValueError(
                "No plugin was found. The archive needs a .koplugin folder containing main.lua."
            )
        if len(candidates) > 32:
            raise ValueError("Install no more than 32 plugins at a time.")
        for parent in candidates:
            if any(other != parent and other in parent.parents for other in candidates):
                raise ValueError(
                    "The archive contains nested plugin folders. Install the individual plugin archive."
                )
        return candidates

    def plugin_files(self, source: PurePosixPath) -> set[str]:
        return {
            str(entry.path.relative_to(source))
            for entry in self.entries
            if not entry.directory and source in entry.path.parents
        }

    def extract_plugin(
        self,
        source: PurePosixPath,
        destination: Path,
        preserve: Collection[str] = (),
        *,
        reject_modified_code: bool = False,
    ) -> dict[str, FileFingerprint]:
        files: dict[str, FileFingerprint] = {}
        for entry in self.entries:
            try:
                relative = entry.path.relative_to(source)
            except ValueError:
                continue
            output = destination / str(relative)
            if entry.directory:
                output.mkdir(parents=True, exist_ok=True)
                continue
            output.parent.mkdir(parents=True, exist_ok=True)
            if output.is_dir():
                raise ValueError("A plugin file conflicts with an existing folder.")
            stream = self._stream(entry)
            digest = hashlib.blake2b(digest_size=16)
            keep = str(relative) in preserve
            with stream, nullcontext() if keep else output.open("wb") as target:
                remaining = entry.size
                prefix = b""
                while remaining:
                    chunk = stream.read(min(128 * 1024, remaining))
                    if not chunk:
                        raise ValueError("The plugin archive is incomplete.")
                    if not prefix:
                        prefix = chunk[:4]
                    digest.update(chunk)
                    if target is not None:
                        target.write(chunk)
                    remaining -= len(chunk)
                if stream.read(1):
                    raise ValueError(
                        "The plugin archive contains an invalid file size."
                    )
            code = bool(entry.mode & 0o111) or code_file(str(relative), prefix)
            if keep and code and reject_modified_code:
                raise ValueError(
                    "The release would replace locally changed plugin code. Use its own updater to keep your changes. Nothing was installed."
                )
            if not keep:
                output.chmod(0o755 if entry.mode & 0o111 else 0o644)
            files[str(relative)] = {
                "size": entry.size,
                "digest": digest.hexdigest(),
                "code": code,
            }
        return files
