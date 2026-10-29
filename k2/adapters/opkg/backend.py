"""Asynchronous opkg access using the bootstrap's configuration and resolver."""

import os
import time
from pathlib import Path

from PyQt5.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, pyqtSignal

from ...core.packages import (
    PROTECTED,
    CatalogPackage,
    InstalledPackage,
    PackageFreshness,
    PackagePlan,
    restart_flags,
)
from ...core.ports import OperationResult
from .catalog import installed_snapshot, read_catalog
from .files import PackageFiles
from .parsing import PACKAGE_NAME, failure_message, parse_plan
from .state import ActivityStore

type Command = tuple[str, list[str]]

UPDATE_TIMEOUT_MS = 15000


class OpkgBackend(QObject):
    catalogChanged = pyqtSignal()
    activityChanged = pyqtSignal()
    logChanged = pyqtSignal()
    resultChanged = pyqtSignal()
    finished = pyqtSignal(bool, str)
    planned = pyqtSignal(bool, object)
    restartRequested = pyqtSignal()

    def __init__(
        self,
        executable: str | Path,
        parent: QObject | None = None,
        state_path: str | Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.executable = str(executable)
        self.kernel_feeds = Path(self.executable).with_name("kernel-feeds")
        self._kernel_feed_error = ""
        self.config_dir = Path(os.environ.get("OPKG_CONF_DIR", "/etc/opkg"))
        self.package_files = PackageFiles(self.config_dir)
        self.state_path = (
            Path(state_path) if state_path else self.config_dir.parent / "k2/state.json"
        )
        self._state_store = ActivityStore(self.state_path)
        self.catalog: list[CatalogPackage] = []
        self.busy = False
        self.status = "Loading packages"
        self.progress = 0.0
        self.log = ""
        self.catalog_error = ""
        self.state_error = ""
        self.freshness: PackageFreshness = {"lastRefresh": 0, "error": ""}
        self.last_result: OperationResult = {}
        self._queue: list[Command] = []
        self._results: dict[str, str] = {}
        self._key = ""
        self._output = ""
        self._operation = ""
        self._action = ""
        self._name = ""
        self._mode = "read"
        self._reviewed: tuple[str, str, PackagePlan] | None = None
        self._active = False
        self._restart_baseline: dict[str, InstalledPackage] | None = None
        self._baseline_loaded = False
        self._planned_restart = False
        self._transaction_ran = False
        self._update_error = ""
        self._update_cancelled = False
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(UPDATE_TIMEOUT_MS)
        self._update_timer.timeout.connect(self._update_timed_out)
        self._load_state()
        self.process = QProcess(self)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("LC_ALL", "C")
        # KPP activation restarts appmgrd, which kills its scriptlet clients,
        # including k2. Let opkg commit its status before any explicit reload.
        environment.insert("KPPMOD_DEFER_RELOAD", "1")
        self.process.setProcessEnvironment(environment)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.finished.connect(self._done)
        self.process.errorOccurred.connect(self._error)

    @property
    def checking_updates(self) -> bool:
        return self.busy and self._mode == "perform" and self._action == "update"

    def cancel_update(self) -> None:
        self._abort_update("Update check cancelled.", cancelled=True)

    def _update_timed_out(self) -> None:
        self._abort_update(
            "Update check timed out. Check your connection or feed server and try again."
        )

    def _abort_update(self, message: str, *, cancelled: bool = False) -> None:
        if not self.checking_updates or self._update_error:
            return
        self._update_timer.stop()
        self._update_error = message
        self._update_cancelled = cancelled
        self._queue.clear()
        # Only feed checks are cancellable; installed packages are not changed.
        # Keep ownership until QProcess reports that the child has stopped.
        if self.process.state() != QProcess.NotRunning:
            self.process.kill()

    def _load_state(self) -> None:
        try:
            self.freshness, self.last_result, self._restart_baseline = (
                self._state_store.load()
            )
            self._baseline_loaded = self._restart_baseline is not None
        except OSError, ValueError, TypeError:
            return
        if self.last_result.get("state") == "running":
            self.last_result.update(
                {
                    "state": "interrupted",
                    "message": "k2 closed before finishing. Some packages may have changed. Check your installed packages before trying again.",
                }
            )
            if self.last_result.get("action") == "update":
                self.last_result["message"] = (
                    "k2 closed before it finished checking for updates."
                )
                self.freshness["error"] = self.last_result["message"]
            self._save_state()
        self.log = self.last_result.get("log", "")

    def _save_state(self) -> None:
        try:
            self._state_store.save(
                self.freshness, self.last_result, self._restart_baseline
            )
            self.state_error = ""
        except OSError:
            self.state_error = "Couldn’t save package activity on this device."

    def refresh(self) -> None:
        self._start("Loading packages", "read", "", "", self._catalog_commands())

    def _validate(self, action: str, name: str) -> None:
        if self.catalog_error:
            raise ValueError("Reload the package list before making more changes.")
        if action == "upgrade" and name == "":
            return
        if action not in {"install", "upgrade", "remove"} or not PACKAGE_NAME.fullmatch(
            name
        ):
            raise ValueError("Invalid package action")
        package = next((item for item in self.catalog if item["name"] == name), None)
        if not package:
            raise ValueError("This package is no longer available.")
        if action == "remove" and package["protected"]:
            raise ValueError("This package is required by k2 or the device")

    def plan(self, action: str, name: str) -> None:
        self._validate(action, name)
        self._reviewed = None
        label = {
            "install": "Preparing installation",
            "upgrade": "Preparing update",
            "remove": "Preparing removal",
        }[action]
        self._start(
            label,
            "plan",
            action,
            name,
            [("plan", ["--json-plan", action] + ([name] if name else []))],
        )

    def perform(self, action: str, name: str = "") -> None:
        if action == "update":
            commands = (
                [("kernel-feeds", ["refresh"])] if self.kernel_feeds.is_file() else []
            )
            self._start(
                "Checking for updates",
                "perform",
                action,
                "",
                [*commands, ("operation", ["update"])],
            )
            return
        self._validate(action, name)
        if not self._reviewed or self._reviewed[:2] != (action, name):
            raise ValueError("Review package changes before continuing.")
        # Re-resolve against the current package database before making changes.
        # Opkg still owns locking during each command and the actual transaction.
        verb = {"install": "Installing", "upgrade": "Updating", "remove": "Removing"}[
            action
        ]
        label = f"{verb} {name}" if name else "Updating all packages"
        self._start(
            label,
            "perform",
            action,
            name,
            [("verify", ["--json-plan", action] + ([name] if name else []))],
        )

    @staticmethod
    def _catalog_commands() -> list[Command]:
        return [
            ("candidates", ["list-candidates"]),
            ("installed", ["status"]),
            ("updates", ["list-upgradable"]),
        ]

    def _start(
        self, label: str, mode: str, action: str, name: str, commands: list[Command]
    ) -> None:
        if self.busy:
            raise ValueError("Wait for the current task to finish.")
        self.busy = True
        if mode == "plan":
            pass
        elif mode != "read" or not self.last_result:
            self.log = label + "\n"
        else:
            self.log = self.last_result.get("log", "")
        self._operation, self._mode, self._action, self._name = (
            label,
            mode,
            action,
            name,
        )
        self._kernel_feed_error = ""
        self.catalog_error = ""
        self._results = {}
        self._queue = list(commands)
        self._transaction_ran = False
        self._update_error = ""
        self._update_cancelled = False
        if mode == "perform":
            self.last_result = {
                "action": action,
                "name": name,
                "state": "running",
                "message": "",
                "startedAt": int(time.time()),
                "finishedAt": 0,
                "catalogError": "",
                "restartRequired": False,
                "restartReaderRequired": False,
                "reloadKppRequired": False,
                "restartAutomatic": False,
                "restartUncertain": self._restart_baseline is not None,
                "log": self.log,
            }
            self._save_state()
        self.activityChanged.emit()
        self.logChanged.emit()
        self.resultChanged.emit()
        if self.checking_updates:
            self._update_timer.start()
        self._next()

    def _next(self) -> None:
        if self._update_error:
            self._complete_command(False, self._update_error)
            return
        self._key, args = self._queue.pop(0)
        self._output = ""
        self._active = True
        if self._key == "operation" and self._action != "update":
            self._transaction_ran = True
        preparing = {
            "install": "Preparing installation",
            "upgrade": "Preparing update",
            "remove": "Preparing removal",
        }.get(self._action, "Loading packages")
        self.status = (
            "Checking for updates"
            if self._action == "update"
            else {
                "candidates": "Loading packages",
                "before": "Checking installed packages",
                "installed": "Checking installed packages",
                "updates": "Checking for updates",
                "plan": preparing,
                "verify": preparing,
                "operation": self._operation,
            }[self._key]
        )
        self.progress = {
            "candidates": 0.15,
            "installed": 0.4,
            "updates": 0.85,
        }.get(self._key, 0.0)
        self.activityChanged.emit()
        if self._update_error:
            self._complete_command(False, self._update_error)
            return
        # No shell, user supplied switches, feed overrides or forced dependencies.
        self.process.start(
            str(self.kernel_feeds) if self._key == "kernel-feeds" else self.executable,
            args,
        )
        self.process.closeWriteChannel()

    def _read(self) -> None:
        text = bytes(self.process.readAllStandardOutput()).decode("utf-8", "replace")
        self._output += text
        if not text:
            return
        previous_status = self.status
        if self._key in {"operation", "verify", "kernel-feeds"}:
            self.log = (self.log + text)[-32768:]
            if self._key == "operation" and self._action != "update":
                lines = [line for line in text.splitlines() if line.strip()]
                if lines:
                    line = lines[-1]
                    for prefix, label in (
                        ("Downloading ", "Downloading packages"),
                        ("Installing ", "Installing packages"),
                        ("Upgrading ", "Updating packages"),
                        ("Configuring ", "Finishing setup"),
                        ("Removing ", "Removing packages"),
                    ):
                        if line.startswith(prefix):
                            self.status = label
                            break
            self.logChanged.emit()
            if self.status != previous_status:
                self.activityChanged.emit()

    def _error(self, error: int) -> None:
        if error == QProcess.FailedToStart and self._active:
            self._active = False
            message = self.process.errorString()
            QTimer.singleShot(0, lambda: self._complete_command(False, message))

    def _done(self, code: int, status: int) -> None:
        if not self._active:
            return
        self._read()
        if self._update_error:
            self._complete_command(False, self._update_error)
            return
        success = code == 0 and status == QProcess.NormalExit
        error = ""
        if status == QProcess.CrashExit:
            error = "The package manager stopped unexpectedly."
            if self._key == "operation" and self._action != "update":
                error += " Some packages may have changed. Check the installed packages before retrying."
            self.log = (self.log + f"\nopkg terminated unexpectedly (code {code}).\n")[
                -32768:
            ]
        elif not success:
            error = failure_message(self._output) or f"opkg exited with status {code}"
        self._complete_command(success, error)

    def _command_plan(self, success: bool, error: str) -> PackagePlan:
        if not success:
            return PackagePlan(error=error)
        try:
            plan = parse_plan(self._output)
            forbidden = [
                item.name
                for item in plan.changes
                if item.action == "remove" and item.name in PROTECTED
            ]
            if forbidden:
                raise ValueError(
                    "This change would remove packages required by k2: "
                    + ", ".join(forbidden)
                )
        except (ValueError, TypeError, KeyError) as exception:
            return PackagePlan(error=str(exception))
        return plan

    def _complete_plan(self, success: bool, error: str) -> None:
        plan = self._command_plan(success, error)
        success = success and not plan.error
        if self._key == "plan":
            self.busy = False
            self.status = "Ready"
            if success:
                self._reviewed = (self._action, self._name, plan)
            # Present the completed plan before idle resumes other work.
            self.planned.emit(success, plan)
            self.activityChanged.emit()
            return
        if success and (self._reviewed is None or plan != self._reviewed[2]):
            success, error = (
                False,
                (
                    "The package list has changed. Check the new list and confirm again. "
                    "Nothing was installed or removed."
                ),
            )
        else:
            error = plan.error
        if success:
            self._planned_restart = (
                plan.restart_required
                or plan.restart_reader_required
                or plan.reload_kpp_required
            )
            # Capture the actual status immediately before mutation. The cached
            # browsing catalog may predate changes made by another opkg client.
            self._queue = [
                ("before", ["status"]),
                ("operation", [self._action] + ([self._name] if self._name else [])),
            ]
        else:
            self._record_result(False, error)
            self._queue = self._catalog_commands()
        self._next()

    def _complete_command(self, success: bool, error: str) -> None:
        self._active = False
        if self._update_error:
            self._record_result(False, self._update_error)
            self._finish()
            return
        if self._key in {"plan", "verify"}:
            self._complete_plan(success, error)
            return
        if self._key == "before":
            if success:
                if self._planned_restart:
                    self._restart_baseline = installed_snapshot(self._output)
                    self._baseline_loaded = False
                    self._save_state()
            else:
                self._record_result(False, error)
                self._queue = self._catalog_commands()
        elif self._key == "kernel-feeds":
            if not success:
                self._kernel_feed_error = "Kernel module feed: " + error
        elif self._key == "operation":
            self._record_result(success, error)
            self._reviewed = None
            self._queue = self._catalog_commands()
        elif success:
            self._results[self._key] = self._output
        else:
            self.catalog_error = error
        if self._queue:
            self._next()
        else:
            self._finish()

    def _record_result(self, success: bool, error: str) -> None:
        verb = {"install": "installed", "upgrade": "updated", "remove": "removed"}
        if not success:
            message = error
        elif self._action == "update":
            message = "Finished checking for updates."
            if self._kernel_feed_error:
                message = "Checked for app updates, but couldn’t check for kernel module updates. See details."
        elif self._action == "upgrade" and not self._name:
            message = "Packages updated."
        else:
            message = f"{self._name} {verb[self._action]}."
        self.last_result.update(
            {
                "state": "cancelled"
                if self._update_cancelled
                else "succeeded"
                if success
                else "failed",
                "message": message,
                "finishedAt": int(time.time()),
                "log": self.log,
            }
        )
        if self._action == "update":
            self._update_timer.stop()
            if success:
                self.freshness = {
                    "lastRefresh": int(time.time()),
                    "error": self._kernel_feed_error,
                }
            else:
                self.freshness["error"] = error
        self._save_state()
        self.resultChanged.emit()

    def _reconcile_restarts(self) -> bool:
        if self._restart_baseline is None:
            return False
        if "installed" not in self._results:
            if self._transaction_ran:
                self.last_result["restartUncertain"] = True
            return False
        flags = restart_flags(
            self._restart_baseline, installed_snapshot(self._results["installed"])
        )
        if self._baseline_loaded:
            # A new k2 process already loaded its current runtime. The reader's
            # firmware process may still need a restart (for example k2-nickel).
            flags["restartRequired"] = flags["restartAutomatic"] = False
        self.last_result.update(flags)
        self.last_result["restartUncertain"] = False
        self._restart_baseline = None
        self._save_state()
        return True

    def _finish(self) -> None:
        reconciled = self._reconcile_restarts()
        if not self.catalog_error and not self._update_error:
            try:
                catalog = read_catalog(self._results)
            except (ValueError, KeyError) as error:
                self.catalog_error = f"Could not read package catalog: {error}"
            else:
                if catalog != self.catalog:
                    self.catalog = catalog
                    self.catalogChanged.emit()
        self.busy = False
        self.progress = 1.0
        self.status = "Ready"
        if self._mode == "perform":
            success = self.last_result["state"] == "succeeded"
            message = self.last_result["message"]
            if self.catalog_error:
                message += "\nThe package list couldn’t be reloaded. Reload it before making more changes."
            self.last_result.update(
                {"catalogError": self.catalog_error, "log": self.log}
            )
            self._save_state()
        else:
            success = not bool(self.catalog_error)
            message = self.catalog_error or "Package list loaded."
        if self._mode != "read" or not self.last_result:
            self.log = (self.log + "\n" + message)[-32768:]
        restart_automatically = (
            self._mode == "perform" or reconciled
        ) and self.last_result.get("restartAutomatic", False)
        # Consumers can reserve follow-up metadata work before publishing idle.
        self.finished.emit(success, message)
        if restart_automatically:
            self.restartRequested.emit()
        self.activityChanged.emit()
        self.resultChanged.emit()
        self.logChanged.emit()
