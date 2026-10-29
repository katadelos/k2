"""Own the stock framebuffer services while an external reader is visible."""

import subprocess
import time
from pathlib import Path


class FramebufferSession:
    """Stop existing display owners through firmware and restore them on close."""

    _SERVICES = (
        ("framework", "cvm"),
        ("webreaderd", "webreader"),
        ("browserd", "browserd"),
    )

    def __init__(self):
        self._owned = []
        self._stopped = set()
        self._upstart = Path("/etc/upstart/x.conf").is_file()
        if self._upstart:
            # Use the firmware jobs so their crash monitors stay idle. The GUI
            # needs an explicit restart: its boot-only start event is consumed.
            running = [
                (service, process)
                for service, process in (("lab126_gui", None), ("x", "Xorg"))
                if Path(f"/etc/upstart/{service}.conf").is_file()
                and self._status(service).startswith(f"{service} start/")
            ]
            if ("x", "Xorg") not in running and self._pids("Xorg"):
                raise OSError(
                    "The stock X server is not owned by its firmware service."
                )
        else:
            running = [
                (service, process)
                for service, process in self._SERVICES
                if self._pids(process)
            ]
        try:
            for service, process in running:
                # A script may stop its owner and then fail. Cleanup still owns
                # that transition and must restore the initially running service.
                self._owned.append((service, process))
                self._run(service, "stop")
                self._wait(service, process, present=False)
                self._stopped.add(service)
        except BaseException as error:
            try:
                self.close()
            except Exception as cleanup:
                error.add_note(
                    f"Restoring stock framebuffer services failed: {cleanup}"
                )
            raise

    @staticmethod
    def _status(service):
        return subprocess.run(  # noqa: S603 -- fixed firmware service names
            ["/sbin/initctl", "status", service],
            check=True,
            timeout=25,
            capture_output=True,
            text=True,
        ).stdout.strip()

    @staticmethod
    def _pids(name):
        found = []
        for entry in Path("/proc").iterdir():
            if not entry.name.isdecimal():
                continue
            try:
                status = (entry / "stat").read_text()
            except FileNotFoundError, ProcessLookupError:
                continue
            # /proc/PID/comm is absent on some supported kernels. The stat
            # command field is shared by every supported Linux version.
            start, end = status.find("("), status.rfind(")")
            if start >= 0 and end > start and status[start + 1 : end] == name:
                state = status[end + 1 :].split()[0]
                if state != "Z":
                    found.append(int(entry.name))
        return found

    def _run(self, service, action):
        # browserd's script uses killall browserd. Invoking the shell explicitly
        # keeps that command from killing the script by its own process name.
        command = (
            ["/sbin/initctl", action, service]
            if self._upstart
            else ["/bin/sh", f"/etc/init.d/{service}", action]
        )
        subprocess.run(  # noqa: S603 -- fixed firmware service names and actions
            command,
            check=True,
            timeout=25,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _running(self, service, process):
        if self._upstart:
            running = self._status(service).startswith(f"{service} start/running")
            return running and (process is None or bool(self._pids(process)))
        return bool(self._pids(process))

    def _wait(self, service, process, *, present):
        deadline = time.monotonic() + 25
        while self._running(service, process) != present or (
            not present and process is not None and self._pids(process)
        ):
            if time.monotonic() >= deadline:
                operation = "start" if present else "stop"
                raise TimeoutError(
                    f"Stock framebuffer service {service} did not {operation}."
                )
            time.sleep(0.1)

    def close(self):
        errors = []
        for service, process in reversed(self._owned.copy()):
            try:
                if self._upstart:
                    if self._status(service).startswith(f"{service} stop/"):
                        self._run(service, "start")
                    # A start goal can still be in pre-start or spawned. Do not
                    # issue another start while firmware is completing it.
                    self._wait(service, process, present=True)
                elif service not in self._stopped:
                    # A failed stop may leave the original process alive while
                    # firmware policy still says stopped. Official restart
                    # completes that transition and resets the service policy.
                    self._run(service, "restart")
                    self._wait(service, process, present=True)
                elif not self._running(service, process):
                    self._run(service, "start")
                    self._wait(service, process, present=True)
                self._owned.remove((service, process))
                self._stopped.discard(service)
            except Exception as error:
                errors.append(f"{service}: {error}")
        if errors:
            raise OSError(
                "Could not restore stock framebuffer services: " + "; ".join(errors)
            )
