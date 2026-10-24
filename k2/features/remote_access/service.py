"""Supernet command protocol and status validation."""

import ipaddress
import json
import subprocess
from pathlib import Path
from typing import Any

from ...core.packages import PackageFeature
from . import kpp_tools


def feature_status(executable: Path) -> dict[str, Any]:
    result = subprocess.run(  # noqa: S603 -- package-owned executable and validated action; no shell
        [str(executable), "status-json"], capture_output=True, text=True, timeout=8
    )
    if result.returncode:
        raise OSError(
            result.stderr.strip()[-1024:] or "Could not read remote access status."
        )
    try:
        state = json.loads(result.stdout)
        if not isinstance(state, dict) or state.get("schema") != 1:
            raise ValueError("unsupported status format")
        for key in (
            "network",
            "ssh",
            "keysReady",
            "canStop",
            "usbEnabled",
            "wifiEnabled",
            "wifiAvailable",
            "canStartUsb",
            "canStartWifi",
            "canStartBoth",
            "adbAvailable",
            "adb",
            "keepAwakeAvailable",
            "keepAwake",
        ):
            if not isinstance(state.get(key), bool):
                raise ValueError("invalid " + key)
        for key in (
            "keyPath",
            "address",
            "detail",
            "error",
            "wifiAddress",
            "usbError",
            "wifiError",
            "hostname",
            "adbError",
            "usbMode",
        ):
            if not isinstance(state.get(key), str):
                raise ValueError("invalid " + key)
        if state["usbMode"] not in {"adb", "network", "other"}:
            raise ValueError("invalid USB mode")
        if type(state.get("prefix")) is not int or not 1 <= state["prefix"] <= 30:
            raise ValueError("invalid address prefix")
        if type(state.get("port")) is not int or not 1 <= state["port"] <= 65535:
            raise ValueError("invalid SSH port")
        interface = ipaddress.IPv4Interface(f"{state['address']}/{state['prefix']}")
        host = ipaddress.IPv4Address("192.168.15.201")
        if (
            host not in interface.network
            or host == interface.ip
            or host
            in {interface.network.network_address, interface.network.broadcast_address}
        ):
            host = interface.network.network_address + (
                2 if interface.ip == interface.network.network_address + 1 else 1
            )
        state["hostAddress"] = f"{host}/{state['prefix']}"
        return state
    except (ValueError, TypeError) as error:
        raise OSError(
            "The installed device tool returned an invalid status."
        ) from error


def _change_error(result: subprocess.CompletedProcess[str], action: str) -> str:
    details = (
        line.removeprefix(f"ERROR {action}: ").removeprefix("ERROR ")
        for line in result.stderr.strip().splitlines()
    )
    return "\n".join(details)[-1024:] or ("Remote access could not be changed.")


def change_feature(executable: Path, action: str) -> None:
    if action not in {
        "start-usb",
        "start-wifi",
        "start-both",
        "stop",
        "adb-start",
        "adb-stop",
        "awake-on",
        "awake-off",
    }:
        raise ValueError("Unsupported device tool action.")
    result = subprocess.run(  # noqa: S603 -- package-owned executable and validated action; no shell
        [str(executable), action], capture_output=True, text=True, timeout=90
    )
    if result.returncode:
        raise OSError(_change_error(result, action))


class RemoteAccessService:
    def __init__(self, family: str) -> None:
        self.family = family

    def _executable(self, feature: PackageFeature) -> Path:
        executable = Path("/var/run/eink-sdk") / feature["executable"].lstrip("/")
        if not executable.is_file():
            raise OSError(
                "This device tool's executable is unavailable. Reinstall its package."
            )
        return executable

    def feature_status(self, feature: PackageFeature) -> dict[str, Any]:
        if feature["id"] == "k2-vnc":
            return self._screen_call(feature, "status-json")
        state = feature_status(self._executable(feature))
        if self.family == "kindle":
            state.update(kpp_tools.status())
        return state

    def change_feature(self, feature: PackageFeature, action: str) -> dict[str, Any]:
        if feature["id"] == "k2-vnc":
            if action not in {"start", "stop"}:
                raise ValueError("Unsupported screen-sharing action.")
            return self._screen_call(feature, action)
        if action in {"kpp-restart", "kpp-safe-mode", "kpp-export"}:
            if self.family != "kindle":
                raise ValueError("KPP maintenance is only available on Kindle.")
            message = kpp_tools.change(action)
            return dict(self.feature_status(feature), kppMessage=message)
        change_feature(self._executable(feature), action)
        return self.feature_status(feature)

    def _screen_call(self, feature: PackageFeature, action: str) -> dict[str, Any]:
        result = subprocess.run(  # noqa: S603 -- package-owned executable and validated action; no shell
            [str(self._executable(feature)), action],
            capture_output=True,
            text=True,
            timeout=40,
        )
        if result.returncode:
            raise OSError(
                result.stderr.strip()[-1024:] or "Screen sharing could not be changed."
            )
        try:
            state = json.loads(result.stdout)
            if not isinstance(state, dict) or state.get("schema") != 1:
                raise ValueError("unsupported status format")
            for key in ("running", "canStop", "usbEnabled", "wifiEnabled", "canStart"):
                if type(state.get(key)) is not bool:
                    raise ValueError("invalid " + key)
            for key in (
                "address",
                "usbAddress",
                "wifiAddress",
                "password",
                "detail",
                "error",
            ):
                if not isinstance(state.get(key), str):
                    raise ValueError("invalid " + key)
            if type(state.get("port")) is not int or not 1 <= state["port"] <= 65535:
                raise ValueError("invalid VNC port")
            return state
        except (ValueError, TypeError) as error:
            raise OSError(
                "The screen-sharing tool returned an invalid status."
            ) from error
