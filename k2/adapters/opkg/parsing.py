"""Decode opkg output without spawning commands or constructing Qt objects."""

import json
import re
from collections.abc import Iterable, Iterator
from typing import Any

from ...core.packages import RESTART_PACKAGES, PackageChange, PackagePlan

PACKAGE_NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9.+_-]*\Z")


def package_lines(output: str) -> Iterator[tuple[str, str, str]]:
    for line in output.splitlines():
        fields = line.split(" - ", 2)
        if len(fields) >= 2 and PACKAGE_NAME.fullmatch(fields[0]):
            yield fields[0], fields[1], fields[2] if len(fields) > 2 else ""


def control_records(output: str) -> Iterator[dict[str, str]]:
    """Read opkg control paragraphs, retaining complete multiline descriptions."""
    record: dict[str, str] = {}
    field = ""
    for line in [*output.splitlines(), ""]:
        if not line.strip():
            if PACKAGE_NAME.fullmatch(record.get("Package", "")):
                yield record
            record, field = {}, ""
        elif line[0].isspace() and field:
            record[field] += "\n" + ("" if line.strip() == "." else line[1:])
        elif ": " in line:
            field, value = line.split(": ", 1)
            record[field] = value


def _optional_text(record: dict[str, Any], key: str) -> str | None:
    value = record.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"Invalid {key} returned by opkg.")
    return value


def _optional_size(record: dict[str, Any], key: str) -> int | None:
    value = record.get(key)
    if value is not None and type(value) is not int:
        raise ValueError(f"Invalid {key} returned by opkg.")
    return value


def _change(record: dict[str, Any]) -> PackageChange:
    action, name = record.get("action"), record.get("name")
    if (
        action not in {"install", "upgrade", "remove", "configure"}
        or not isinstance(name, str)
        or not PACKAGE_NAME.fullmatch(name)
    ):
        raise ValueError("Invalid package change returned by opkg.")
    return PackageChange(
        action=action,
        name=name,
        from_version=_optional_text(record, "fromVersion"),
        to_version=_optional_text(record, "toVersion"),
        download_bytes=_optional_size(record, "downloadBytes"),
        installed_delta_bytes=_optional_size(record, "installedDeltaBytes"),
    )


def _total(values: Iterable[int | None]) -> int | None:
    total = 0
    for value in values:
        if value is None:
            return None
        total += value
    return total


def parse_plan(output: str) -> PackagePlan:
    by_package: dict[tuple[str, str], PackageChange] = {}
    complete = False
    for line in output.splitlines():
        if not line.startswith("OPKG_PLAN "):
            continue
        record = json.loads(line[len("OPKG_PLAN ") :])
        if not isinstance(record, dict) or record.get("schema") != 1:
            raise ValueError("Unsupported opkg plan format.")
        if record.get("complete"):
            complete = True
            continue
        change = _change(record)
        by_package[(change.name, change.action)] = change
    if not complete:
        raise ValueError("opkg did not return a complete package plan.")
    changes = tuple(by_package.values())
    return PackagePlan(
        changes=changes,
        download_bytes=_total(item.download_bytes for item in changes),
        installed_delta_bytes=_total(item.installed_delta_bytes for item in changes),
        restart_required=any(
            item.name in RESTART_PACKAGES and item.action != "remove"
            for item in changes
        ),
        restart_reader_required=any(
            item.name == "k2-nickel" and item.action != "remove" for item in changes
        ),
    )
