"""The only place that constructs and connects production or simulated services."""

from pathlib import Path

from ..adapters.device import Device
from ..core.packages import PackageFeature
from ..core.ports import (
    ApplicationsBackend,
    DeviceBackend,
    PackageBackend,
    RemoteAccessBackend,
)
from ..features.device.routes import routes as device_routes
from ..features.device.viewmodel import DeviceViewModel
from ..features.file_sharing.ports import FileSharingBackend
from ..features.file_sharing.routes import routes as sharing_routes
from ..features.file_sharing.service import (
    FileSharingService,
)
from ..features.file_sharing.viewmodel import FileSharingViewModel
from ..features.files.routes import routes as file_routes
from ..features.files.service import FileService
from ..features.files.viewmodel import FilesViewModel
from ..features.koreader.routes import routes as reader_routes
from ..features.koreader.service import ReaderService
from ..features.koreader.viewmodel import KOReaderViewModel
from ..features.packages.featured import FeaturedCatalog, catalog_url
from ..features.packages.routes import routes as package_routes
from ..features.packages.viewmodel import PackagesViewModel
from ..features.remote_access.routes import routes as remote_routes
from ..features.remote_access.viewmodel import RemoteAccessViewModel
from ..ui.confirmations import Confirmations
from ..ui.navigation import Navigation, Route
from ..ui.operations import Operations
from .shell import AppShell


def compose(
    backend: PackageBackend,
    device: DeviceBackend,
    applications: ApplicationsBackend,
    reader_service: ReaderService,
    remote_service: RemoteAccessBackend,
    file_service: FileService,
    *,
    sharing_service: FileSharingBackend,
    page: str = "home",
) -> AppShell:
    navigation = Navigation()
    operations = Operations()
    confirmations = Confirmations(operations)
    featured = FeaturedCatalog(catalog_url())
    packages = PackagesViewModel(
        backend,
        applications,
        device,
        navigation,
        operations,
        confirmations,
        featured=featured,
    )
    reader = KOReaderViewModel(reader_service, navigation, operations, confirmations)
    remote = RemoteAccessViewModel(
        remote_service, device.family, navigation, operations, confirmations
    )
    controls = DeviceViewModel(device, operations)
    files = FilesViewModel(file_service, navigation, operations, confirmations)
    sharing = FileSharingViewModel(
        sharing_service,
        navigation,
        operations,
        confirmations,
    )
    shell = AppShell(
        device=device,
        packages=packages,
        reader=reader,
        remote=remote,
        controls=controls,
        files=files,
        sharing=sharing,
        navigation=navigation,
        operations=operations,
        confirmations=confirmations,
    )
    for routes in (
        package_routes(packages),
        reader_routes(reader),
        remote_routes(remote),
        device_routes(controls),
        file_routes(files),
        sharing_routes(sharing),
    ):
        for route in routes:
            navigation.register(route)
    directory = Path(__file__).parents[1] / "ui/shell"
    for name, title, qml in [
        ("home", "k2", "HomePage.qml"),
        ("about", "About k2", "AboutPage.qml"),
    ]:
        navigation.register(Route(name, title, str(directory / qml), shell))
    packages.exitRequested.connect(shell.exitRequested)
    packages.restartRequested.connect(shell.quit)
    reader.exitRequested.connect(shell.exitRequested)

    def select_feature(feature: PackageFeature) -> None:
        if feature["kind"] == "file-sharing":
            sharing.select(feature)
        elif feature["kind"] == "remote-access":
            remote.select(feature)

    packages.featureRequested.connect(select_feature)
    controls.controlsOpenChanged.connect(
        lambda: reader.popoverChanged(controls.controlsOpen)
    )
    remote.settled.connect(reader.refreshShortcut)
    navigation.routeActivated.connect(controls.closeControls)

    def catalog_changed() -> None:
        remote.set_catalog(packages.features, packages.catalogWarning)
        sharing.set_catalog(packages.features, packages.catalogWarning)
        reader.catalogChanged()

    packages.catalogChanged.connect(catalog_changed)
    navigation.start(page)
    return shell


def create_device_app(backend: PackageBackend, device: Device) -> AppShell:
    from ..adapters.launcher import Launcher
    from ..features.koreader.customise import CustomiseManager
    from ..features.koreader.manager import KOReaderManager
    from ..features.koreader.plugins import PluginManager
    from ..features.koreader.previews import load_preview
    from ..features.packages.service import ApplicationService
    from ..features.remote_access.service import RemoteAccessService

    launcher = Launcher(device)
    reader = ReaderService(
        KOReaderManager(device),
        PluginManager,
        lambda root: CustomiseManager(root, device.snapshot()),
        lambda item: load_preview(item, device.sdk / "cache/koreader-previews"),
        launcher.launch_koreader,
    )
    return compose(
        backend,
        device,
        ApplicationService(device, launcher),
        reader,
        RemoteAccessService(device.family),
        FileService.for_device(device.family),
        sharing_service=FileSharingService(),
    )
