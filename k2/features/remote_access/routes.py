from pathlib import Path
from typing import TYPE_CHECKING

from ...ui.navigation import Route

if TYPE_CHECKING:
    from .viewmodel import RemoteAccessViewModel


def routes(model: RemoteAccessViewModel) -> list[Route]:
    directory = Path(__file__).parent / "qml"
    return [
        Route(
            "feature",
            "Developer tools",
            str(directory / "RemoteAccessPage.qml"),
            model,
            enter=model.enter,
            leave=model.leave,
            available=lambda: bool(model.feature),
        ),
    ]
