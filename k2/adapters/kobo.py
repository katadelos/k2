"""Kobo controls coordinated with the stock firmware."""

from ..core.ports import WifiStatus
from .device import Device
from .session import native_request


class KoboDevice(Device):
    def __init__(self) -> None:
        super().__init__("kobo")

    @staticmethod
    def _wifi_request(command: str, **values: bool) -> WifiStatus:
        # Nickel owns the supplicant and reconnect workflow during a K2 session.
        # Toggling the radio directly leaves that workflow out of sync.
        result = native_request(command, **values)
        enabled = bool(result["enabled"])
        connected = enabled and bool(result["connected"])
        ssid = result["ssid"] if connected else ""
        return {
            "available": True,
            "enabled": enabled,
            "connected": connected,
            "connection_available": True,
            "connection_error": 0,
            "ssid": ssid,
            "status": "Wi-Fi off"
            if not enabled
            else "Connected"
            if connected
            else "Not connected",
            "detail": ssid,
        }

    def wifi(self) -> WifiStatus:
        return self._wifi_request("wifi")

    def set_wifi(self, enabled: bool) -> WifiStatus:
        return self._wifi_request("set_wifi", enabled=bool(enabled))
