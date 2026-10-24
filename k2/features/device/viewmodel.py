"""Device information and asynchronous brightness/Wi-Fi controls."""

from collections.abc import Callable
from functools import partial
from typing import cast

from PyQt5.QtCore import QObject, QTimer, pyqtProperty, pyqtSignal, pyqtSlot

from ...core.ports import DeviceBackend, DeviceInfo, LightState, WifiStatus
from ...ui.operations import Operation, Operations
from ...ui.tasks import TaskFailure, TaskRunner

type ControlValue = DeviceInfo | LightState | WifiStatus


def pending_device_info(family: str) -> DeviceInfo:
    """Stable QML fields before the first background device snapshot arrives."""
    return {
        "family": family,
        "model": "Kindle" if family == "kindle" else "Kobo",
        "firmware": "Reading…",
        "kernel": "Reading…",
        "architecture": "Reading…",
        "battery": "Reading…",
        "free": "Reading…",
        "total": "Reading…",
        "usedFraction": 0.0,
        "store": "",
        "sdk": "",
        "feeds": [],
        "launcher": "Reading…",
    }


class DeviceViewModel(QObject):
    changed = pyqtSignal()
    controlsOpenChanged = pyqtSignal()
    brightnessChanged = pyqtSignal()
    wifiChanged = pyqtSignal()
    errorChanged = pyqtSignal()
    activityChanged = pyqtSignal()
    infoChanged = pyqtSignal()
    infoStatusChanged = pyqtSignal()
    availabilityChanged = pyqtSignal()
    opened = pyqtSignal()

    def __init__(self, device: DeviceBackend, operations: Operations) -> None:
        super().__init__()
        self.device = device
        self.operations = operations
        self._controls_open = False
        self._stopped = False
        self._brightness: LightState = {"available": False, "value": 0, "maximum": 100}
        self._control_error = ""
        self._wifi: WifiStatus = {
            "available": False,
            "enabled": False,
            "connected": False,
            "ssid": "",
            "status": "Checking Wi-Fi…",
            "detail": "",
        }
        self._tasks = TaskRunner(self)
        self._tasks.completed.connect(self._control_result)
        self._tasks.finished.connect(self._control_finished)
        self._tasks.busyChanged.connect(self._publish_activity)
        self._pending_controls: dict[str, Callable[[], ControlValue]] = {}
        self._info = pending_device_info(device.family)
        self._info_error = ""
        self._info_status = (False, "")
        self._last_activity = self._activity_state()
        self._can_change_wifi = self.canChangeWifi
        self._controls_timer = QTimer(self)
        self._controls_timer.setInterval(5000)
        self._controls_timer.timeout.connect(self._refresh_controls)
        operations.changed.connect(self._publish_availability)
        # Opening the menu only presents cached state; hardware reads run in the background.
        self.refreshInfo()
        self._refresh_controls()
        self._controls_timer.start()

    @pyqtProperty(bool, notify=availabilityChanged)
    def canChangeWifi(self) -> bool:
        return not self._stopped and self.operations.allows(
            {"network", "controls"}, owner="controls"
        )

    @pyqtSlot()
    def _publish_availability(self) -> None:
        available = self.canChangeWifi
        if available != self._can_change_wifi:
            self._can_change_wifi = available
            self.availabilityChanged.emit()

    def _sync_operation(self) -> None:
        operation = None
        if self.controlsBusy:
            resources = set()
            if self.wifiChanging:
                resources = {"controls", "network"}
            elif self.brightnessChanging:
                resources = {"controls"}
            # Status reads stay tracked for shutdown without blocking actions.
            operation = Operation(
                resources=frozenset(resources),
                working=self.wifiChanging,
                title="Changing Wi-Fi…",
                route="device",
            )
        self.operations.update("controls", operation)

    def _activity_state(self) -> tuple[bool, bool, bool, bool]:
        return (
            self.controlsBusy,
            self.controlsChanging,
            self.brightnessChanging,
            self.wifiChanging,
        )

    @pyqtSlot()
    def _publish_activity(self) -> None:
        self._sync_operation()
        info_status = self.infoLoading, self._info_error
        if info_status != self._info_status:
            self._info_status = info_status
            self.infoStatusChanged.emit()
            self.changed.emit()
        activity = self._activity_state()
        if activity != self._last_activity:
            self._last_activity = activity
            self.activityChanged.emit()
            self.changed.emit()

    def _set_error(self, error: str) -> None:
        if error != self._control_error:
            self._control_error = error
            self.errorChanged.emit()
            self.changed.emit()

    def _set_brightness(self, brightness: LightState) -> None:
        if brightness != self._brightness:
            self._brightness = brightness
            self.brightnessChanged.emit()
            self.changed.emit()

    @pyqtSlot()
    def refreshInfo(self) -> None:
        self._control("info", self.device.snapshot, queue=True)

    @pyqtProperty(bool, notify=infoStatusChanged)
    def infoLoading(self) -> bool:
        return self._tasks.action == "info" or "info" in self._pending_controls

    @pyqtProperty(str, notify=infoStatusChanged)
    def infoError(self) -> str:
        return self._info_error

    def stop(self) -> None:
        self._stopped = True
        self._controls_timer.stop()
        self._pending_controls = {
            action: call
            for action, call in self._pending_controls.items()
            if action.endswith("-set")
        }
        self.closeControls()
        self._publish_availability()
        self._publish_activity()

    def close(self) -> None:
        self.stop()
        self._tasks.wait()

    @pyqtProperty(bool, notify=controlsOpenChanged)
    def controlsOpen(self) -> bool:
        return self._controls_open

    @pyqtProperty("QVariantMap", notify=brightnessChanged)
    def brightness(self) -> LightState:
        return self._brightness

    @pyqtProperty(str, notify=errorChanged)
    def controlError(self) -> str:
        return self._control_error

    @pyqtProperty("QVariantMap", notify=wifiChanged)
    def wifi(self) -> WifiStatus:
        return self._wifi

    @pyqtProperty(bool, notify=activityChanged)
    def controlsBusy(self) -> bool:
        return self._tasks.busy or bool(self._pending_controls)

    @pyqtProperty(bool, notify=activityChanged)
    def controlsChanging(self) -> bool:
        return self.brightnessChanging or self.wifiChanging

    @pyqtProperty(bool, notify=activityChanged)
    def brightnessChanging(self) -> bool:
        return (
            "brightness-set" in self._pending_controls
            or self._tasks.action == "brightness-set"
        )

    @pyqtProperty(bool, notify=activityChanged)
    def wifiChanging(self) -> bool:
        return "wifi-set" in self._pending_controls or self._tasks.action == "wifi-set"

    def _control(
        self,
        action: str,
        call: Callable[[], ControlValue],
        reset_error: bool = False,
        queue: bool = False,
    ) -> None:
        if (self._stopped or self.operations.stopping) and not action.endswith("-set"):
            return
        if self._tasks.busy:
            if reset_error or (queue and action != self._tasks.action):
                self._pending_controls[action] = call
                self._publish_activity()
            return
        if reset_error:
            self._set_error("")
        self._tasks.start(action, call)

    @pyqtSlot(str, object, object)
    def _control_result(
        self, action: str, result: object, failure: TaskFailure | None
    ) -> None:
        if action == "info":
            self._info_error = failure.message if failure else ""
            if failure is None and result != self._info:
                self._info = cast(DeviceInfo, result)
                self.infoChanged.emit()
                self.changed.emit()
        elif failure is not None:
            self._set_error(failure.message)
            if (
                action == "brightness-set"
                and "brightness-set" not in self._pending_controls
                and not self._stopped
                and not self.operations.stopping
            ):
                self._pending_controls["brightness"] = self.device.brightness
        elif action.startswith("brightness"):
            # A completed write can precede a newer queued slider position.
            # Keep the latest requested value until that write completes.
            brightness = cast(LightState, result).copy()
            if "brightness-set" in self._pending_controls:
                brightness["value"] = self._brightness["value"]
            self._set_brightness(brightness)
        elif result != self._wifi:
            self._wifi = cast(WifiStatus, result).copy()
            self.wifiChanged.emit()
            self.changed.emit()
        self._publish_activity()

    @pyqtSlot(str)
    def _control_finished(self, action: str) -> None:
        while self._pending_controls and not self._tasks.busy:
            next_action = next(iter(self._pending_controls))
            call = self._pending_controls.pop(next_action)
            self._control(next_action, call, reset_error=next_action.endswith("-set"))

    @pyqtSlot()
    def _refresh_controls(self) -> None:
        self._control("brightness", self.device.brightness, queue=True)
        self._control("wifi", self.device.wifi, queue=True)

    @pyqtSlot()
    def toggleControls(self) -> None:
        if self._controls_open:
            self.closeControls()
            return
        self._controls_open = True
        self.opened.emit()
        self.controlsOpenChanged.emit()
        self.changed.emit()

    @pyqtSlot()
    def closeControls(self) -> None:
        if self._controls_open:
            self._controls_open = False
            self.controlsOpenChanged.emit()
            self.changed.emit()

    @pyqtSlot(bool)
    def setWifi(self, enabled: bool) -> None:
        if self.canChangeWifi:
            self._control(
                "wifi-set", partial(self.device.set_wifi, enabled), reset_error=True
            )

    @pyqtSlot(int)
    def setBrightness(self, value: int) -> None:
        if self._stopped or self.operations.stopping:
            return
        value = max(0, min(self._brightness.get("maximum", 100), value))
        if value == self._brightness["value"]:
            return
        brightness = self._brightness.copy()
        brightness["value"] = value
        self._set_brightness(brightness)
        self._control(
            "brightness-set",
            partial(self.device.set_brightness, value),
            reset_error=True,
        )

    @pyqtProperty("QVariantMap", notify=infoChanged)
    def info(self) -> DeviceInfo:
        return self._info
