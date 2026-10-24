"""Kindle controls through the e-reader HAL."""

import time

from ..core.ports import WifiStatus
from .device import Device


class KindleDevice(Device):
    def __init__(self) -> None:
        super().__init__("kindle")

    def set_wifi(self, enabled: bool) -> WifiStatus:
        enabled = bool(enabled)
        with self._hardware_lock:
            self._require_capability("wifi")
            self._hal().set_wifi(enabled)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if self._hal().get_wifi() == enabled:
                    return self.wifi()
                time.sleep(0.15)
        raise OSError("Wi-Fi did not finish switching.")
