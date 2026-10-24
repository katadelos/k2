"""Compose the application with explicit simulated backends."""

from ..app.bootstrap import compose
from ..app.shell import AppShell
from ..core.ports import PackageBackend
from ..features.files.service import FileService
from ..features.koreader.service import ReaderService
from .backends.device import SimulatedDevice
from .backends.file_sharing import SimulatedFileSharingService


def create_simulated_app(
    backend: PackageBackend, device: SimulatedDevice, page: str = "home"
) -> AppShell:
    reader = ReaderService(
        device.koreader_manager(),
        device.koreader_plugins,
        device.koreader_customise,
        device.koreader_preview,
        lambda argv, expected: device.launch_koreader(argv),
    )
    return compose(
        backend,
        device,
        device,
        reader,
        device,
        FileService.demo(),
        sharing_service=SimulatedFileSharingService(),
        page=page,
    )
