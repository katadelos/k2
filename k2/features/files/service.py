"""File operations confined to one reader storage directory."""

import os
import shutil
import stat
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Self

from .moves import move_without_replacing

BOOK_EXTENSIONS = frozenset(
    {
        ".epub",
        ".mobi",
        ".azw",
        ".azw3",
        ".azw4",
        ".kfx",
        ".pdf",
        ".djvu",
        ".djv",
        ".fb2",
        ".cbz",
        ".cbr",
        ".cbt",
        ".cb7",
        ".prc",
        ".pdb",
    }
)
FILE_TYPES = {
    "Image": {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".tiff"},
    "Document": {".txt", ".md", ".rtf", ".doc", ".docx", ".odt", ".html", ".htm"},
    "Audio": {".mp3", ".m4a", ".m4b", ".aac", ".ogg", ".flac", ".wav", ".aax"},
    "Archive": {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar"},
    "App package": {".ipk"},
    "Settings": {".json", ".ini", ".conf", ".cfg", ".yaml", ".toml", ".lua"},
}
PROTECTED_FOLDERS = frozenset({".eink-sdk"})


def format_size(size):
    amount = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if amount < 1024:
            return f"{int(amount)} B" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{amount:.1f} TB"


def file_kind(path):
    suffix = path.suffix.lower()
    if suffix in BOOK_EXTENSIONS or path.name.lower().endswith(".fb2.zip"):
        return "Book", "book"
    for kind, extensions in FILE_TYPES.items():
        if suffix in extensions:
            return kind, "apps" if kind == "App package" else "file"
    return "File", "file"


class FileService:
    """Never follow a link into system storage or replace an existing item."""

    def __init__(
        self, root: str | Path, *, temporary: TemporaryDirectory[str] | None = None
    ) -> None:
        self.root = Path(root).resolve()
        self._temporary = temporary
        self._mounts: set[str] = set()
        self._has_mountinfo = False

    @classmethod
    def for_device(cls, family: str) -> Self:
        roots = {"kindle": "/mnt/us", "kobo": "/mnt/onboard"}
        return cls(roots[family])

    @classmethod
    def demo(cls) -> Self:
        temporary = TemporaryDirectory(prefix="k2-files-")
        service = cls(temporary.name, temporary=temporary)
        documents = service.root / "documents"
        documents.mkdir()
        (documents / "Fiction").mkdir()
        (documents / "Fiction" / "Pride and Prejudice.epub").write_bytes(b"Demo book\n")
        (documents / "A Tale of Two Cities.epub").write_bytes(b"Demo book\n" * 1024)
        (documents / "Reader guide.pdf").write_bytes(b"Demo book\n" * 512)
        (service.root / "Pictures").mkdir()
        (service.root / "Downloads").mkdir()
        (service.root / "Reading list.txt").write_text("Books to read next\n")
        return service

    @property
    def is_demo(self):
        return self._temporary is not None

    def close(self):
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None

    def _path(self, relative, *, item=False):
        self._read_mounts()
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or "\0" in str(path):
            raise ValueError("Choose an item inside reader storage.")
        if item and not path.parts:
            raise ValueError("Reader storage itself cannot be changed.")
        if path.parts and path.parts[0].lower() in PROTECTED_FOLDERS:
            raise ValueError(
                "This folder belongs to the running system and cannot be changed here."
            )
        current = self.root
        # Final links can be renamed/deleted, but are never opened or traversed.
        for part in path.parts[:-1] if item else path.parts:
            current /= part
            if current.is_symlink():
                raise ValueError("Links cannot be used as folders.")
            if not current.is_dir():
                raise OSError(
                    "This folder is no longer available. Refresh and try again."
                )
            if self._mounted(current):
                raise ValueError(
                    "Mounted filesystems cannot be opened or changed here."
                )
        return self.root / path

    def _read_mounts(self):
        # Linux bind mounts can share the parent's device number, so ismount()
        # alone cannot identify the SDK's mounted system directories.
        mountinfo = Path("/proc/self/mountinfo")
        self._mounts = set()
        self._has_mountinfo = mountinfo.is_file()
        if self._has_mountinfo:
            for line in mountinfo.read_text().splitlines():
                fields = line.split()
                if len(fields) > 4:
                    value = fields[4]
                    for escaped, character in (
                        ("\\040", " "),
                        ("\\011", "\t"),
                        ("\\012", "\n"),
                        ("\\134", "\\"),
                    ):
                        value = value.replace(escaped, character)
                    self._mounts.add(value)

    def _mounted(self, path):
        return str(path) in self._mounts or os.path.ismount(path)

    def _name(self, name):
        if (
            not name
            or name in {".", ".."}
            or name != name.strip()
            or any(character in name for character in '/\\\0<>:"|?*')
            or any(ord(character) < 32 for character in name)
            or name.endswith(".")
            or len(name.encode("utf-8")) > 255
        ):
            raise ValueError(
                "Use a name without slashes, control characters or trailing spaces."
            )
        return name

    def _record(self, path):
        info = path.lstat()
        link = stat.S_ISLNK(info.st_mode)
        directory = stat.S_ISDIR(info.st_mode)
        regular = stat.S_ISREG(info.st_mode)
        protected = (
            path.parent == self.root and path.name.lower() in PROTECTED_FOLDERS
        ) or self._mounted(path)
        if directory:
            kind, icon = "Folder", "folder"
        elif link:
            kind, icon = "Link", "file"
        elif regular:
            kind, icon = file_kind(path)
        else:
            kind, icon = "Special file", "file"
        suffix = path.suffix[1:].upper()
        detail = kind
        if regular:
            detail += (
                (" · " + suffix if suffix else "") + " · " + format_size(info.st_size)
            )
        return {
            "name": path.name,
            "path": path.relative_to(self.root).as_posix(),
            "directory": directory,
            "link": link,
            "mutable": not protected and (directory or regular or link),
            "protected": protected,
            "kind": kind,
            "icon": icon,
            "detail": "System folder · protected" if protected else detail,
            "size": format_size(info.st_size) if regular else "",
            "extension": suffix if regular else "",
            "modified": datetime.fromtimestamp(info.st_mtime).strftime(
                "%d %b %Y, %H:%M"
            ),
            "identity": [
                info.st_dev,
                info.st_ino,
                info.st_mode,
                info.st_size,
                info.st_mtime_ns,
            ],
        }

    def list_directory(self, relative="", show_hidden=False):
        directory = self._path(relative)
        rows = []
        for path in directory.iterdir():
            if not show_hidden and path.name.startswith("."):
                continue
            try:
                rows.append(self._record(path))
            except FileNotFoundError:
                continue
        rows.sort(
            key=lambda row: (not row["directory"], row["name"].casefold(), row["name"])
        )
        return {"path": relative, "rows": rows}

    def _source(self, record):
        path = self._path(record["path"], item=True)
        current = self._record(path)
        if current["identity"] != record["identity"]:
            raise OSError(
                "This item changed since you selected it. Refresh and try again."
            )
        if not current["mutable"]:
            raise ValueError("System folders and special files cannot be changed here.")
        if path.is_dir() and not path.is_symlink():
            nested_mount = any(path in Path(mount).parents for mount in self._mounts)
            if not self._has_mountinfo:

                def fail(error):
                    raise error

                nested_mount = any(
                    self._mounted(Path(parent) / name)
                    for parent, folders, _ in os.walk(
                        path, followlinks=False, onerror=fail
                    )
                    for name in folders
                )
            if nested_mount:
                raise ValueError(
                    "This folder contains a mounted filesystem and cannot be changed here."
                )
        return path

    @staticmethod
    def _unused(path):
        if os.path.lexists(path):
            raise FileExistsError(
                "An item with that name already exists. Choose another name."
            )

    def new_folder(self, relative, name):
        path = self._path(relative) / self._name(name)
        if path.parent == self.root and path.name.lower() in PROTECTED_FOLDERS:
            raise ValueError("This folder name is reserved for the system.")
        self._unused(path)
        path.mkdir()

    def _destination(self, source, directory, name):
        target = self._path(directory) / self._name(name)
        if target.parent == self.root and target.name.lower() in PROTECTED_FOLDERS:
            raise ValueError("This folder name is reserved for the system.")
        if target == source or source in target.parents:
            raise ValueError("Choose a different folder outside the selected item.")
        self._unused(target)
        return target

    def rename(self, record, name):
        source = self._source(record)
        target = self._destination(
            source, source.parent.relative_to(self.root).as_posix(), name
        )
        move_without_replacing(source, target)

    def transfer(self, record, directory, *, copy):
        source = self._source(record)
        target = self._destination(source, directory, source.name)
        if not copy:
            # Both paths are confined to the same storage volume. A nested mount
            # fails visibly instead of degrading a move into copy-then-delete.
            move_without_replacing(source, target)
        elif source.is_symlink():
            os.symlink(os.readlink(source), target)
        elif source.is_dir():
            try:
                shutil.copytree(source, target, symlinks=True)
            except OSError as error:
                raise OSError(
                    f"Copy could not finish: {error}. A partial copy may remain in the destination."
                ) from error
        else:
            try:
                with source.open("rb") as incoming, target.open("xb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
            except OSError as error:
                raise OSError(
                    f"Copy could not finish: {error}. A partial copy may remain in the destination."
                ) from error

    def delete(self, record):
        source = self._source(record)
        if source.is_dir() and not source.is_symlink():
            shutil.rmtree(source)
        else:
            source.unlink()
