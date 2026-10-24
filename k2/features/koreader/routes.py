from pathlib import Path
from typing import TYPE_CHECKING

from ...ui.navigation import Route

if TYPE_CHECKING:
    from .viewmodel import KOReaderViewModel


def routes(model: KOReaderViewModel) -> list[Route]:
    directory = Path(__file__).parent / "qml"
    return [
        Route(
            "koreader",
            "KOReader",
            str(directory / "KOReaderPage.qml"),
            model,
            enter=model.refreshReader,
        ),
        Route(
            "koreader-plugins",
            "KOReader plugins",
            str(directory / "KOReaderPluginsPage.qml"),
            model,
            enter=model.refreshReaderPlugins,
        ),
        Route(
            "koreader-customise",
            "Customise KOReader",
            str(directory / "KOReaderCustomisePage.qml"),
            model,
            enter=model.refreshReaderCustomisations,
        ),
        Route(
            "koreader-customisation",
            "Customisation details",
            str(directory / "KOReaderCustomisationPage.qml"),
            model,
        ),
    ]
