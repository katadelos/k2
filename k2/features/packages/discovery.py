"""Device controls supplied by installed packages, with explicit UI protocols."""

import json
import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from ...core.packages import (
    CatalogPackage,
    FeatureCatalog,
    FeaturePopover,
    PackageFeature,
)
from .applications import describe_application

IDENTIFIER = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9.+_-]*\Z")
KINDS = {"remote-access", "application", "file-sharing"}
# Names rendered by KIcon.qml; descriptors cannot supply executable QML or paths.
POPOVER_ICONS = {
    "apps",
    "device",
    "usb",
    "folder",
    "info",
    "arrow",
    "back",
    "shift",
    "backspace",
    "search",
    "refresh",
    "download",
    "exit",
    "check",
    "close",
    "battery",
    "terminal",
    "trash",
    "storage",
    "settings",
    "wifi",
    "brightness",
    "home",
}


def _read_descriptor(path: Path, owner: str) -> dict[str, Any]:
    if path.stat().st_size > 16384:
        raise ValueError("feature definition is too large")
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValueError("unsupported feature definition")
    if data.get("id") != owner or not IDENTIFIER.fullmatch(owner):
        raise ValueError("feature identifier must match its package")
    if data.get("kind") not in KINDS:
        raise ValueError("unsupported feature kind")
    platforms = data.get("platforms")
    if not isinstance(platforms, list) or any(
        p not in {"kindle", "kobo"} for p in platforms
    ):
        raise ValueError("invalid supported platforms")
    return data


def _executable(data: dict[str, Any], owned: set[str]) -> str:
    owner, kind, platforms = data["id"], data["kind"], data["platforms"]
    executable = data.get("executable", "")
    if (
        not isinstance(executable, str)
        or not executable.startswith("/")
        or ".." in PurePosixPath(executable).parts
        or "\0" in executable
        or executable not in owned
    ):
        raise ValueError("feature executable must belong to its package")
    if kind == "file-sharing" and (
        owner != "k2-fileshare"
        or platforms != ["kindle"]
        or executable != "/usr/bin/k2-fileshare"
    ):
        raise ValueError("invalid Kindle file-sharing feature")
    if owner == "k2-vnc" and (
        kind != "remote-access"
        or platforms != ["kindle"]
        or executable != "/usr/bin/k2-vnc"
    ):
        raise ValueError("invalid Kindle screen-sharing feature")
    return executable


def _popover(value: object) -> FeaturePopover:
    if not isinstance(value, dict) or set(value) - {"icon", "order"}:
        raise ValueError("invalid feature popover definition")
    icon, order = value.get("icon", "settings"), value.get("order", 100)
    if not isinstance(icon, str) or icon not in POPOVER_ICONS:
        raise ValueError("invalid feature popover icon")
    if type(order) is not int or not -(2**31) <= order < 2**31:
        raise ValueError("invalid feature popover order")
    return {"icon": icon, "order": order}


def _feature(
    data: dict[str, Any], owned: set[str], package: CatalogPackage, root: Path
) -> PackageFeature:
    executable = _executable(data, owned)
    for key in ("title", "description"):
        if (
            not isinstance(data.get(key), str)
            or not data[key].strip()
            or len(data[key]) > 512
        ):
            raise ValueError("invalid feature " + key)
    feature: PackageFeature = {
        "id": data["id"],
        "kind": data["kind"],
        "title": data["title"],
        "description": data["description"],
        "executable": executable,
        "package": data["id"],
    }
    if data["kind"] == "application":
        application = describe_application(package, owned, root)
        if not application["canOpen"] or application["argv"][0] != executable:
            raise ValueError(
                "application feature needs a matching package-owned launch entry"
            )
    if "popover" in data:
        feature["popover"] = _popover(data["popover"])
    return feature


def discover_features(
    catalog: Sequence[CatalogPackage],
    package_files: Callable[[str], list[str]],
    root: Path,
    family: str,
) -> FeatureCatalog:
    installed = {
        p["name"]: p for p in catalog if p.get("installed") and p.get("configured")
    }
    features: list[PackageFeature] = []
    errors: list[str] = []
    for path in sorted((root / "usr/share/k2/features").glob("*.json")):
        owner = path.stem
        if owner not in installed:
            continue
        try:
            owned = set(package_files(owner))
            if "/usr/share/k2/features/" + path.name not in owned:
                continue
            data = _read_descriptor(path, owner)
            if family in data["platforms"]:
                features.append(_feature(data, owned, installed[owner], root))
        except (OSError, ValueError, TypeError) as error:
            errors.append(f"{owner}: {error}")
    return {"items": features, "errors": errors}
