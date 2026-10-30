"""Serialized access to the e-reader HAL shared by application workers."""

import errno
import os
from dataclasses import asdict
from threading import RLock
from typing import TYPE_CHECKING

from ..core.ports import BatteryState, CapabilityState, LightState, WifiStatus

if TYPE_CHECKING:
    from ereader_hal import Device as NativeDevice
    from ereader_hal import WifiConfig


def open_device() -> NativeDevice:
    """Open the HAL and lend stock light state when hardware has no readback."""
    from ereader_hal import Capability, Device

    device = Device()
    try:
        if os.environ.get("K2_STOCK_DISPLAY") == "nickel":
            state = device.get_capability(Capability.BRIGHTNESS)
            if (
                state.supported
                and not state.available
                and state.error
                in {
                    errno.ENOENT,
                    errno.ENODEV,
                    errno.ENOSYS,
                    errno.EOPNOTSUPP,
                }
            ):
                from .session import native_request

                def read() -> int:
                    return native_request("frontlight")["brightness"]

                def write(percent: int) -> None:
                    native_request("set_frontlight", brightness=percent)

                device.set_brightness_provider(read, write)
        return device
    except BaseException:
        device.close()
        raise


class Hardware:
    def __init__(self) -> None:
        self._hardware_lock = RLock()
        self._hardware: NativeDevice | None = None
        self._hardware_closed = False

    def _hal(self) -> NativeDevice:
        if self._hardware_closed:
            raise RuntimeError("Device is closed")
        if self._hardware is None:
            self._hardware = open_device()
        return self._hardware

    def close(self) -> None:
        with self._hardware_lock:
            if self._hardware is not None:
                self._hardware.close()
                self._hardware = None
            self._hardware_closed = True

    def capability(self, name: str) -> CapabilityState:
        from ereader_hal import Capability

        capability = Capability[name.upper().replace("-", "_")]
        with self._hardware_lock:
            value = self._hal().get_capability(capability)
            return {
                "supported": value.supported,
                "implemented": value.implemented,
                "available": value.available,
                "blocked": value.blocked,
                "error": value.error,
                "minimum": value.minimum,
                "maximum": value.maximum,
                "steps": value.steps,
                "reason_code": value.reason_code,
                "reason": value.reason,
            }

    def capabilities(self) -> dict[str, CapabilityState]:
        from ereader_hal import Capability

        with self._hardware_lock:
            return {
                cap.name.lower().replace("_", "-"): self.capability(cap.name)
                for cap in Capability
            }

    def _require_capability(self, name: str) -> None:
        state = self.capability(name)
        if not state["available"]:
            raise OSError(state["error"] or errno.ENOTSUP, state["reason"])

    @property
    def model(self) -> str:
        with self._hardware_lock:
            return self._hal().get_info().model

    def _light(self, name: str) -> LightState:
        with self._hardware_lock:
            state = self.capability(name)
            value = getattr(self._hal(), "get_" + name)() if state["available"] else 0
            return {**(state), "value": value, "minimum": 0, "maximum": 100}

    def _set_light(self, name: str, value: int) -> LightState:
        with self._hardware_lock:
            self._require_capability(name)
            getattr(self._hal(), "set_" + name)(max(0, min(100, int(value))))
            return self._light(name)

    def brightness(self) -> LightState:
        return self._light("brightness")

    def set_brightness(self, value: int) -> LightState:
        return self._set_light("brightness", value)

    def warmth(self) -> LightState:
        return self._light("warmth")

    def set_warmth(self, value: int) -> LightState:
        return self._set_light("warmth", value)

    def battery(self) -> BatteryState:
        from ereader_hal import ChargeState

        with self._hardware_lock:
            state = self.capability("battery")
            battery = self._hal().get_battery() if state["available"] else None
            return {
                **(state),
                "percent": battery.percent if battery else None,
                "charging": battery.state == ChargeState.CHARGING if battery else False,
            }

    def wifi(self) -> WifiStatus:
        from ereader_hal import WifiState

        with self._hardware_lock:
            state = self.capability("wifi")
            connection = self.capability("wifi-status")
            enabled = self._hal().get_wifi() if state["available"] else None
            if not connection["available"]:
                return {
                    **(state),
                    "enabled": enabled,
                    "connected": None,
                    "ssid": "",
                    "connection_available": False,
                    "connection_error": connection["error"],
                    "status": "Wi-Fi off"
                    if enabled is False
                    else "Connection status unavailable",
                    "detail": connection["reason"],
                }
            status = self._hal().get_wifi_status()
            labels = {
                WifiState.OFF: "Wi-Fi off",
                WifiState.DISCONNECTED: "Not connected",
                WifiState.CONNECTING: "Connecting",
                WifiState.CONNECTED: "Connected",
            }
            return {
                **(state),
                "enabled": status.state != WifiState.OFF,
                "connected": status.state == WifiState.CONNECTED,
                "ssid": status.ssid,
                "network_id": status.network_id,
                "address": status.address,
                "bssid": status.bssid,
                "connection_available": True,
                "connection_error": 0,
                "status": labels[status.state],
                "detail": status.ssid,
            }

    def wifi_list_networks(self) -> list[dict[str, object]]:
        with self._hardware_lock:
            return [asdict(network) for network in self._hal().wifi_list_networks()]

    def wifi_scan(self) -> list[dict[str, object]]:
        with self._hardware_lock:
            return [asdict(point) for point in self._hal().wifi_scan()]

    def wifi_capabilities(self) -> dict[str, object]:
        with self._hardware_lock:
            return asdict(self._hal().get_wifi_capabilities())

    def wifi_add_network(
        self, config: WifiConfig, timeout_ms: int = 5000
    ) -> dict[str, object]:
        with self._hardware_lock:
            return asdict(self._hal().wifi_add_network(config, timeout_ms=timeout_ms))

    def wifi_update_network(
        self, identifier: str, config: WifiConfig, timeout_ms: int = 5000
    ) -> dict[str, object]:
        with self._hardware_lock:
            return asdict(
                self._hal().wifi_update_network(
                    identifier, config, timeout_ms=timeout_ms
                )
            )

    def wifi_remove_network(
        self, identifier: str, timeout_ms: int = 5000
    ) -> dict[str, object]:
        with self._hardware_lock:
            return asdict(
                self._hal().wifi_remove_network(identifier, timeout_ms=timeout_ms)
            )

    def wifi_connect(
        self, identifier: str, wait_for_address: bool = True, timeout_ms: int = 30000
    ) -> dict[str, object]:
        with self._hardware_lock:
            return asdict(
                self._hal().wifi_connect(
                    identifier, wait_for_address=wait_for_address, timeout_ms=timeout_ms
                )
            )

    def wifi_disconnect(self, timeout_ms: int = 5000) -> dict[str, object]:
        with self._hardware_lock:
            return asdict(self._hal().wifi_disconnect(timeout_ms=timeout_ms))

    def set_wifi(self, enabled: bool) -> WifiStatus:
        with self._hardware_lock:
            self._require_capability("wifi")
            self._hal().set_wifi(bool(enabled))
            return self.wifi()
