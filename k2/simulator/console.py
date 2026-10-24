"""Headless commands bound directly to the composed feature models."""

from ..app.shell import AppShell
from ..ui.console import JsonConsole
from ..ui.runtime import Runtime
from .state import snapshot


class Console(JsonConsole):
    def __init__(self, runtime: Runtime) -> None:
        c = runtime.controller
        if not isinstance(c, AppShell):
            raise TypeError("The simulator console requires an attached application")
        commands = {
            "navigate": lambda r: c.navigation.navigate(r["page"]),
            "back": lambda r: c.back(),
            "retry": lambda r: c.packages.retry(),
            "tab": lambda r: c.packages.setTab(r["value"]),
            "search": lambda r: c.packages.search(r["text"]),
            "featured-refresh": lambda r: c.packages.featured.refresh(),
            "featured-open": lambda r: c.packages.openFeatured(r["name"]),
            "controls": lambda r: c.controls.toggleControls(),
            "wifi": lambda r: c.controls.setWifi(bool(r["enabled"])),
            "brightness": lambda r: c.controls.setBrightness(r["value"]),
            "feature": lambda r: c.packages.selectFeature(r["name"]),
            "feature-action": lambda r: c.remote.changeFeature(r["action"]),
            "feature-transport": lambda r: c.remote.setFeatureTransport(r["value"]),
            "feature-refresh": lambda r: c.remote.refreshFeature(),
            "reader-refresh": lambda r: c.reader.refreshReader(),
            "reader-release": lambda r: c.reader.checkReaderRelease(),
            "reader-select": lambda r: c.reader.selectReaderInstallation(r["path"]),
            "reader-request": lambda r: c.reader.requestReader(
                r["action"], r.get("value", "")
            ),
            "reader-plugins": lambda r: c.reader.refreshReaderPlugins(),
            "reader-customise": lambda r: c.reader.refreshReaderCustomisations(
                bool(r.get("online", False))
            ),
            "reader-customisation": lambda r: c.reader.selectReaderCustomisation(
                r["name"]
            ),
            "reader-customise-tab": lambda r: c.reader.setReaderCustomiseTab(
                r["value"]
            ),
            "reader-customise-action": lambda r: c.reader.requestReaderCustomisation(
                r["action"]
            ),
            "reader-preview": lambda r: c.reader.loadReaderPreview(),
            "select": lambda r: c.packages.selectPackage(r["name"]),
            "request": lambda r: c.packages.request(r["action"], r.get("name", "")),
            "confirm": lambda r: c.confirmations.confirm(),
            "cancel": lambda r: c.confirmations.cancel(),
            "quit": lambda r: c.quit(),
        }
        super().__init__(runtime, snapshot, commands)
