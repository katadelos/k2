"""Validate plugin file ownership and preserve local changes during updates."""

import hashlib
import os
import re
import stat
from pathlib import Path, PurePosixPath
from typing import TypedDict

MAX_EXTRACTED = 256 * 1024 * 1024
MAX_MEMBERS = 10000


class FileFingerprint(TypedDict):
    size: int
    digest: str
    code: bool


def safe_path(name: str) -> PurePosixPath:
    if (
        not name
        or name.startswith("/")
        or "\\" in name
        or ":" in name
        or len(name) > 1024
        or any(ord(char) < 32 for char in name)
    ):
        raise ValueError("The plugin archive contains an unsafe file path.")
    path = PurePosixPath(name)
    if ".." in path.parts:
        raise ValueError("The plugin archive contains an unsafe file path.")
    return path


def owned_files(record: object) -> dict[str, FileFingerprint]:
    files = record.get("files") if isinstance(record, dict) else None
    if not isinstance(files, dict) or not files or len(files) > MAX_MEMBERS:
        return {}
    for name, fingerprint in files.items():
        if not isinstance(name, str):
            return {}
        try:
            path = safe_path(name)
        except ValueError, TypeError:
            return {}
        if (
            str(path) != name
            or not path.parts
            or not isinstance(fingerprint, dict)
            or type(fingerprint.get("size")) is not int
            or not 0 <= fingerprint["size"] <= MAX_EXTRACTED
            or not isinstance(fingerprint.get("digest"), str)
            or not re.fullmatch(r"[0-9a-f]{32}", fingerprint["digest"])
            or ("code" in fingerprint and type(fingerprint["code"]) is not bool)
        ):
            return {}
    return files


def unchanged_file(path: Path, fingerprint: FileFingerprint) -> bool:
    try:
        if (
            path.is_symlink()
            or not path.is_file()
            or path.stat().st_size != fingerprint["size"]
        ):
            return False
        digest = hashlib.blake2b(digest_size=16)
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(128 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest() == fingerprint["digest"]
    except OSError:
        return False


def code_file(name: str, prefix: bytes = b"") -> bool:
    path = PurePosixPath(name)
    return (
        path.suffix.lower() in {".lua", ".luac", ".sh", ".py", ".so", ".dll", ".dylib"}
        or ".so." in path.name
        or prefix.startswith((b"\x7fELF", b"#!"))
    )


def modified_owned_code(root: Path, files: dict[str, FileFingerprint]) -> str:
    for relative, fingerprint in files.items():
        path = root / relative
        # Linked paths cannot safely establish ownership of installed code.
        if any(
            (root / Path(*PurePosixPath(relative).parts[:index])).is_symlink()
            for index in range(1, len(PurePosixPath(relative).parts) + 1)
        ):
            return relative
        code = fingerprint.get("code", False) or code_file(relative)
        if not code and path.is_file():
            try:
                with path.open("rb") as stream:
                    code = code_file(relative, stream.read(4))
            except OSError:
                return relative
        if code and not unchanged_file(path, fingerprint):
            return relative
    return ""


def tree_size(path: Path) -> int:
    """Reject links before copying an existing plugin into a writable staging area."""
    total, count = 0, 0
    for base, directories, files in os.walk(path, followlinks=False):
        for name in directories + files:
            item = Path(base) / name
            info = item.lstat()
            if stat.S_ISLNK(info.st_mode) or not (
                stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)
            ):
                raise ValueError(
                    "This existing plugin contains links or special files. Manage it in KOReader."
                )
            total += info.st_size if stat.S_ISREG(info.st_mode) else 0
            count += 1
            if total > MAX_EXTRACTED or count > MAX_MEMBERS:
                raise ValueError("This existing plugin is too large to replace in k2.")
    return total


def preserve_local_files(
    root: Path, previous: dict[str, FileFingerprint], incoming: set[str]
) -> tuple[set[str], dict[str, FileFingerprint]]:
    """Remove obsolete owned files and identify modified files to retain."""
    keep: set[str] = set()
    retained: dict[str, FileFingerprint] = {}
    if not previous:
        return keep, retained
    for relative, fingerprint in previous.items():
        path = root / relative
        if relative in incoming or not path.exists():
            continue
        if not unchanged_file(path, fingerprint):
            retained[relative] = fingerprint
            continue
        path.unlink()
        parent = path.parent
        while parent != root and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    for relative in incoming:
        path = root / relative
        if path.exists() and (
            relative not in previous or not unchanged_file(path, previous[relative])
        ):
            keep.add(relative)
    return keep, retained
