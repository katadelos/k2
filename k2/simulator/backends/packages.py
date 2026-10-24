import time
from pathlib import Path

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from ... import __version__
from ...core.packages import (
    PROTECTED,
    RESTART_PACKAGES,
    CatalogPackage,
    InstalledPackage,
    PackageChange,
    PackageFreshness,
    PackagePlan,
    restart_flags,
)
from ...core.ports import OperationResult


class SimulatedPackages(QObject):
    config_dir: Path | None = None
    catalogChanged = pyqtSignal()
    activityChanged = pyqtSignal()
    logChanged = pyqtSignal()
    resultChanged = pyqtSignal()
    finished = pyqtSignal(bool, str)
    planned = pyqtSignal(bool, object)
    restartRequested = pyqtSignal()

    def __init__(self, scenario: str) -> None:
        super().__init__()
        self.scenario = scenario
        self.freshness: PackageFreshness = {"lastRefresh": 0, "error": ""}
        self.last_result: OperationResult = {}
        self.catalog_error = ""
        self.state_error = ""
        self.busy = False
        self.status = "Loading packages"
        self.progress = 0.15
        self.log = "Simulator ready. Package changes stay in memory."
        k2_version = f"{__version__}-r1"
        samples = [
            ("k2", k2_version, "Package and system manager", k2_version, ""),
            (
                "dropbear",
                "2025.88-r3",
                "Lightweight SSH server and client",
                "2024.86-r3",
                "2025.88-r3",
            ),
            ("python3", "3.13.7-r3", "Python programming language", "3.13.7-r3", ""),
            ("python-pyqt5", "5.15.6-r4", "Python bindings for Qt", "5.15.6-r4", ""),
            ("htop", "3.4.1-r3", "Interactive process viewer", "", ""),
            ("curl", "8.16.0-r3", "Transfer data using network protocols", "", ""),
            ("nano", "8.6-r3", "Small terminal text editor", "", ""),
            ("rsync", "3.4.1-r3", "Efficient file synchronisation", "", ""),
        ]
        samples.append(
            (
                "supernet",
                "0.1.0-r1",
                "Key-only SSH access over USB or Wi-Fi",
                "0.1.0-r1"
                if scenario in {"supernet", "supernet-setup", "home-assistant"}
                else "",
                "",
            )
        )
        samples.append(
            (
                "k2-home",
                "0.1.0-r1",
                "Native Home Assistant app",
                "0.1.0-r1" if scenario == "home-assistant" else "",
                "",
            )
        )
        self.catalog: list[CatalogPackage] = (
            []
            if scenario == "empty"
            else [
                {
                    "name": n,
                    "version": v,
                    "summary": s,
                    "installed": i,
                    "update": u,
                    "available": True,
                    "protected": n in PROTECTED,
                    "configured": bool(i),
                }
                for n, v, s, i, u in samples
            ]
        )

    def refresh(self) -> None:
        self.busy = True
        self.status = "Loading packages"
        self.activityChanged.emit()
        if self.scenario == "loading":
            return

        def finish() -> None:
            self.busy = False
            self.status = "Ready"
            self.progress = 1.0
            self.catalogChanged.emit()
            self.finished.emit(True, "Package list loaded.")
            self.activityChanged.emit()

        QTimer.singleShot(700, finish)

    @staticmethod
    def package_files(name: str) -> list[str]:
        return []

    def _targets(self, action: str, name: str) -> list[CatalogPackage]:
        if action == "upgrade" and name == "":
            return [p for p in self.catalog if p["installed"] and p["update"]]
        package = next((p for p in self.catalog if p["name"] == name), None)
        if not package:
            raise ValueError("Unknown package")
        return [package]

    @staticmethod
    def _make_plan(action: str, targets: list[CatalogPackage]) -> PackagePlan:
        return PackagePlan(
            changes=tuple(
                PackageChange(
                    action=action,
                    name=package["name"],
                    from_version=package["installed"],
                    to_version="" if action == "remove" else package["version"],
                )
                for package in targets
            ),
            download_bytes=0 if action == "remove" else 284672 * len(targets),
            installed_delta_bytes=(-1048576 if action == "remove" else 1048576)
            * len(targets),
            restart_required=action != "remove"
            and any(package["name"] in RESTART_PACKAGES for package in targets),
            restart_reader_required=action != "remove"
            and any(package["name"] == "k2-nickel" for package in targets),
        )

    def plan(self, action: str, name: str) -> None:
        if self.busy:
            raise ValueError("Wait for the current task to finish.")
        targets = self._targets(action, name)
        self.busy = True
        self.status = {
            "install": "Preparing installation",
            "upgrade": "Preparing update",
            "remove": "Preparing removal",
        }[action]
        self.activityChanged.emit()

        def finish() -> None:
            self.busy = False
            self.status = "Ready"
            plan = self._make_plan(action, targets)
            self.planned.emit(True, plan)
            self.activityChanged.emit()

        QTimer.singleShot(200, finish)

    def perform(self, action: str, name: str = "") -> None:
        if self.busy:
            raise ValueError("Wait for the current task to finish.")
        if action not in {"update", "install", "upgrade", "remove"}:
            raise ValueError("Invalid package action")
        if action == "remove" and name in PROTECTED:
            raise ValueError("This package is required by k2")
        targets = [] if action == "update" else self._targets(action, name)
        before = self._installed_snapshot()
        self.busy = True
        self.status = {
            "install": f"Installing {name}",
            "upgrade": f"Updating {name}" if name else "Updating all packages",
            "remove": f"Removing {name}",
            "update": "Checking for updates",
        }[action]
        self.log = f"Simulating opkg {action} {name}\nResolving dependencies…"
        self.last_result = {
            "action": action,
            "name": name,
            "state": "running",
            "message": "",
            "catalogError": "",
            "restartRequired": False,
            "restartReaderRequired": False,
            "restartAutomatic": False,
        }
        self.activityChanged.emit()
        self.logChanged.emit()
        self.resultChanged.emit()

        def finish() -> None:
            self.busy = False
            success = self.scenario != "offline"
            if success:
                for package in targets:
                    package["installed"] = (
                        "" if action == "remove" else package["version"]
                    )
                    package["configured"] = action != "remove"
                    package["update"] = ""
                verb = {
                    "install": "installed",
                    "upgrade": "updated",
                    "remove": "removed",
                }
                if action == "update":
                    message = "Finished checking for updates."
                elif action == "upgrade" and not name:
                    message = "Packages updated."
                else:
                    message = f"{name} {verb[action]}."
            else:
                message = "Couldn’t connect. Check your network and try again."
            if action == "update":
                if success:
                    self.freshness = {"lastRefresh": int(time.time()), "error": ""}
                else:
                    self.freshness["error"] = message
            restarts = restart_flags(before, self._installed_snapshot())
            self.last_result = {
                "action": action,
                "name": name,
                "state": "succeeded" if success else "failed",
                "message": message,
                "catalogError": "",
                "finishedAt": int(time.time()),
                **restarts,
            }
            self.status = "Ready"
            self.log += "\n" + message
            if success and targets:
                self.catalogChanged.emit()
            self.finished.emit(success, message)
            if restarts["restartAutomatic"]:
                self.restartRequested.emit()
            self.activityChanged.emit()
            self.logChanged.emit()
            self.resultChanged.emit()

        QTimer.singleShot(700, finish)

    def _installed_snapshot(self) -> dict[str, InstalledPackage]:
        return {
            package["name"]: InstalledPackage(
                package["installed"],
                "installed" if package["configured"] else "unpacked",
            )
            for package in self.catalog
            if package["installed"]
        }
