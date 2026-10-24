from pathlib import Path
from typing import TYPE_CHECKING

from ...ui.navigation import Route

if TYPE_CHECKING:
    from .viewmodel import FilesViewModel


def routes(model: FilesViewModel) -> list[Route]:
    return [
        Route(
            "files",
            "Files",
            str(Path(__file__).parent / "qml/FilesPage.qml"),
            model,
            enter=model.enter,
            leave=model.leave,
        )
    ]
