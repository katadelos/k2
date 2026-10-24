"""Validated handoff to the device session supervisor."""

import json
import os
from pathlib import Path

from .device import Device


class Launcher:
    def __init__(self, device: Device) -> None:
        self.device = device

    def launch_application(self, argv: list[str]) -> None:
        directory = os.environ.get("K2_SESSION_DIR")
        if not directory:
            raise OSError("Open k2 through its device launcher to launch applications.")
        if not argv or not all(
            isinstance(arg, str) and "\0" not in arg for arg in argv
        ):
            raise ValueError("Invalid application launch request")
        if not os.path.isabs(argv[0]) or ".." in Path(argv[0]).parts:
            raise ValueError("Invalid application executable path")
        executable = Path("/var/run/eink-sdk") / argv[0].lstrip("/")
        if not executable.is_file():
            raise OSError("The application's launcher is not installed.")
        target = Path(directory) / "launch.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps([str(executable), *argv[1:]]))
        temporary.replace(target)

    def launch_koreader(self, argv: list[str], expected: list[str]) -> None:
        directory = os.environ.get("K2_SESSION_DIR")
        if not directory:
            raise OSError("Open k2 through its device launcher to open KOReader.")
        if not argv or not all(
            isinstance(arg, str) and "\0" not in arg for arg in argv
        ):
            raise ValueError("Invalid KOReader launch request.")
        if argv != expected:
            raise ValueError(
                "The selected KOReader installation changed. Refresh and try again."
            )
        if not os.path.isabs(argv[0]) or not Path(argv[0]).is_file():
            raise OSError("KOReader’s launcher is unavailable.")
        target = Path(directory) / "launch.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(argv))
        temporary.replace(target)
