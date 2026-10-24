"""Durable plugin backups, with recovery that never replaces a live target."""

import json
import os
import re
import shutil
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ..files.moves import move_without_replacing
from .archive import PLUGIN_NAME


def sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class PluginTransaction:
    """Called only while the installation lock is held and KOReader is closed."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.directory = root / ".k2-plugin-transaction"
        self.previous = self.directory / "previous"
        self.uncommitted = self.directory / "uncommitted"
        self.receipt = root / ".k2-plugins.json"
        self.journal = self.directory / "journal.json"
        self.identifier = ""

    def _blocked(self, reason: str) -> OSError:
        return OSError(
            f"Plugin recovery could not finish: {reason}. "
            f"Preserved files are in {self.directory}. Resolve this before changing plugins."
        )

    def _receipt(self) -> bytes | None:
        if self.receipt.is_symlink():
            raise self._blocked("the plugin receipt is a symbolic link")
        if not self.receipt.exists():
            return None
        if not self.receipt.is_file() or self.receipt.stat().st_size > 2 * 1024 * 1024:
            raise self._blocked("the plugin receipt cannot be read safely")
        return self.receipt.read_bytes()

    def prepare(self, names: Iterable[str]) -> None:
        names = list(names)
        receipt = self._receipt()
        self.directory.mkdir(mode=0o700)
        try:
            self.previous.mkdir()
            self.uncommitted.mkdir()
            self.identifier = uuid.uuid4().hex
            if receipt is not None:
                with (self.directory / "receipt.previous").open("xb") as stream:
                    stream.write(receipt)
                    stream.flush()
                    os.fsync(stream.fileno())
            journal = {
                "schema": 1,
                "id": self.identifier,
                "names": names,
                "previous": [
                    name for name in names if (self.root / "plugins" / name).exists()
                ],
                "receipt": receipt is not None,
            }
            with self.journal.open("x") as stream:
                json.dump(journal, stream)
                stream.flush()
                os.fsync(stream.fileno())
            sync_directory(self.directory)
            sync_directory(self.root)
        except BaseException:
            # No plugin has been moved before preparation succeeds.
            shutil.rmtree(self.directory)
            raise

    def _read_journal(self) -> dict[str, Any]:
        if (
            self.directory.is_symlink()
            or self.journal.is_symlink()
            or not self.journal.is_file()
            or self.journal.stat().st_size > 1024 * 1024
        ):
            raise self._blocked("the recovery record is unavailable")
        try:
            value = json.loads(self.journal.read_text())
        except ValueError as error:
            raise self._blocked("the recovery record is unreadable") from error
        if not isinstance(value, dict) or value.get("schema") != 1:
            raise self._blocked("the recovery record is invalid")
        names, previous = value.get("names"), value.get("previous")
        if (
            not isinstance(value.get("id"), str)
            or not re.fullmatch(r"[0-9a-f]{32}", value["id"])
            or type(value.get("receipt")) is not bool
            or not isinstance(names, list)
            or not all(
                isinstance(name, str) and PLUGIN_NAME.fullmatch(name) for name in names
            )
            or len(names) != len(set(names))
            or not isinstance(previous, list)
            or not all(isinstance(name, str) and name in names for name in previous)
        ):
            raise self._blocked("the recovery record is invalid")
        for path in (self.previous, self.uncommitted):
            if path.is_symlink() or (path.exists() and not path.is_dir()):
                raise self._blocked("a recovery directory was replaced")
        return value

    def recover(self) -> None:
        if not os.path.lexists(self.directory):
            return
        journal = self._read_journal()
        receipt = self._receipt()
        try:
            state = json.loads(receipt) if receipt is not None else {}
        except ValueError:
            state = {}
        if isinstance(state, dict) and state.get("transaction") == journal["id"]:
            self._cleanup()
            return
        restored = self.directory / "restored"
        if restored.is_symlink():
            raise self._blocked("the recovery completion marker was replaced")
        if restored.is_file() and restored.read_text() == journal["id"]:
            self._cleanup()
            return
        old = self.directory / "receipt.previous"
        if old.is_symlink() or (journal["receipt"] and not old.is_file()):
            raise self._blocked("the previous plugin receipt is unavailable")
        if receipt != (old.read_bytes() if journal["receipt"] else None):
            raise self._blocked("the plugin receipt changed outside this transaction")
        for name in journal["names"]:
            self._restore(name, name in journal["previous"])
        if self.uncommitted.exists() and any(self.uncommitted.iterdir()):
            # A failed attempt's new files may have been changed externally.
            # Preserve them even after the old installation is restored.
            saved = self.root / (".k2-plugin-uncommitted-" + journal["id"])
            if os.path.lexists(saved):
                raise self._blocked(f"{saved} already exists")
            self.uncommitted.rename(saved)
            sync_directory(self.root)
        with restored.open("w") as stream:
            stream.write(journal["id"])
            stream.flush()
            os.fsync(stream.fileno())
        sync_directory(self.directory)
        self._cleanup()

    def _restore(self, name: str, existed: bool) -> None:
        backup, target = self.previous / name, self.root / "plugins" / name
        if backup.is_symlink():
            raise self._blocked(f"the backup of {name} is a symbolic link")
        if backup.exists():
            if os.path.lexists(target):
                raise self._blocked(f"{target} already exists; its contents were kept")
            try:
                move_without_replacing(backup, target)
                sync_directory(target.parent)
                sync_directory(self.previous)
            except OSError as error:
                raise self._blocked(f"could not restore {name}: {error}") from error
        elif existed != os.path.lexists(target):
            raise self._blocked(f"{target} no longer matches the recovery record")

    def rollback(self, installed: Iterable[str]) -> None:
        # Receipt replacement may have succeeded before a directory flush
        # failed. Its transaction marker is the commit decision.
        receipt = self._receipt()
        try:
            state = json.loads(receipt) if receipt is not None else {}
        except ValueError:
            state = {}
        if isinstance(state, dict) and state.get("transaction") == self.identifier:
            self.recover()
            return
        try:
            for name in installed:
                target = self.root / "plugins" / name
                # Preserve the unsuccessful new copy too. A failure here must not
                # destroy either version or run automatic temporary-dir cleanup.
                target.rename(self.uncommitted / name)
            sync_directory(self.uncommitted)
            sync_directory(self.root / "plugins")
        except OSError as error:
            raise self._blocked(str(error)) from error
        self.recover()

    def _cleanup(self) -> None:
        # Detach a completed transaction before deleting its recovery record.
        # Interrupted cleanup then leaves harmless obsolete files, not an
        # active transaction with a partly deleted journal or receipt.
        identifier = self._read_journal()["id"]
        discarded = self.root / (".k2-plugin-cleanup-" + identifier)
        if os.path.lexists(discarded):
            raise self._blocked(f"{discarded} already exists")
        self.directory.rename(discarded)
        sync_directory(self.root)
        shutil.rmtree(discarded)
