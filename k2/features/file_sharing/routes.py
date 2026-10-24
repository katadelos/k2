from pathlib import Path
from typing import TYPE_CHECKING

from ...ui.navigation import Route

if TYPE_CHECKING:
    from .viewmodel import FileSharingViewModel


def routes(model: FileSharingViewModel) -> list[Route]:
    return [
        Route(
            "file-sharing",
            "File Sharing",
            str(Path(__file__).parent / "qml/FileSharingPage.qml"),
            model,
            enter=model.enter,
            leave=model.leave,
            available=lambda: model.available,
        )
    ]
