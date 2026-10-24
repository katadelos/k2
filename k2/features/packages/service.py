"""Installed application metadata and package-owned feature discovery."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ...core.packages import Application, CatalogPackage, FeatureCatalog, PackageFeature
from ...core.ports import ApplicationsBackend
from .applications import describe_application, empty_application
from .discovery import discover_features


class ApplicationDevice(Protocol):
    sdk: Path
    family: str


class ApplicationLauncher(Protocol):
    def launch_application(self, argv: list[str]) -> None: ...


class ApplicationService:
    def __init__(self, device: ApplicationDevice, launcher: ApplicationLauncher):
        self.root = device.sdk
        self.family = device.family
        self.launcher = launcher

    def application(self, package: CatalogPackage, files: list[str]) -> Application:
        return describe_application(package, files, self.root)

    def features(
        self,
        catalog: Sequence[CatalogPackage],
        package_files: Callable[[str], list[str]],
    ) -> FeatureCatalog:
        return discover_features(catalog, package_files, self.root, self.family)

    def launch_application(self, argv: list[str]) -> None:
        self.launcher.launch_application(argv)


@dataclass(frozen=True)
class CatalogMetadata:
    features: tuple[PackageFeature, ...]
    errors: tuple[str, ...]
    applications: dict[str, Application]


def read_catalog_metadata(
    service: ApplicationsBackend,
    catalog: Sequence[CatalogPackage],
    package_files: Callable[[str], list[str]],
) -> CatalogMetadata:
    """Read captured catalogue data and filesystem metadata outside the GUI thread."""
    file_cache: dict[str, list[str]] = {}
    errors: dict[str, str] = {}

    def files(name: str) -> list[str]:
        if name not in file_cache:
            try:
                file_cache[name] = package_files(name)
            except (OSError, ValueError) as error:
                errors[name] = f"Could not read package files: {error}"
                file_cache[name] = []
        return file_cache[name]

    discovered = service.features(catalog, files)
    control_packages = {
        feature["package"]
        for feature in discovered["items"]
        if feature["kind"] != "application"
    }
    applications: dict[str, Application] = {}
    for package in catalog:
        name = package["name"]
        package_paths = files(name) if package["installed"] else []
        try:
            application = service.application(package, package_paths)
        except (OSError, ValueError) as error:
            errors[name] = f"Could not read application metadata: {error}"
            application = empty_application(name)
        if name in errors:
            application = empty_application(name, errors[name])
        elif name in control_packages:
            application["instructions"] = "This package adds controls to Device."
        applications[name] = application
    return CatalogMetadata(
        tuple(discovered["items"]),
        (
            *discovered["errors"],
            *(f"{name}: {error}" for name, error in errors.items()),
        ),
        applications,
    )
