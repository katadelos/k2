"""Package selection, filtering and pagination without Qt state."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from ...core.packages import CatalogPackage


@dataclass
class PackageBrowser:
    tab: str = "Featured"
    query: str = ""
    selection: str = ""
    page: int = 0
    page_size: int = 8
    packages: Sequence[CatalogPackage] = ()
    filtered: list[CatalogPackage] = field(default_factory=list)

    @property
    def page_count(self) -> int:
        return max(1, (len(self.filtered) + self.page_size - 1) // self.page_size)

    @property
    def rows(self) -> list[CatalogPackage]:
        start = self.page * self.page_size
        return self.filtered[start : start + self.page_size]

    @property
    def selected(self) -> CatalogPackage | None:
        return next(
            (item for item in self.packages if item["name"] == self.selection), None
        )

    def replace(self, packages: Sequence[CatalogPackage]) -> None:
        self.packages = packages
        query = self.query.casefold()
        self.filtered = [
            package
            for package in sorted(packages, key=lambda item: item["name"].casefold())
            if (self.tab != "Installed" or package["installed"])
            and (self.tab != "Updates" or package["update"])
            and query in (package["name"] + " " + package["summary"]).casefold()
        ]
        self.page = min(self.page, self.page_count - 1)

    def set_page(self, value: int) -> bool:
        page = min(max(0, value), self.page_count - 1)
        if page == self.page:
            return False
        self.page = page
        return True

    def resize(self, value: int) -> bool:
        value = max(1, value)
        if value == self.page_size:
            return False
        self.page_size = value
        self.page = min(self.page, self.page_count - 1)
        return True

    def set_tab(self, value: str) -> bool:
        if (
            value not in {"Featured", "All", "Installed", "Updates"}
            or value == self.tab
        ):
            return False
        self.tab = value
        if value == "Featured":
            self.query = ""
        self.page = 0
        self.replace(self.packages)
        return True

    def search(self, value: str) -> bool:
        if value == self.query and not (value and self.tab == "Featured"):
            return False
        self.query = value
        if value and self.tab == "Featured":
            self.tab = "All"
        self.page = 0
        self.replace(self.packages)
        return True
