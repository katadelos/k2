from pathlib import Path

from ...ui.navigation import Route
from .viewmodel import DeviceViewModel


def routes(model: DeviceViewModel) -> list[Route]:
    directory = Path(__file__).parent / "qml"
    return [
        Route(
            "device",
            "Device",
            str(directory / "DevicePage.qml"),
            model,
            enter=model.refreshInfo,
        ),
        Route(
            "storage",
            "Storage",
            str(directory / "StoragePage.qml"),
            model,
            enter=model.refreshInfo,
        ),
    ]
