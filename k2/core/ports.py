"""Backend contracts used by the feature models and simulator."""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, NotRequired, Protocol, TypedDict

from .packages import (
    Application,
    CatalogPackage,
    FeatureCatalog,
    PackageFeature,
    PackageFreshness,
)


class Signal(Protocol):
    def connect(self, slot: Callable[..., None]) -> None: ...


class Feed(TypedDict):
    name: str
    url: str


class DeviceInfo(TypedDict):
    family: str
    model: str
    firmware: str
    kernel: str
    architecture: str
    battery: str
    free: str
    total: str
    usedFraction: float
    store: str
    sdk: str
    feeds: list[Feed]
    launcher: str


class CapabilityState(TypedDict, total=False):
    supported: bool
    implemented: bool
    available: bool
    blocked: bool
    error: int
    minimum: int
    maximum: int
    steps: int
    reason_code: int
    reason: str


class LightState(CapabilityState):
    value: int


class BatteryState(CapabilityState):
    percent: int | None
    charging: bool


class WifiStatus(CapabilityState):
    enabled: bool | None
    connected: bool | None
    ssid: str
    status: str
    detail: str
    connection_available: NotRequired[bool]
    connection_error: NotRequired[int]
    network_id: NotRequired[str]
    address: NotRequired[str]
    bssid: NotRequired[str]


class OperationResult(TypedDict, total=False):
    action: str
    name: str
    state: str
    message: str
    log: str
    catalogError: str
    startedAt: int
    finishedAt: int
    restartRequired: bool
    restartReaderRequired: bool
    restartAutomatic: bool
    restartUncertain: bool
    reloadKppRequired: bool


class DeviceBackend(Protocol):
    family: str

    def snapshot(self) -> DeviceInfo: ...
    def brightness(self) -> LightState: ...
    def set_brightness(self, value: int) -> LightState: ...
    def warmth(self) -> LightState: ...
    def set_warmth(self, value: int) -> LightState: ...
    def battery(self) -> BatteryState: ...
    def capability(self, name: str) -> CapabilityState: ...
    def capabilities(self) -> dict[str, CapabilityState]: ...
    def close(self) -> None: ...
    def wifi(self) -> WifiStatus: ...
    def set_wifi(self, enabled: bool) -> WifiStatus: ...
    def network_available(self) -> bool: ...
    def set_active(self, active: bool) -> None: ...


class PackageBackend(Protocol):
    config_dir: Path | None
    catalogChanged: Signal
    activityChanged: Signal
    logChanged: Signal
    resultChanged: Signal
    planned: Signal
    finished: Signal
    restartRequested: Signal
    catalog: list[CatalogPackage]
    busy: bool
    status: str
    progress: float
    log: str
    freshness: PackageFreshness
    last_result: OperationResult
    catalog_error: str
    state_error: str

    def refresh(self) -> None: ...
    def package_files(self, name: str) -> list[str]: ...
    def plan(self, action: str, name: str) -> None: ...
    def perform(self, action: str, name: str = "") -> None: ...


class ApplicationsBackend(Protocol):
    def application(self, package: CatalogPackage, files: list[str]) -> Application: ...
    def features(
        self,
        catalog: Sequence[CatalogPackage],
        package_files: Callable[[str], list[str]],
    ) -> FeatureCatalog: ...
    def launch_application(self, argv: list[str]) -> None: ...


class RemoteAccessBackend(Protocol):
    def feature_status(self, feature: PackageFeature) -> dict[str, Any]: ...
    def change_feature(
        self, feature: PackageFeature, action: str
    ) -> dict[str, Any]: ...
