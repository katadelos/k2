"""Package transaction values and protection policy."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, NotRequired, Self, TypedDict


class CatalogPackage(TypedDict):
    name: str
    version: str
    summary: str
    installed: str
    update: str
    available: bool
    protected: bool
    configured: bool
    description: NotRequired[str]
    metadata: NotRequired[dict[str, str]]
    installState: NotRequired[str]


class Application(TypedDict):
    name: str
    instructions: str
    argv: list[str]
    canOpen: bool
    commands: list[str]
    error: str


class FeaturePopover(TypedDict):
    icon: str
    order: int


class PackageFeature(TypedDict):
    id: str
    kind: Literal["application", "remote-access", "file-sharing"]
    title: str
    description: str
    executable: str
    package: str
    popover: NotRequired[FeaturePopover]


class FeatureCatalog(TypedDict):
    items: list[PackageFeature]
    errors: list[str]


class PackageFreshness(TypedDict):
    lastRefresh: int
    error: str


@dataclass(frozen=True)
class InstalledPackage:
    version: str
    state: str


class RestartFlags(TypedDict):
    restartRequired: bool
    restartReaderRequired: bool
    restartAutomatic: bool
    reloadKppRequired: bool


@dataclass(frozen=True)
class PackageRequest:
    action: str
    name: str = ""


@dataclass(frozen=True)
class PackageChange:
    action: str
    name: str
    from_version: str | None = None
    to_version: str | None = None
    download_bytes: int | None = None
    installed_delta_bytes: int | None = None

    def to_mapping(self) -> dict[str, str | int | None]:
        return {
            "action": self.action,
            "name": self.name,
            "fromVersion": self.from_version,
            "toVersion": self.to_version,
            "downloadBytes": self.download_bytes,
            "installedDeltaBytes": self.installed_delta_bytes,
        }


@dataclass(frozen=True)
class PackagePlan:
    changes: tuple[PackageChange, ...] = ()
    download_bytes: int | None = None
    installed_delta_bytes: int | None = None
    restart_required: bool = False
    restart_reader_required: bool = False
    error: str = ""

    @property
    def reload_kpp_required(self) -> bool:
        return any(is_kpp_package(change.name) for change in self.changes) and not any(
            change.name == "kppmods" and change.action == "remove"
            for change in self.changes
        )

    @property
    def restart_automatically(self) -> bool:
        return not self.restart_reader_required and any(
            change.name == "k2" and change.action in {"install", "upgrade"}
            for change in self.changes
        )


@dataclass(frozen=True)
class PackageRecord:
    name: str
    version: str
    summary: str
    installed: str
    update: str
    available: bool
    protected: bool
    configured: bool

    @classmethod
    def from_mapping(cls, row: CatalogPackage) -> Self:
        return cls(
            name=row["name"],
            version=row["version"],
            summary=row["summary"],
            installed=row["installed"],
            update=row["update"],
            available=row["available"],
            protected=row["protected"],
            configured=row["configured"],
        )


# Removing these would break the running package manager. Opkg checks other
# reverse dependencies itself; k2 never supplies force options.
PROTECTED = {
    "k2",
    "opkg",
    "python3",
    "python-pyqt5",
    "python-pyqt5-sip",
    "qt5base",
    "qt5declarative",
    "qt5quickcontrols2",
}
RESTART_PACKAGES = PROTECTED | {"qt5-kobo-platform", "fbink"}


def is_kpp_package(name: str) -> bool:
    return name == "kppmods" or name.startswith("kppmods-")


def restart_flags(
    before: Mapping[str, InstalledPackage], after: Mapping[str, InstalledPackage]
) -> RestartFlags:
    """Restart guidance follows installed changes, even after a partial failure."""
    changed = {
        name
        for name in before.keys() | after.keys()
        if before.get(name) != after.get(name)
    }
    kpp_removed = "kppmods" in before and "kppmods" not in after
    reader = "k2-nickel" in changed or kpp_removed
    runtime_ready = all(
        name in after and after[name].state == "installed"
        for name in changed & RESTART_PACKAGES
    )
    return {
        "restartRequired": bool(changed & RESTART_PACKAGES),
        "restartReaderRequired": reader,
        "restartAutomatic": bool("k2" in changed and runtime_ready and not reader),
        "reloadKppRequired": not kpp_removed
        and any(is_kpp_package(name) for name in changed),
    }
