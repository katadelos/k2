import time
from collections.abc import Sequence
from typing import TYPE_CHECKING

from ...features.koreader.manager import VARIANT_LABELS

if TYPE_CHECKING:
    from .device import SimulatedDevice


class SimulatedKOReaderManager:
    def __init__(self, device: SimulatedDevice) -> None:
        self.device = device
        info = device.snapshot()
        self.variant = "kindlehf" if info["family"] == "kindle" else "kobo"
        self.path = info["store"] + (
            "/koreader" if info["family"] == "kindle" else "/.adds/koreader"
        )
        scenario = device.scenario
        self.installed = scenario in {
            "koreader-installed",
            "koreader-conflict",
            "koreader-offline",
        }
        self.conflict = scenario == "koreader-conflict"
        self.version = "v2026.03" if self.installed else ""
        self.release = ""
        self.checked = 0
        self.scriptlet = ""

    def status(self) -> dict:
        paths = (
            [{"path": self.path, "version": self.version, "complete": True}]
            if self.installed
            else []
        )
        if self.conflict:
            paths.append(
                {
                    "path": self.path.replace("/.adds/", "/")
                    if "/.adds/" in self.path
                    else self.path.replace("/koreader", "/.adds/koreader"),
                    "version": "v2025.10",
                    "complete": True,
                }
            )
        return {
            "installed": self.installed,
            "complete": self.installed,
            "path": "" if self.conflict else self.path,
            "version": self.version,
            "variant": self.variant,
            "variantLabel": VARIANT_LABELS[self.variant],
            "supported": True,
            "reason": "More than one KOReader installation was found. Choose the copy to manage."
            if self.conflict
            else "",
            "releaseVersion": self.release,
            "updateAvailable": self.installed
            and bool(self.release)
            and self.version != self.release,
            "newerInstalled": False,
            "running": False,
            "canInstall": bool(self.release) and not self.conflict,
            "canOpen": self.installed and not self.conflict,
            "installations": paths,
            "lastChecked": self.checked,
            "identity": [1, 1, 0, 0, 0] if self.installed else [],
            "canRemove": self.installed and not self.conflict,
            "canAddScriptlet": self.installed
            and not self.conflict
            and self.device.family == "kindle",
            "scriptletInstalled": self.scriptlet == self.path,
            "detail": "",
        }

    def check_release(self) -> dict:
        if self.device.scenario in {"offline", "koreader-offline"}:
            raise OSError(
                "Could not contact KOReader's release server. Check Wi-Fi and try again."
            )
        self.release, self.checked = "v2026.07.1", int(time.time())
        return self.status()

    def select_installation(self, path: str) -> dict:
        if path not in {item["path"] for item in self.status()["installations"]}:
            raise ValueError("That installation is no longer available.")
        self.path, self.conflict = path, False
        return self.status()

    def install(self) -> dict:
        if not self.status()["canInstall"]:
            raise OSError("Check for a release and choose an installation first.")
        self.installed, self.version = True, self.release
        return self.status()

    def launch_command(self) -> list[str]:
        if not self.status()["canOpen"]:
            raise OSError("Install KOReader before opening it.")
        return ["/bin/sh", self.path + "/koreader.sh"]

    def uninstall(self, identity: Sequence[int]) -> dict:
        if (
            not self.status()["canRemove"]
            or list(identity) != self.status()["identity"]
        ):
            raise OSError("The selected installation changed. Refresh and try again.")
        self.installed, self.version, self.scriptlet = False, "", ""
        return self.status()

    def add_scriptlet(self) -> dict:
        if not self.status()["canAddScriptlet"]:
            raise OSError("Choose a ready KOReader installation first.")
        self.scriptlet = self.path
        return self.status()
