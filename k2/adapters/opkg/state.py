"""Durable package activity storage, independent of the process and UI state."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from ...core.packages import InstalledPackage, PackageFreshness
from ...core.ports import OperationResult

_RESULT_FIELDS = {
    "action": str,
    "name": str,
    "state": str,
    "message": str,
    "log": str,
    "catalogError": str,
    "startedAt": int,
    "finishedAt": int,
    "restartRequired": bool,
    "restartReaderRequired": bool,
    "restartAutomatic": bool,
    "restartUncertain": bool,
    "reloadKppRequired": bool,
}


@dataclass(frozen=True)
class ActivityStore:
    path: Path

    def load(
        self,
    ) -> tuple[PackageFreshness, OperationResult, dict[str, InstalledPackage] | None]:
        state = json.loads(self.path.read_text())
        if not isinstance(state, dict):
            raise ValueError("Invalid package activity")
        freshness = state.get("freshness", {"lastRefresh": 0, "error": ""})
        result = state.get("lastResult", {})
        if (
            not isinstance(freshness, dict)
            or type(freshness.get("lastRefresh")) is not int
            or not isinstance(freshness.get("error"), str)
        ):
            raise ValueError("Invalid package refresh state")
        if not isinstance(result, dict) or any(
            key not in _RESULT_FIELDS or type(value) is not _RESULT_FIELDS[key]
            for key, value in result.items()
        ):
            raise ValueError("Invalid package result")
        before = state.get("restartBefore")
        snapshot = None
        if before is not None:
            if not isinstance(before, dict) or any(
                not isinstance(name, str)
                or not isinstance(item, dict)
                or set(item) != {"version", "state"}
                or not all(isinstance(value, str) for value in item.values())
                for name, item in before.items()
            ):
                raise ValueError("Invalid package restart snapshot")
            snapshot = {name: InstalledPackage(**item) for name, item in before.items()}
        return (
            cast(PackageFreshness, freshness),
            cast(OperationResult, result),
            snapshot,
        )

    def save(
        self,
        freshness: PackageFreshness,
        result: OperationResult,
        restart_before: dict[str, InstalledPackage] | None,
    ) -> None:
        temporary = self.path.with_suffix(".tmp")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with temporary.open("w") as output:
                before = (
                    None
                    if restart_before is None
                    else {
                        name: {"version": item.version, "state": item.state}
                        for name, item in restart_before.items()
                    }
                )
                json.dump(
                    {
                        "freshness": freshness,
                        "lastResult": result,
                        "restartBefore": before,
                    },
                    output,
                )
                output.flush()
                os.fsync(output.fileno())
            temporary.replace(self.path)
            directory = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)
