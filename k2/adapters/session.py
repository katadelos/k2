"""Own temporary device resources independently of the UI process."""

import argparse
import ctypes
import fcntl
import json
import os
import select
import signal
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import suppress
from pathlib import Path

NICKEL_SOCKET = "/var/run/k2-nickel.sock"


def native_request(command, **values):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(4)
        connection.connect(NICKEL_SOCKET)
        return request(connection, command, **values)


def request(connection, command, **values):
    connection.sendall((json.dumps(dict(command=command, **values)) + "\n").encode())
    data = bytearray()
    while b"\n" not in data and len(data) <= 4096:
        part = connection.recv(4096)
        if not part:
            raise OSError("The stock reader control connection closed.")
        data.extend(part)
    result = json.loads(data.split(b"\n", 1)[0])
    if result.get("error"):
        raise OSError(result["error"])
    return result


class WakeLease:
    """Renew a HAL wake lease, supplementing Nickel session ownership on Kobo."""

    def __init__(self, family):
        self.device = None
        self.held = False
        self.optional = family == "kobo"
        self.enabled = True

    def renew(self):
        if not self.enabled:
            return
        if self.device is None:
            from ereader_hal import Capability, Device

            self.device = Device()
            if (
                self.optional
                and not self.device.get_capability(Capability.AWAKE_LEASE).available
            ):
                self.device.close()
                self.device = None
                self.enabled = False
                return
        self.device.renew_awake(45)
        self.held = True

    def release(self):
        if self.held and self.device is not None:
            self.device.release_awake()
            self.held = False

    def close(self):
        try:
            self.release()
        finally:
            if self.device is not None:
                self.device.close()
                self.device = None


class DisplaySession:
    """Keep the displayed app scoped to its supervisor on either firmware family."""

    def __init__(self, family, *, retain_display=False, allow_sleep=False):
        self.bridge = None
        self.device = None
        self.framebuffer = None
        self.direct_framebuffer = (
            family != "kobo" and os.environ.get("QT_QPA_PLATFORM") == "ereader"
        )
        self.visible = False
        self.allow_sleep = allow_sleep
        try:
            if family == "kobo":
                self.bridge = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.bridge.settimeout(4)
                try:
                    self.bridge.connect(NICKEL_SOCKET)
                except OSError as error:
                    raise OSError(
                        "The k2 native bridge is not available. Restart the Kobo after installing k2-nickel."
                    ) from error
            elif retain_display:
                from ereader_hal import Device

                self.device = Device()
            self.set_visible(True)
        except Exception:
            self.close()
            raise

    def set_visible(self, visible):
        if self.visible == visible:
            return
        if self.bridge is not None:
            if visible:
                request(self.bridge, "begin", allowSleep=self.allow_sleep)
            else:
                request(self.bridge, "end")
        else:
            if visible:
                if self.device is not None:
                    self.device.retain_display()
                if self.direct_framebuffer:
                    from .framebuffer import FramebufferSession

                    self.framebuffer = FramebufferSession()
            else:
                if self.framebuffer is not None:
                    self.framebuffer.close()
                    self.framebuffer = None
                if self.device is not None:
                    self.device.release_display()
        self.visible = visible

    def close(self):
        try:
            if self.bridge is not None:
                # Disconnect is also the crash cleanup path in Nickel.
                with suppress(OSError, ValueError):
                    self.set_visible(False)
            else:
                self.set_visible(False)
        finally:
            if self.bridge is not None:
                self.bridge.close()
                self.bridge = None
            if self.device is not None:
                self.device.close()
                self.device = None


def child_setup(parent):
    # If the resource owner is SIGKILLed, the UI must relinquish its display fd.
    # The kernel closes Nickel's session socket and lets the wake lease expire.
    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(signum, signal.SIG_DFL)
    if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGTERM, 0, 0, 0) != 0:
        raise OSError(
            ctypes.get_errno(), "Unable to bind UI lifetime to its supervisor"
        )
    if os.getppid() != parent:
        os.kill(os.getpid(), signal.SIGTERM)


def main():
    parser = argparse.ArgumentParser(
        description="Supervise a k2-compatible Qt application"
    )
    parser.add_argument("family", choices=("kindle", "kobo"))
    parser.add_argument("--module", default="k2.app.device_main")
    parser.add_argument(
        "--allow-sleep",
        action="store_true",
        help="leave sleep and idle timeouts under stock firmware control",
    )
    parser.add_argument(
        "--retain-display",
        action="store_true",
        help="retain app content while the app coordinates suspend through the HAL",
    )
    args, arguments = parser.parse_known_args()
    if args.family == "kobo" and args.retain_display:
        parser.error("app display retention is only supported on Kindle")
    if args.allow_sleep and args.retain_display:
        parser.error(
            "stock sleep screens and app display retention are mutually exclusive"
        )
    with open("/var/run/k2-ui.lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("k2 is already running.", file=sys.stderr)
            return 1
        with tempfile.TemporaryDirectory(
            prefix="k2-session-", dir="/var/run"
        ) as directory:
            result, argv = supervise(
                args.family,
                arguments,
                directory,
                args.module,
                allow_sleep=args.allow_sleep,
                retain_display=args.retain_display,
            )
    # A second k2-compatible app acquires the same lock and display session.
    # Release both before starting its launcher.
    if argv:
        subprocess.Popen(  # noqa: S603 -- explicit launcher argv; no shell
            argv,
            env={
                key: value
                for key, value in os.environ.items()
                if key != "K2_SESSION_DIR"
            },
            start_new_session=True,
        )
    return result


def supervise(
    family,
    arguments,
    directory,
    module="k2.app.device_main",
    *,
    allow_sleep=False,
    retain_display=False,
):
    environment = dict(
        os.environ,
        K2_SESSION_DIR=directory,
        K2_ALLOW_SLEEP="1" if allow_sleep else "0",
        K2_RETAIN_DISPLAY="1" if retain_display else "0",
    )
    control = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    control.bind(str(Path(directory) / "control"))
    display, child = None, None
    wake = WakeLease(family)
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True
        if child is not None and child.poll() is None:
            child.terminate()

    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(signum, stop)
    try:
        if not allow_sleep:
            wake.renew()
        display = DisplaySession(
            family, retain_display=retain_display, allow_sleep=allow_sleep
        )
        owner_pid = os.getpid()
        child = subprocess.Popen(  # noqa: S603 -- explicit launcher argv; no shell
            [sys.executable, "-m", module, "--family", family, *arguments],
            env=environment,
            preexec_fn=lambda: child_setup(owner_pid),
        )
        _wait_for_child(
            child, control, display, wake, family, allow_sleep, retain_display
        )
        result = child.returncode
    finally:
        _terminate_child(child, timeout=75 if retain_display else 5)
        try:
            if display is not None:
                display.close()
        finally:
            try:
                wake.close()
            finally:
                control.close()
    handoff = Path(directory) / "launch.json"
    argv = []
    if result == 0 and not stopping and handoff.exists():
        argv = json.loads(handoff.read_text())
        if (
            not isinstance(argv, list)
            or not argv
            or not all(isinstance(arg, str) and "\0" not in arg for arg in argv)
        ):
            raise ValueError("Invalid application launch request")
    return result, argv


def _wait_for_child(child, control, display, wake, family, allow_sleep, retain_display):
    active, next_renewal = True, 0.0
    bridge = display.bridge
    while child.poll() is None:
        readable, _, _ = select.select(
            [control] + ([bridge] if bridge else []), [], [], 1
        )
        if bridge in readable:
            if child.poll() is not None:
                break
            raise OSError("The stock reader display session ended.")
        if control in readable:
            message = control.recv(128)
            if message in (b"active", b"inactive"):
                active = family == "kobo" or message == b"active"
                next_renewal = 0
            elif retain_display and message in (b"retain", b"release"):
                display.set_visible(message == b"retain")
        if not allow_sleep and active and time.monotonic() >= next_renewal:
            wake.renew()
            next_renewal = time.monotonic() + 15
        elif not active:
            wake.release()


def _terminate_child(child, *, timeout=5):
    if child is not None and child.poll() is None:
        child.terminate()
        try:
            # App-owned suspend must finish restoring hardware before its
            # framebuffer and stock display session can be released.
            child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"k2: {error}", file=sys.stderr)
        raise SystemExit(1) from error
