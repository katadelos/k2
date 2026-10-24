"""Remote access page, polling and confirmed changes."""

from enum import Enum, auto
from functools import partial

from PyQt5.QtCore import QObject, QTimer, pyqtProperty, pyqtSignal, pyqtSlot

from ...core.packages import PackageFeature
from ...core.ports import RemoteAccessBackend
from ...ui.confirmations import ConfirmationContent, Confirmations
from ...ui.navigation import Navigation
from ...ui.operations import Operation, Operations
from ...ui.tasks import TaskRunner


class RemotePhase(Enum):
    IDLE = auto()
    READING = auto()
    CHANGING = auto()
    RECONCILING = auto()


class RemoteAccessViewModel(QObject):
    changed = pyqtSignal()
    featureChanged = pyqtSignal()
    stateChanged = pyqtSignal()
    transportChanged = pyqtSignal()
    errorChanged = pyqtSignal()
    activityChanged = pyqtSignal()
    availabilityChanged = pyqtSignal()
    settled = pyqtSignal()

    def __init__(
        self,
        service: RemoteAccessBackend,
        family: str,
        navigation: Navigation,
        operations: Operations,
        confirmations: Confirmations,
    ) -> None:
        super().__init__()
        self.service = service
        self.family = family
        self.navigation = navigation
        self.operations = operations
        self.confirmations = confirmations
        self._feature: PackageFeature | None = None
        self._features: list[PackageFeature] = []
        self._selected_id = ""
        self._state: dict = {}
        self._transport = "usb"
        self._maintenance_message = ""
        self._error = ""
        self._failed_action = ""
        self._pending_action = ""
        self._phase = RemotePhase.IDLE
        self._catalog_warning = ""
        self._tasks = TaskRunner(self)
        self._tasks.completed.connect(self._feature_result)
        self._tasks.finished.connect(self._feature_finished)
        self._tasks.busyChanged.connect(self._publish_activity)
        self._last_activity = (self.featureBusy, self.featureWorking)
        self._availability = (self.canRead, self.canChange)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(5000)
        self._poll_timer.timeout.connect(self.refreshFeature)
        operations.changed.connect(self._publish_availability)

    @pyqtProperty(bool, notify=availabilityChanged)
    def canRead(self):
        return self.operations.allows({"network"}, owner="remote")

    @pyqtProperty(bool, notify=availabilityChanged)
    def canChange(self):
        return not self.featureWorking and self.operations.allows(
            {"network", "packages", "reader"}, owner="remote"
        )

    @pyqtSlot()
    def _publish_availability(self):
        availability = (self.canRead, self.canChange)
        if availability != self._availability:
            self._availability = availability
            self.availabilityChanged.emit()

    def _sync_operation(self):
        operation = None
        if self.featureBusy or self.featureWorking:
            resources = (
                {"network", "packages", "reader"}
                if self.featureWorking
                else {"network"}
            )
            operation = Operation(
                resources=frozenset(resources),
                working=self.featureWorking,
                title="Changing developer tools…",
                route="feature",
            )
        self.operations.update("remote", operation)

    @pyqtSlot()
    def _publish_activity(self):
        self._sync_operation()
        self._publish_availability()
        activity = (self.featureBusy, self.featureWorking)
        if activity != self._last_activity:
            self._last_activity = activity
            self.activityChanged.emit()
            self.changed.emit()

    def _set_feature(self, feature: PackageFeature | None) -> None:
        if feature != self._feature:
            self._feature = feature.copy() if feature is not None else None
            self.featureChanged.emit()
            self.changed.emit()

    def _set_state(self, state):
        if state.get("kppMessage"):
            self._maintenance_message = state["kppMessage"]
        if state and self._maintenance_message:
            state = dict(state, kppMessage=self._maintenance_message)
        if state != self._state:
            self._state = state
            self.stateChanged.emit()
            self.changed.emit()

    def _set_error(self, error, action=""):
        self._failed_action = action
        if error != self._error:
            self._error = error
            self.errorChanged.emit()
            self.changed.emit()

    def _set_transport(self, transport):
        if transport != self._transport:
            self._transport = transport
            self.transportChanged.emit()
            self.changed.emit()

    def set_catalog(self, features: list[PackageFeature], warning: str) -> None:
        self._catalog_warning = warning
        remote_features = [item for item in features if item["kind"] == "remote-access"]
        if remote_features != self._features:
            self._features = remote_features
            self.featureChanged.emit()
        feature = next(
            (item for item in remote_features if item["id"] == self._selected_id), None
        )
        self._set_feature(feature)
        if not feature:
            self._poll_timer.stop()
            self._set_state({})
            if self.navigation.page == "feature":
                self.navigation.navigate("device")

    def select(self, feature: PackageFeature) -> None:
        if self.featureBusy and feature["id"] != self._selected_id:
            return
        same_page = self.navigation.page == "feature"
        self._selected_id = feature["id"]
        self._set_feature(feature)
        self._set_state({})
        self._set_error("")
        self._set_transport("wifi" if self.screenSharing else "usb")
        self.navigation.navigate("feature")
        if same_page:
            self.refreshFeature()

    def enter(self):
        self.refreshFeature()
        self._poll_timer.start()

    def leave(self):
        self._poll_timer.stop()
        self._pending_action = ""
        self._publish_activity()

    def _can_confirm_stop(self, selected_id):
        return (
            selected_id == self._selected_id
            and self.canChange
            and not self.featureBusy
            and bool(self._state.get("canStop"))
        )

    def _confirm_stop(self, selected_id):
        if self._can_confirm_stop(selected_id):
            self._feature_call("stop")

    def stop(self):
        self.leave()

    def close(self):
        self.stop()
        self._tasks.wait()

    @pyqtProperty("QVariantMap", notify=featureChanged)
    def feature(self):
        return self._feature or {}

    @pyqtProperty(bool, notify=featureChanged)
    def screenSharing(self):
        return self._feature is not None and self._feature["id"] == "k2-vnc"

    @pyqtProperty("QVariantList", notify=featureChanged)
    def featureOptions(self):
        return [
            {
                "id": item["id"],
                "title": "Screen" if item["id"] == "k2-vnc" else "Developer tools",
            }
            for item in sorted(self._features, key=lambda item: item["id"] == "k2-vnc")
        ]

    @pyqtSlot(str)
    def selectRemoteFeature(self, identifier):
        feature = next(
            (item for item in self._features if item["id"] == identifier), None
        )
        if feature and not self.featureBusy and not self.featureWorking:
            self.select(feature)

    @pyqtProperty("QVariantMap", notify=stateChanged)
    def featureState(self):
        return self._state

    @pyqtProperty(str, notify=errorChanged)
    def featureError(self):
        return self._error

    @pyqtProperty(str, notify=transportChanged)
    def featureTransport(self):
        return self._transport

    @pyqtSlot(str)
    def setFeatureTransport(self, transport):
        if (
            transport
            in ({"usb", "wifi"} if self.screenSharing else {"usb", "wifi", "both"})
            and not self.featureWorking
            and not self._state.get("ssh")
            and not self._state.get("running")
            and (transport == "wifi" or not self._state.get("adb"))
        ):
            self._set_transport(transport)

    @pyqtProperty(bool, notify=activityChanged)
    def featureBusy(self):
        return self._tasks.busy

    @pyqtProperty(bool, notify=activityChanged)
    def featureWorking(self):
        return bool(self._pending_action) or self._phase in {
            RemotePhase.CHANGING,
            RemotePhase.RECONCILING,
        }

    def _feature_call(self, action, phase=None):
        if self.featureBusy or not self.canRead or not self._feature:
            return False
        feature = self._feature.copy()
        if action == "status":
            call = partial(self.service.feature_status, feature)
            self._phase = phase or RemotePhase.READING
        else:
            self._set_error("")
            call = partial(self.service.change_feature, feature, action)
            self._phase = RemotePhase.CHANGING
        return self._tasks.start(action, call)

    @pyqtSlot(str, object, object)
    def _feature_result(self, action, result, failure):
        if failure is not None:
            self._set_error(failure.message, action)
            if action == "status":
                self._set_state({})
            return
        self._set_state(result)
        if result.get("ssh") or result.get("running"):
            if result["usbEnabled"] and result["wifiEnabled"]:
                transport = "both"
            elif result["wifiEnabled"]:
                transport = "wifi"
            else:
                transport = "usb"
            self._set_transport(transport)
        if self._failed_action == "status":
            self._set_error("")

    @pyqtSlot(str)
    def _feature_finished(self, action):
        if action != "status":
            # A failed transition may still have changed the USB interface.
            if not self._feature_call("status", phase=RemotePhase.RECONCILING):
                self._phase = RemotePhase.IDLE
        else:
            self._phase = RemotePhase.IDLE
            pending_action = self._pending_action
            self._pending_action = ""
            if pending_action:
                self.changeFeature(pending_action)
        self._publish_activity()
        if not self.featureBusy:
            self.settled.emit()

    @pyqtSlot()
    def refreshFeature(self):
        if self.navigation.page == "feature" and not self.confirmations.active:
            self._feature_call("status")

    def _stop_confirmation(self):
        if self.screenSharing:
            return ConfirmationContent(
                title="Stop screen sharing?",
                label="Stop sharing",
                body="Connected VNC viewers will disconnect.",
                ready=True,
            )
        ssh_running = self._state.get("ssh")
        usb_enabled = self._state.get("usbEnabled") or (
            self.family == "kobo" and self._state.get("owned")
        )
        if ssh_running:
            title = "Stop SSH access?"
            label = "Stop SSH"
            body = "Active Supernet SSH connections will close."
        else:
            title = "Clean up connection?"
            label = "Clean up"
            body = "Release the network resources left by Supernet."
        if usb_enabled:
            if self.family == "kindle":
                body += " USB network mode will stay enabled."
            else:
                body += " Supernet’s USB network connection will also close."
        return ConfirmationContent(title=title, label=label, body=body, ready=True)

    def _can_maintain(self, selected_id):
        return (
            selected_id == self._selected_id
            and self.canChange
            and not self.featureBusy
            and bool(self._state.get("kppAvailable"))
            and not self._state.get("kppBusy")
        )

    def _maintain(self, selected_id, action):
        if self._can_maintain(selected_id):
            self._maintenance_message = ""
            self._feature_call(action)

    @pyqtSlot(str)
    def changeFeature(self, action):
        if not self.canChange or self.confirmations.active:
            return
        if action in {"kpp-restart", "kpp-safe-mode", "kpp-export"}:
            selected_id = self._selected_id
            if not self._can_maintain(selected_id):
                return
            if action == "kpp-export":
                self._maintain(selected_id, action)
            else:
                safe = action == "kpp-safe-mode"
                self.confirmations.present(
                    "remote",
                    ConfirmationContent(
                        title="Disable optional extensions?"
                        if safe
                        else "Restart Kindle interface?",
                        label="Disable extensions" if safe else "Restart interface",
                        body=(
                            "All optional extensions will be disabled and the affected interface services restarted. "
                            "Extension settings are kept. Re-enable extensions individually in Extensions."
                            if safe
                            else "The Kindle interface will close and reopen. k2 stays open."
                        ),
                        ready=True,
                    ),
                    partial(self._maintain, selected_id, action),
                    partial(self._can_maintain, selected_id),
                )
            return
        developer_actions = {
            "adb-start": ("adbAvailable", "adb", False),
            "adb-stop": ("adbAvailable", "adb", True),
            "awake-on": ("keepAwakeAvailable", "keepAwake", False),
            "awake-off": ("keepAwakeAvailable", "keepAwake", True),
        }
        if action in developer_actions:
            capability, state_key, current = developer_actions[action]
            if action == "adb-start" and (
                self._state.get("adbError")
                or (self._state.get("ssh") and self._state.get("usbEnabled"))
            ):
                return
            if (
                self.screenSharing
                or self._catalog_warning
                or not self._state.get(capability)
            ):
                return
            if self._state.get(state_key) is not current:
                return
            if self.featureBusy:
                self._pending_action = action
                self._publish_activity()
            else:
                self._feature_call(action)
            return
        if action not in {"start", "stop"}:
            return
        if action == "start" and self._catalog_warning:
            return
        start_capabilities = {
            "usb": "canStartUsb",
            "wifi": "canStartWifi",
            "both": "canStartBoth",
        }
        capability = (
            ("canStart" if self.screenSharing else start_capabilities[self._transport])
            if action == "start"
            else "canStop"
        )
        if not self._state.get(capability):
            return
        if self.featureBusy:
            # Finish the status read and revalidate the user's intent against it.
            self._pending_action = action
            self._publish_activity()
            return
        if action == "stop":
            selected_id = self._selected_id
            self.confirmations.present(
                "remote",
                self._stop_confirmation(),
                partial(self._confirm_stop, selected_id),
                partial(self._can_confirm_stop, selected_id),
            )
        else:
            self._feature_call(
                "start" if self.screenSharing else "start-" + self._transport
            )
