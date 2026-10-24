"""Device composition: stock firmware plus the existing SDK bootstrap."""

import os
import platform
import shutil
import socket
import sys
from pathlib import Path

from ..core.ports import DeviceInfo, Feed
from .hardware import Hardware


def read(path: str | Path) -> str:
    try:
        return Path(path).read_text(errors="replace").strip()
    except OSError:
        return ""


def gib(value: int) -> str:
    return f"{value / 1024**3:.1f} GB"


class Device(Hardware):
    def __init__(self, family: str) -> None:
        super().__init__()
        self.family = family
        self.store = Path("/mnt/onboard" if family == "kobo" else "/mnt/us")
        self.sdk = self.store / ".eink-sdk"

    def network_available(self) -> bool:
        from PyQt5.QtNetwork import QAbstractSocket, QNetworkInterface

        # Check local link/address state, including USB networking, without
        # waking Wi-Fi or probing an unrelated internet service.
        required = QNetworkInterface.IsUp | QNetworkInterface.IsRunning
        for interface in QNetworkInterface.allInterfaces():
            flags = interface.flags()
            if flags & required != required or flags & QNetworkInterface.IsLoopBack:
                continue
            for entry in interface.addressEntries():
                address = entry.ip()
                if address.isGlobal() or (
                    address.protocol() == QAbstractSocket.IPv4Protocol
                    and address.isLinkLocal()
                ):
                    return True
        return False

    def set_active(self, active: bool) -> None:
        directory = os.environ.get("K2_SESSION_DIR")
        if directory:
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as control:
                    control.setblocking(False)
                    control.sendto(
                        b"active" if active else b"inactive",
                        str(Path(directory) / "control"),
                    )
            except OSError:
                # Never let a Python exception escape a Qt signal callback.
                # The UI cannot safely retain display ownership without its lease.
                from PyQt5.QtCore import QCoreApplication

                print(
                    "k2: the device session ended; closing the interface.",
                    file=sys.stderr,
                )
                QCoreApplication.exit(1)

    def snapshot(self) -> DeviceInfo:
        disk = shutil.disk_usage(self.store)
        firmware = (
            read("/mnt/onboard/.kobo/version")
            if self.family == "kobo"
            else read("/etc/prettyversion.txt")
        )
        battery_state = self.battery()
        battery = (
            f"{battery_state['percent']}%"
            if battery_state["available"]
            else "Unavailable"
        )
        feeds: list[Feed] = []
        for config in sorted((self.sdk / "opkg").glob("*.conf")):
            for line in read(config).splitlines():
                fields = line.split()
                if len(fields) >= 3 and fields[0] in {"src", "src/gz"}:
                    feeds.append({"name": fields[1], "url": fields[2]})
        return {
            "family": self.family,
            "model": self.model,
            "firmware": firmware or "Unavailable",
            "kernel": platform.release(),
            "architecture": platform.machine(),
            "battery": battery,
            "free": gib(disk.free),
            "total": gib(disk.total),
            "usedFraction": disk.used / disk.total,
            "store": str(self.store),
            "sdk": str(self.sdk),
            "feeds": feeds,
            "launcher": "k2 bottom rail button"
            if self.family == "kobo"
            else "k2 library scriptlet",
        }


def create_device(family: str) -> Device:
    if family == "kindle":
        from .kindle import KindleDevice

        return KindleDevice()
    if family == "kobo":
        from .kobo import KoboDevice

        return KoboDevice()
    raise ValueError("Unsupported device family: " + family)
