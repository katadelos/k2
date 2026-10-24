"""Folder navigation, destination selection and confirmed file changes."""

from functools import partial
from pathlib import PurePosixPath
from typing import Any

from PyQt5.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from ...ui.confirmations import ConfirmationContent, Confirmations
from ...ui.navigation import Navigation
from ...ui.operations import Operation, Operations
from ...ui.tasks import TaskRunner
from .service import FileService


class FilesViewModel(QObject):
    changed = pyqtSignal()
    listingChanged = pyqtSignal()
    selectionChanged = pyqtSignal()
    transferChanged = pyqtSignal()
    feedbackChanged = pyqtSignal()
    activityChanged = pyqtSignal()
    viewChanged = pyqtSignal()

    def __init__(
        self,
        service: FileService,
        navigation: Navigation,
        operations: Operations,
        confirmations: Confirmations,
    ) -> None:
        super().__init__()
        self.service = service
        self.navigation = navigation
        self.operations = operations
        self.confirmations = confirmations
        self._path = ""
        self._rows: list[dict[str, Any]] = []
        self._selected: dict[str, Any] = {}
        self._transfer: dict[str, Any] = {}
        self._show_hidden = False
        self._grid_view = True
        self._error = ""
        self._message = ""
        self._stopped = False
        self._refresh_after = False
        self._tasks = TaskRunner(self)
        self._tasks.completed.connect(self._completed)
        self._tasks.finished.connect(self._finished)
        self._tasks.busyChanged.connect(self._publish_activity)
        self.operations.changed.connect(self._availability_changed)
        self._last_available = self.canChange

    @pyqtProperty("QVariantList", notify=listingChanged)
    def entries(self):
        if self._transfer:
            source = self._transfer["record"]["path"]
            return [
                row
                for row in self._rows
                if row["directory"] and not row["protected"] and row["path"] != source
            ]
        return self._rows

    @pyqtProperty(str, notify=listingChanged)
    def currentPath(self):
        return self._path

    @pyqtProperty(str, notify=listingChanged)
    def location(self):
        return "Reader storage" + (
            " / " + self._path.replace("/", " / ") if self._path else ""
        )

    @pyqtProperty("QVariantList", notify=listingChanged)
    def breadcrumbs(self):
        crumbs = [{"name": "Storage", "path": ""}]
        parts = PurePosixPath(self._path).parts
        for index, name in enumerate(parts):
            crumbs.append({"name": name, "path": "/".join(parts[: index + 1])})
        return crumbs

    @pyqtProperty(bool, notify=listingChanged)
    def showHidden(self):
        return self._show_hidden

    @pyqtProperty(bool, notify=viewChanged)
    def gridView(self):
        return self._grid_view

    @pyqtSlot(bool)
    def setGridView(self, value):
        if value != self._grid_view:
            self._grid_view = value
            self.viewChanged.emit()
            self.changed.emit()

    @pyqtProperty("QVariantMap", notify=selectionChanged)
    def selected(self):
        return self._selected

    @pyqtProperty("QVariantMap", notify=transferChanged)
    def transfer(self):
        return self._transfer

    @pyqtProperty(str, notify=feedbackChanged)
    def error(self):
        return self._error

    @pyqtProperty(str, notify=feedbackChanged)
    def message(self):
        return self._message

    @pyqtProperty(bool, constant=True)
    def demo(self):
        return self.service.is_demo

    @pyqtProperty(bool, notify=activityChanged)
    def busy(self):
        return self._tasks.busy

    @pyqtProperty(bool, notify=activityChanged)
    def canChange(self):
        return (
            not self._stopped
            and not self.busy
            and self.operations.allows({"files", "packages", "reader"}, owner="files")
        )

    @pyqtProperty(str, notify=activityChanged)
    def activity(self):
        return {
            "list": "Opening folder…",
            "copy": "Copying…",
            "move": "Moving…",
            "rename": "Renaming…",
            "mkdir": "Creating folder…",
            "delete": "Deleting…",
        }.get(self._tasks.action, "")

    @pyqtSlot()
    def _availability_changed(self):
        available = self.canChange
        if available != self._last_available:
            self._last_available = available
            self.activityChanged.emit()
            self.changed.emit()

    @pyqtSlot()
    def _publish_activity(self):
        operation = None
        if self.busy:
            working = self._tasks.action != "list"
            operation = Operation(
                resources=frozenset({"files", "packages", "reader"})
                if working
                else frozenset(),
                working=working,
                title=self.activity,
                route="files",
            )
        self.operations.update("files", operation)
        self._last_available = self.canChange
        self.activityChanged.emit()
        self.changed.emit()

    def _feedback(self, error="", message=""):
        self._error = error
        self._message = message
        self.feedbackChanged.emit()
        self.changed.emit()

    def _set_selected(self, record=None):
        self._selected = dict(record or {})
        self.selectionChanged.emit()
        self.changed.emit()

    def _set_transfer(self, transfer=None):
        self._transfer = dict(transfer or {})
        self.transferChanged.emit()
        self.listingChanged.emit()
        self.changed.emit()

    def enter(self):
        if not self.busy:
            self.refresh()

    def leave(self):
        self._set_transfer()
        self._set_selected()

    def stop(self):
        self._stopped = True
        self._refresh_after = False
        self.leave()

    def close(self):
        self.stop()
        self._tasks.wait()
        self.service.close()

    def _read(self, path):
        if self._stopped or self.busy:
            return
        self._tasks.start(
            "list", partial(self.service.list_directory, path, self._show_hidden)
        )

    @pyqtSlot()
    def refresh(self):
        self._feedback()
        self._read(self._path)

    @pyqtSlot(bool)
    def setShowHidden(self, value):
        if self.busy:
            return
        self._show_hidden = value
        self.listingChanged.emit()
        self.refresh()

    @pyqtSlot(str)
    def openFolder(self, path):
        if self.busy:
            return
        if self._transfer:
            source = self._transfer["record"]["path"]
            if path == source or path.startswith(source + "/"):
                return
        self._feedback()
        self._read(path)

    @pyqtSlot()
    def up(self):
        parent = str(PurePosixPath(self._path).parent)
        self.openFolder("" if parent == "." else parent)

    @pyqtSlot(str)
    def select(self, path):
        if self.busy or self._transfer:
            return
        record = next((row for row in self._rows if row["path"] == path), None)
        self._feedback()
        self._set_selected(record)

    @pyqtSlot()
    def clearSelection(self):
        if not self.busy:
            self._set_selected()

    @pyqtSlot(str)
    def beginTransfer(self, action):
        if (
            not self.canChange
            or action not in {"copy", "move"}
            or not self._selected.get("mutable")
        ):
            return
        self._feedback()
        self._set_transfer(
            {"action": action, "record": dict(self._selected), "origin": self._path}
        )
        self._set_selected()

    @pyqtSlot()
    def cancelTransfer(self):
        if not self.busy:
            origin = self._transfer.get("origin", self._path)
            self._set_transfer()
            self.openFolder(origin)

    @pyqtSlot()
    def completeTransfer(self):
        if not self.canChange or not self._transfer:
            return
        request = dict(self._transfer)
        self._start(
            request["action"],
            partial(
                self.service.transfer,
                request["record"],
                self._path,
                copy=request["action"] == "copy",
            ),
        )

    @pyqtSlot(str)
    def newFolder(self, name):
        if self.canChange:
            self._start("mkdir", partial(self.service.new_folder, self._path, name))

    @pyqtSlot(str)
    def renameSelected(self, name):
        if self.canChange and self._selected.get("mutable"):
            self._start(
                "rename", partial(self.service.rename, dict(self._selected), name)
            )

    def _start(self, action, call):
        self._feedback()
        self._tasks.start(action, call)

    def _can_delete(self, record):
        return (
            self.canChange
            and self.navigation.page == "files"
            and self._selected == record
        )

    def _delete(self, record):
        if self._can_delete(record):
            self._start("delete", partial(self.service.delete, record))

    @pyqtSlot()
    def requestDelete(self):
        if not self.canChange or not self._selected.get("mutable"):
            return
        record = dict(self._selected)
        body = "Permanently delete “" + record["name"] + "”"
        body += " and everything inside it?" if record["directory"] else "?"
        body += "\n\nThis cannot be undone."
        if record["link"]:
            body += " Only the link is removed; its target is kept."
        self.confirmations.present(
            "files",
            ConfirmationContent(
                "Delete this folder?" if record["directory"] else "Delete this file?",
                "Delete",
                body,
                ready=True,
            ),
            partial(self._delete, record),
            partial(self._can_delete, record),
        )

    @pyqtSlot(str, object, object)
    def _completed(self, action, result, failure):
        if self._stopped:
            return
        if failure is not None:
            self._feedback(error=failure.message)
        elif action == "list":
            self._path = result["path"]
            self._rows = result["rows"]
            self._set_selected()
            self.listingChanged.emit()
            self.changed.emit()
        else:
            self._feedback(
                message={
                    "copy": "Copied.",
                    "move": "Moved.",
                    "rename": "Renamed.",
                    "mkdir": "Folder created.",
                    "delete": "Deleted.",
                }[action]
            )
            if action in {"copy", "move"}:
                self._set_transfer()
        if action != "list":
            self._refresh_after = True
            self._set_selected()

    @pyqtSlot(str)
    def _finished(self, action):
        if self._refresh_after and not self._stopped:
            self._refresh_after = False
            self._read(self._path)
