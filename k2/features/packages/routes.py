from pathlib import Path
from typing import TYPE_CHECKING

from ...ui.navigation import Route

if TYPE_CHECKING:
    from .viewmodel import PackagesViewModel


def routes(model: PackagesViewModel) -> list[Route]:
    directory = Path(__file__).parent / "qml"
    return [
        Route(
            "apps",
            "App Store",
            str(directory / "AppsPage.qml"),
            model,
            enter=model.refreshFeatured,
        ),
        Route("package", "Package details", str(directory / "PackagePage.qml"), model),
        Route(
            "activity",
            lambda: (
                "Update"
                if model.operation.get("action") in {"update", "upgrade"}
                else "Activity"
            ),
            str(directory / "ActivityPage.qml"),
            model,
        ),
    ]
