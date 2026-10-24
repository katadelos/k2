"""Registered routes, persistent feature models and page lifecycle."""

from collections.abc import Callable
from dataclasses import dataclass

from PyQt5.QtCore import QObject, QUrl, pyqtProperty, pyqtSignal, pyqtSlot


def always_available() -> bool:
    return True


@dataclass(frozen=True)
class Route:
    name: str
    title: str | Callable[[], str]
    source: str
    model: QObject
    enter: Callable[[], None] | None = None
    leave: Callable[[], None] | None = None
    available: Callable[[], bool] = always_available


class Navigation(QObject):
    changed = pyqtSignal()
    routeChanged = pyqtSignal()
    routeActivated = pyqtSignal()
    titleChanged = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._routes: dict[str, Route] = {}
        self._page = ""
        self._title = ""
        self._history: list[str] = []

    def register(self, route: Route) -> None:
        if route.name in self._routes:
            raise ValueError("Duplicate route: " + route.name)
        self._routes[route.name] = route
        if callable(route.title):
            route.model.changed.connect(self._refresh_title)

    @pyqtProperty(str, notify=routeChanged)
    def page(self):
        return self._page

    @pyqtProperty(str, notify=titleChanged)
    def title(self):
        return self._title

    @pyqtProperty(QUrl, notify=routeChanged)
    def source(self):
        return QUrl.fromLocalFile(self._routes[self._page].source)

    @pyqtProperty(QObject, notify=routeChanged)
    def model(self):
        return self._routes[self._page].model

    @pyqtSlot()
    def _refresh_title(self):
        route = self._routes.get(self._page)
        if route is None:
            return
        title = route.title() if callable(route.title) else route.title
        if title != self._title:
            self._title = title
            self.titleChanged.emit()
            self.changed.emit()

    def start(self, page: str) -> None:
        if self._page:
            raise RuntimeError("Navigation has already started")
        route = self._routes.get(page)
        if route is None or not route.available():
            raise ValueError("Unavailable initial route: " + page)
        self._activate(page)

    @pyqtSlot(str)
    def navigate(self, page):
        route = self._routes.get(page)
        if route is None or not route.available():
            return
        if page == "home":
            self._history.clear()
        elif page != self._page:
            if page in self._history:
                self._history = self._history[: self._history.index(page)]
            elif self._page:
                self._history.append(self._page)
        self._activate(page)

    def _activate(self, page: str) -> None:
        previous = self._routes.get(self._page)
        if previous and previous.leave:
            previous.leave()
        route_changed = page != self._page
        self._page = page
        self._refresh_title()
        if route_changed:
            self.routeChanged.emit()
            self.changed.emit()
        self.routeActivated.emit()
        route = self._routes[page]
        if route.enter:
            route.enter()

    @pyqtSlot()
    def back(self):
        while self._history:
            page = self._history.pop()
            if self._routes[page].available():
                self._activate(page)
                return
        self._activate("home")
