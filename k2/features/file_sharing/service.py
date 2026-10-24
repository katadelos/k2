"""Fixed protocol for the installed file-sharing package."""

import json
import subprocess
from pathlib import Path
from typing import cast

from .ports import SharingAction, SharingState


class FileSharingService:
    def call(self, action: SharingAction) -> SharingState:
        if action not in {"status-json", "start", "stop"}:
            raise ValueError("Unsupported file-sharing action.")
        executable = Path("/var/run/eink-sdk/usr/bin/k2-fileshare")
        result = subprocess.run(  # noqa: S603 -- fixed SDK executable and validated action
            [str(executable), action],
            capture_output=True,
            text=True,
            timeout=8 if action == "status-json" else 55,
        )
        if result.returncode:
            raise OSError(
                result.stderr.strip()[-1024:] or "Could not change File Sharing."
            )
        try:
            state = json.loads(result.stdout)
            if state.get("schema") != 1:
                raise ValueError("Unsupported status")
            for name in ("running", "canStart", "usbBlocked"):
                if type(state.get(name)) is not bool:
                    raise ValueError("Invalid status")
            for name in ("address", "name", "detail", "error"):
                if not isinstance(state.get(name), str):
                    raise ValueError("Invalid status")
            if state["running"]:
                for name in (
                    "windows",
                    "mac",
                    "direct",
                    "username",
                    "password",
                    "url",
                    "network",
                ):
                    if not isinstance(state.get(name), str):
                        raise ValueError("Invalid connection details")
                matrix = state.get("qr")
                if not isinstance(matrix, list) or not 21 <= len(matrix) <= 185:
                    raise ValueError("Invalid QR code")
                if any(
                    not isinstance(row, list)
                    or len(row) != len(matrix)
                    or any(type(cell) is not bool for cell in row)
                    for row in matrix
                ):
                    raise ValueError("Invalid QR code")
            return cast(SharingState, state)
        except (ValueError, TypeError, AttributeError) as error:
            raise OSError("File Sharing returned an invalid status.") from error
