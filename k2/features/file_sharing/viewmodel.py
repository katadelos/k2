"""File-sharing controls; service lifetime is independent of the k2 window."""

from functools import partial

from PyQt5.QtCore import QObject, QTimer, pyqtProperty, pyqtSignal, pyqtSlot

from ...core.packages import PackageFeature
from ...ui.confirmations import ConfirmationContent, Confirmations
from ...ui.navigation import Navigation
from ...ui.operations import Operation, Operations
from ...ui.tasks import TaskFailure, TaskRunner
from .ports import FileSharingBackend, SharingAction, SharingState


class FileSharingViewModel(QObject):
    changed = pyqtSignal()
    stateChanged = pyqtSignal()

    def __init__(
        self,
        service: FileSharingBackend,
        navigation: Navigation,
        operations: Operations,
        confirmations: Confirmations,
    ) -> None:
        super().__init__()
        self.service, self.navigation = service, navigation
        self.operations, self.confirmations = operations, confirmations
        self._feature: PackageFeature | None = None
        self._state: SharingState = {}
        self._error = ""
        self._status_known = False
        self._reconciling = False
        self._needs_reconcile = False
        self._stopped = False
        self._warning = ""
        self._connection_type = "phone"
        self._pending_action: SharingAction | None = None
        self.tasks = TaskRunner(self)
        self.tasks.completed.connect(self.completed)
        self.tasks.finished.connect(self.finish_action)
        self.tasks.busyChanged.connect(self.activity)
        self.timer = QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.refresh)
        operations.changed.connect(self.changed)

    @pyqtProperty("QVariantMap", notify=stateChanged)
    def state(self):
        return self._state

    @pyqtProperty(bool, notify=stateChanged)
    def statusKnown(self):
        return self._status_known

    @pyqtProperty(str, notify=changed)
    def error(self):
        return self._error

    @pyqtProperty(bool, notify=changed)
    def available(self):
        return bool(self._feature)

    @pyqtProperty(bool, notify=changed)
    def busy(self):
        return self.tasks.busy

    @pyqtProperty(bool, notify=changed)
    def working(self):
        return (
            self._reconciling
            or bool(self._pending_action)
            or (self.busy and self.tasks.action != "status-json")
        )

    @pyqtProperty(bool, notify=changed)
    def canChange(self):
        return (
            self.available
            and not self._stopped
            and not self.working
            and self.operations.allows(
                {"network", "packages", "reader"}, owner="sharing"
            )
        )

    @pyqtProperty(bool, notify=changed)
    def canStop(self):
        # Closing a session must remain possible during unrelated device work.
        return (
            self.available
            and not self._stopped
            and not self.working
            and self.operations.allows(set())
        )

    @pyqtProperty(str, notify=changed)
    def connectionType(self):
        return self._connection_type

    @pyqtSlot(str)
    def setConnectionType(self, value):
        if value in {"phone", "mac", "windows"} and value != self._connection_type:
            self._connection_type = value
            self.changed.emit()

    def set_catalog(self, features: list[PackageFeature], warning: str) -> None:
        self._warning = warning
        self._feature = next((f for f in features if f["kind"] == "file-sharing"), None)
        if not self.available:
            self.timer.stop()
            self._state = {}
            self._status_known = False
            self._pending_action = None
            self.stateChanged.emit()
            if self.navigation.page == "file-sharing":
                self.navigation.navigate("device")
        self.changed.emit()

    def select(self, feature: PackageFeature) -> None:
        self._feature = feature
        self.navigation.navigate("file-sharing")

    def enter(self):
        self.refresh()
        self.timer.start()

    def leave(self):
        self.timer.stop()
        self._pending_action = None
        self.activity()

    def stop(self):
        self._stopped = True
        self.leave()

    def close(self):
        self.stop()
        self.tasks.wait()

    def activity(self):
        action = self._pending_action or self.tasks.action
        changing = self.working
        operation = (
            Operation(
                resources=frozenset({"network", "packages", "reader"})
                if changing
                else frozenset(),
                working=changing,
                title="Stopping File Sharing…"
                if action == "stop"
                else "Starting File Sharing…",
                route="file-sharing",
            )
            if action or self._reconciling
            else None
        )
        self.operations.update("sharing", operation)
        self.changed.emit()

    def call(self, action: SharingAction):
        if not (self.canStop if action == "stop" else self.canChange):
            return
        if self.busy:
            self._pending_action = action
            self.activity()
        else:
            self._error = ""
            self._status_known = False
            self.stateChanged.emit()
            self.tasks.start(action, partial(self.service.call, action))

    def finish_action(self, _action):
        if self._stopped:
            self._needs_reconcile = False
            self._reconciling = False
            return
        if self._needs_reconcile:
            self._needs_reconcile = False
            self._reconciling = True
            self.tasks.start("status-json", partial(self.service.call, "status-json"))
        else:
            self._reconciling = False
            action, self._pending_action = self._pending_action, None
            if action == "stop" or (
                action == "start" and self._status_known and self._state.get("canStart")
            ):
                self.call(action)
        self.activity()

    @pyqtSlot()
    def refresh(self):
        if (
            self.available
            and not self._stopped
            and not self.busy
            and not self.working
            and not self.confirmations.active
            and self.operations.allows(set())
        ):
            self.tasks.start("status-json", partial(self.service.call, "status-json"))

    @pyqtSlot(str, object, object)
    def completed(
        self, action: str, state: SharingState | None, failure: TaskFailure | None
    ):
        known = failure is None and state is not None
        changed = self._status_known != known
        self._status_known = known
        if failure:
            self._error = failure.message
            self._needs_reconcile = action in {"start", "stop"}
        elif not self._reconciling:
            self._error = ""
        if state is not None and not failure and state != self._state:
            self._state = state
            changed = True
        if changed:
            self.stateChanged.emit()
        self.changed.emit()

    @pyqtSlot()
    def startSharing(self):
        if (
            self.canChange
            and self._status_known
            and not self._warning
            and self._state.get("canStart")
        ):
            self.call("start")

    @pyqtSlot()
    def stopSharing(self):
        if self.canStop and (not self._status_known or self._state.get("running")):
            self.confirmations.present(
                "sharing",
                ConfirmationContent(
                    title="Stop File Sharing?",
                    label="Stop sharing",
                    body="Connected computers will disconnect and unfinished transfers will stop. "
                    "USB file sharing stays disabled until the reader restarts.",
                    ready=True,
                ),
                partial(self.call, "stop"),
                lambda: (
                    self.canStop
                    and (not self._status_known or bool(self._state.get("running")))
                ),
            )
