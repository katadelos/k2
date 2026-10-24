import time
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

from ...core.packages import Application, CatalogPackage, FeatureCatalog, PackageFeature
from ...core.ports import (
    BatteryState,
    CapabilityState,
    DeviceInfo,
    LightState,
    WifiStatus,
)

if TYPE_CHECKING:
    from ...features.koreader.ports import PluginBackend
    from .customise import SimulatedCustomiseManager
    from .manager import SimulatedKOReaderManager

from ..scenarios import PROFILES


class SimulatedDevice:
    def __init__(self, profile: str, scenario: str = "normal") -> None:
        self.profile = profile
        self.family = PROFILES[profile][3]
        self.scenario = scenario
        self.light = 75 if profile == "pw5" else 60
        self.warm_light = 0
        self.wireless = True
        self.launched: list[str] = []
        self.kpp_message = ""
        self.supernet_mode = "other"
        self.supernet_adb = False
        self.supernet_awake = False
        self.supernet_network = False
        self.supernet_ssh = False
        self.supernet_usb = False
        self.supernet_wifi = False
        self.supernet_keys = scenario != "supernet-setup"
        self._customise_managers: dict[str, SimulatedCustomiseManager] = {}

    def capability(self, name: str) -> CapabilityState:
        supported = name in {"brightness", "warmth", "wifi", "battery"}
        return {
            "supported": supported,
            "implemented": supported,
            "available": supported,
            "blocked": False,
            "error": 0 if supported else 95,
            "minimum": 0,
            "maximum": 100 if name in {"brightness", "warmth", "battery"} else 0,
            "steps": 101 if name in {"brightness", "warmth"} else 0,
            "reason": "" if supported else "Not supported by the simulator",
        }

    def capabilities(self) -> dict[str, CapabilityState]:
        return {
            name: self.capability(name)
            for name in ("brightness", "warmth", "wifi", "battery")
        }

    def close(self) -> None:
        pass

    def brightness(self) -> LightState:
        return {**(self.capability("brightness")), "value": self.light}

    def set_brightness(self, value: int) -> LightState:
        self.light = max(0, min(100, int(value)))
        return self.brightness()

    def warmth(self) -> LightState:
        return {**(self.capability("warmth")), "value": self.warm_light}

    def set_warmth(self, value: int) -> LightState:
        self.warm_light = max(0, min(100, int(value)))
        return self.warmth()

    def battery(self) -> BatteryState:
        return {**(self.capability("battery")), "percent": 85, "charging": False}

    def wifi(self) -> WifiStatus:
        return {
            **(self.capability("wifi")),
            "enabled": self.wireless,
            "connected": self.wireless,
            "ssid": "Home network" if self.wireless else "",
            "status": "Connected" if self.wireless else "Wi-Fi off",
            "detail": "",
        }

    def set_wifi(self, enabled: bool) -> WifiStatus:
        self.wireless = bool(enabled)
        return self.wifi()

    def network_available(self) -> bool:
        return self.wireless and self.scenario != "offline"

    def application(self, package: CatalogPackage, files: list[str]) -> Application:
        name = package["name"]
        installed = bool(package["installed"])
        if name == "k2-home" and installed and package.get("configured"):
            return {
                "name": "Home Assistant",
                "instructions": "Open Home Assistant from the cog menu or Device.",
                "argv": ["/usr/bin/k2-home"],
                "canOpen": True,
                "commands": ["k2-home"],
                "error": "",
            }
        return {
            "name": name,
            "instructions": ("Open a terminal and run: " + name)
            if installed and name in {"htop", "nano", "curl", "rsync"}
            else "No launch instructions are included with this package.",
            "argv": [],
            "canOpen": False,
            "commands": [],
            "error": "",
        }

    def launch_application(self, argv: list[str]) -> None:
        self.launched = list(argv)

    def koreader_manager(self) -> SimulatedKOReaderManager:
        from .manager import SimulatedKOReaderManager

        return SimulatedKOReaderManager(self)

    def koreader_plugins(self, root: str) -> PluginBackend:
        return self.koreader_customise(root).backend

    def koreader_customise(self, root: str) -> SimulatedCustomiseManager:
        from .customise import SimulatedCustomiseManager

        if root not in self._customise_managers:
            self._customise_managers[root] = SimulatedCustomiseManager(
                root, dict(self.snapshot(), scenario=self.scenario)
            )
        return self._customise_managers[root]

    def koreader_preview(self, item_id: str) -> str:
        import tempfile
        from pathlib import Path

        from ...features.koreader.previews import load_preview

        return load_preview(
            item_id,
            Path(tempfile.gettempdir()) / "k2-simulator-previews",
            offline=self.scenario in {"offline", "koreader-offline"},
        )

    def launch_koreader(self, argv: list[str]) -> None:
        self.launched = list(argv)

    def set_active(self, active: bool) -> None:
        self.active = active

    def features(
        self,
        catalog: Sequence[CatalogPackage],
        package_files: Callable[[str], list[str]],
    ) -> FeatureCatalog:
        installed = {
            p["name"] for p in catalog if p.get("installed") and p.get("configured")
        }
        items: list[PackageFeature] = []
        if "supernet" in installed:
            items.append(
                {
                    "id": "supernet",
                    "package": "supernet",
                    "kind": "remote-access",
                    "title": "Developer tools",
                    "description": "Manage SSH, USB debugging and wake settings.",
                    "popover": {"icon": "terminal", "order": 50},
                    "executable": "/usr/bin/supernet",
                }
            )
        if "k2-home" in installed:
            items.append(
                {
                    "id": "k2-home",
                    "package": "k2-home",
                    "kind": "application",
                    "title": "Home Assistant",
                    "description": "Control your home and view its sensors.",
                    "popover": {"icon": "home", "order": 40},
                    "executable": "/usr/bin/k2-home",
                }
            )
        return {"items": items, "errors": []}

    def feature_status(self, feature: PackageFeature) -> dict[str, Any]:
        ready = self.supernet_keys and not self.supernet_ssh
        wifi_lost = self.supernet_wifi and not self.wireless
        return {
            "schema": 1,
            "kppAvailable": self.family == "kindle",
            "kppBusy": False,
            "kppErrors": [],
            "kppError": "",
            "kppMessage": self.kpp_message,
            "hostname": "kindle" if self.family == "kindle" else "kobo",
            "usbMode": self.supernet_mode,
            "adbAvailable": self.family == "kindle",
            "adb": self.supernet_adb,
            "adbError": "Stop USB SSH before enabling ADB."
            if self.supernet_usb and self.supernet_ssh
            else "",
            "keepAwakeAvailable": True,
            "keepAwake": self.supernet_awake,
            "network": self.supernet_network,
            "ssh": self.supernet_ssh,
            "owned": self.supernet_network,
            "usbEnabled": self.supernet_usb,
            "wifiEnabled": self.supernet_wifi,
            "wifiAvailable": self.wireless,
            "wifiAddress": "192.168.1.42"
            if self.wireless or self.supernet_wifi
            else "",
            "canStartUsb": ready and not self.supernet_adb,
            "canStartWifi": ready and self.wireless,
            "canStartBoth": ready and self.wireless and not self.supernet_adb,
            "keysReady": self.supernet_keys,
            "keyPath": self.snapshot()["sdk"] + "/etc/supernet/authorized_keys",
            "address": "192.168.15.244",
            "prefix": 24,
            "port": 22,
            "hostAddress": "192.168.15.201/24",
            "canStart": ready,
            "canStop": self.supernet_ssh
            or (self.profile == "elipsa" and self.supernet_network),
            "detail": (
                "USB network mode stays enabled after SSH stops; reboot to restore file transfer mode."
                if self.profile == "pw5"
                else "Stopping SSH also releases the USB network connection created by Supernet."
            )
            if self.supernet_network
            else (
                "SSH accepts public-key connections over Wi-Fi."
                if self.supernet_ssh
                else "Start SSH only when you want to connect from another device."
            ),
            "usbError": "Stop ADB before enabling USB SSH."
            if self.supernet_adb
            else "",
            "wifiError": ""
            if self.wireless
            else "Connect to Wi-Fi in the reader’s stock settings first.",
            "error": "Wi-Fi disconnected. Stop and restart SSH after reconnecting."
            if wifi_lost
            else "",
        }

    def change_feature(self, feature: PackageFeature, action: str) -> dict[str, Any]:
        time.sleep(0.2)
        if action in {"start-usb", "start-wifi", "start-both"}:
            if self.supernet_adb and action in {"start-usb", "start-both"}:
                raise OSError("Stop ADB before enabling USB SSH.")
            if not self.supernet_keys:
                raise OSError("Add an SSH public key before starting Supernet.")
            if action in {"start-wifi", "start-both"} and not self.wireless:
                raise OSError("Connect to Wi-Fi in the reader’s stock settings first.")
            self.supernet_usb = action in {"start-usb", "start-both"}
            if self.supernet_usb:
                self.supernet_mode = "network"
            self.supernet_wifi = action in {"start-wifi", "start-both"}
            self.supernet_network = self.supernet_network or self.supernet_usb
            self.supernet_ssh = True
        elif (
            action in {"kpp-restart", "kpp-safe-mode", "kpp-export"}
            and self.family == "kindle"
        ):
            self.kpp_message = {
                "kpp-restart": "Kindle interface restarted.",
                "kpp-safe-mode": "Optional extensions are disabled. Re-enable them in Extensions.",
                "kpp-export": "Simulator diagnostics export; no device files were written.",
            }[action]
        elif action in {"adb-start", "adb-stop"} and self.family == "kindle":
            if action == "adb-start" and self.supernet_usb and self.supernet_ssh:
                raise OSError("Stop USB SSH before enabling ADB.")
            self.supernet_adb = action == "adb-start"
            if self.supernet_adb:
                self.supernet_mode = "adb"
        elif action in {"awake-on", "awake-off"}:
            self.supernet_awake = action == "awake-on"
        elif action == "stop":
            self.supernet_ssh = False
            self.supernet_network = self.profile == "pw5" and self.supernet_network
            self.supernet_usb = self.supernet_wifi = False
        else:
            raise ValueError("Unsupported device tool action.")
        return self.feature_status(feature)

    def snapshot(self) -> DeviceInfo:
        _, _, model, family = PROFILES[self.profile]
        store = "/mnt/us" if family == "kindle" else "/mnt/onboard"
        return {
            "model": model,
            "family": family,
            "firmware": "Simulated firmware",
            "kernel": "Simulated kernel",
            "architecture": "armv7l",
            "battery": "85%",
            "free": "5.2 GB",
            "total": "28.8 GB",
            "usedFraction": 0.819,
            "store": store,
            "sdk": store + "/.eink-sdk",
            "feeds": [{"name": "Simulator", "url": "Local sample catalog"}],
            "launcher": "k2 bottom rail button"
            if family == "kobo"
            else "k2 library scriptlet",
        }
