"""KPP maintenance commands owned by k2, independent of Supernet."""

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from . import kpp_status

MANAGER = Path("/var/run/eink-sdk/usr/bin/kppmod")
LOG = Path("/var/log/messages")


def command(*args: str, timeout: float = 300) -> str:
    result = subprocess.run(  # noqa: S603 -- fixed SDK executable; arguments are passed without a shell
        [str(MANAGER), *args], capture_output=True, text=True, timeout=timeout
    )
    if result.returncode:
        raise OSError(result.stderr.strip()[-2048:] or "KPP maintenance failed.")
    return result.stdout


def recent_log(path: Path = LOG) -> str:
    try:
        with path.open("rb") as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - 262144))
            text = stream.read().decode("utf-8", errors="replace")
        return re.sub(r"\x1b\[[0-9;]*m", "", text)
    except OSError as error:
        return "Log unavailable: " + str(error)


def ui_errors() -> list[dict[str, Any]]:
    result = subprocess.run(  # noqa: S603 -- fixed SDK executable; arguments are passed without a shell
        [str(MANAGER.with_name("kppmod-bridge")), "--request", "state"],
        input="{}",
        capture_output=True,
        text=True,
        timeout=8,
    )
    if result.returncode:
        raise OSError(
            result.stderr.strip()[-1024:] or "Cannot read UI extension errors."
        )
    return kpp_status.ui_events(result.stdout)


def status() -> dict[str, Any]:
    if not MANAGER.is_file():
        return {"kppAvailable": False}
    try:
        state = kpp_status.native_status(command("status", timeout=8))
        errors = [
            str(item.get("module", "")) + ": " + str(item.get("message", ""))
            for process in state.get("native", [])
            for item in process.get("entries", [])
            if item.get("priority", 7) <= 3
        ]
        for line in recent_log().splitlines():
            lower = line.lower()
            if "kppmod" in lower and any(
                word in lower for word in ("error", "failed", "exception")
            ):
                errors.append(line)
        warning = ""
        try:
            errors.extend(
                str(event["owner"]) + ": " + str(event["message"])
                for event in ui_errors()
            )
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            warning = "UI error history unavailable: " + str(error)
        return {
            "kppAvailable": True,
            "kppBusy": bool(state.get("manager_running")),
            "kppErrors": errors[-12:],
            "kppError": warning,
        }
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return {
            "kppAvailable": True,
            "kppBusy": True,
            "kppErrors": [],
            "kppError": str(error),
        }


def change(action: str) -> str:
    if not MANAGER.is_file():
        raise OSError("KPP Mods is not installed.")
    if action == "kpp-restart":
        command("reload", "ui-host")
    elif action == "kpp-safe-mode":
        packages = kpp_status.packages(command("list", timeout=8))
        keep = {"ui-host", "mod-manager"} & packages.keys()
        pending = list(keep)
        while pending:
            for dependency in packages[pending.pop()].get("needs", []):
                if dependency not in keep:
                    if dependency not in packages:
                        raise OSError("Required extension is missing: " + dependency)
                    keep.add(dependency)
                    pending.append(dependency)
        command("apply", json.dumps(sorted(packages.keys() - keep)))
    elif action == "kpp-export":
        # Fixed userstore destination, with each export preserving earlier files.
        directory = Path("/mnt/us/kppmods-diagnostics")
        directory.mkdir(exist_ok=True)
        target = directory / (
            datetime.now().strftime("kppmods-%Y%m%d-%H%M%S-%f") + ".txt"
        )
        with target.open("x") as output:
            state = kpp_status.native_status(command("status", timeout=8))
            output.write(
                "KPP Mods native status\n"
                + json.dumps(
                    {
                        "manager_running": state.get("manager_running"),
                        "native": state.get("native", []),
                    },
                    indent=2,
                )
            )
            output.write("\nUI extension errors\n")
            try:
                output.write(json.dumps(ui_errors(), indent=2))
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                output.write("UI error history unavailable: " + str(error))
            output.write("\nInstalled extensions\n" + command("list", timeout=8))
            output.write("\nRecent system log (up to 256 KiB)\n" + recent_log())
            for log in (
                Path("/var/local/kppmods/app.log"),
                Path("/var/run/k2-developer-tools.log"),
            ):
                output.write("\n" + str(log) + " (up to 256 KiB)\n" + recent_log(log))
        return "Saved diagnostics to " + str(target)
    else:
        raise ValueError("Unsupported KPP maintenance action.")
    return (
        "Optional extensions are disabled. Re-enable them in Extensions."
        if action == "kpp-safe-mode"
        else "Kindle interface restarted."
    )
