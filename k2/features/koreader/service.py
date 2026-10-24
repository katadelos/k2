"""Synchronous KOReader operations, called by the feature's worker runner."""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Self

from .ports import CustomisationBackend, PluginBackend, ReaderBackend


class PluginAction(StrEnum):
    INSTALL = "install"
    REMOVE = "remove"


class CustomisationAction(StrEnum):
    INSTALL = "install"
    REMOVE = "remove"
    ENABLE = "enable"
    DISABLE = "disable"


@dataclass(frozen=True)
class ReaderSelection:
    path: str
    installed: bool


@dataclass(frozen=True)
class InstallationRequest:
    selection: ReaderSelection
    release_version: str


@dataclass(frozen=True)
class RemovalRequest:
    selection: ReaderSelection
    identity: tuple[int, ...]


@dataclass(frozen=True)
class PluginRequest:
    selection: ReaderSelection
    action: PluginAction
    value: str


@dataclass(frozen=True)
class CustomisationRequest:
    selection: ReaderSelection
    action: CustomisationAction
    item_id: str


@dataclass(frozen=True)
class ReaderSnapshot:
    values: dict
    message: str = ""


@dataclass(frozen=True)
class PluginSnapshot:
    items: list[dict]
    message: str = ""


@dataclass(frozen=True)
class CustomisationSnapshot:
    items: list[dict]
    checked_at: int = 0
    error: str = ""
    message: str = field(default="", compare=False)

    @classmethod
    def from_backend(cls, values: dict) -> Self:
        return cls(
            items=values["items"],
            checked_at=values.get("checkedAt", 0),
            error=values.get("error", ""),
            message=values.get("message", ""),
        )


@dataclass(frozen=True)
class CustomisationPlan:
    title: str
    label: str
    body: str
    ready: bool


@dataclass(frozen=True)
class CustomisationPreview:
    item_id: str
    url: str


class ReaderService:
    """Own backend caches; feature models only pass captured request values.

    Worker operations are serialised by the view model's TaskRunner. Launching
    is allowed only while it is idle, so backend managers are never concurrent.
    """

    def __init__(
        self,
        manager: ReaderBackend,
        plugins: Callable[[str], PluginBackend],
        customise: Callable[[str], CustomisationBackend],
        preview: Callable[[str], str],
        launch: Callable[[list[str], list[str]], None],
    ) -> None:
        self.manager = manager
        self._create_plugins = plugins
        self._create_customise = customise
        self._load_preview = preview
        self._launch = launch
        self._backend_path = ""
        self._plugins: PluginBackend | None = None
        self._customise: CustomisationBackend | None = None

    def status(self) -> ReaderSnapshot:
        return ReaderSnapshot(self.manager.status())

    def check_release(self) -> ReaderSnapshot:
        return ReaderSnapshot(self.manager.check_release())

    def select_installation(self, path: str) -> ReaderSnapshot:
        return ReaderSnapshot(self.manager.select_installation(path))

    def install(self, request: InstallationRequest) -> ReaderSnapshot:
        values = self._verify_selection(request.selection)
        if values.get("releaseVersion", "") != request.release_version:
            raise ValueError(
                "The selected KOReader release changed. Check the release and try again."
            )
        self._plugins = None
        self._customise = None
        return ReaderSnapshot(
            self.manager.install(),
            "KOReader is installed. Your books and settings are kept.",
        )

    def uninstall(self, request: RemovalRequest) -> ReaderSnapshot:
        self._verify_selection(request.selection)
        values = self.manager.uninstall(request.identity)
        self._plugins = None
        self._customise = None
        self._backend_path = ""
        return ReaderSnapshot(values, "KOReader and its plugins have been removed.")

    def add_scriptlet(self, selection: ReaderSelection) -> ReaderSnapshot:
        self._verify_selection(selection)
        return ReaderSnapshot(
            self.manager.add_scriptlet(),
            "KOReader is available in your Kindle library and KPP Mods.",
        )

    def _select_backend(self, selection: ReaderSelection, purpose: str) -> None:
        if not selection.installed or not selection.path:
            raise ValueError(f"Install or select KOReader before {purpose}.")
        self._verify_selection(selection)
        if self._backend_path != selection.path:
            self._backend_path = selection.path
            self._plugins = None
            self._customise = None

    def _plugin_backend(self, selection: ReaderSelection) -> PluginBackend:
        self._select_backend(selection, "managing plugins")
        if self._plugins is None:
            self._plugins = self._create_plugins(selection.path)
        return self._plugins

    def _customisation_backend(
        self, selection: ReaderSelection
    ) -> CustomisationBackend:
        self._select_backend(selection, "customising it")
        if self._customise is None:
            self._customise = self._create_customise(selection.path)
        return self._customise

    def list_plugins(self, selection: ReaderSelection) -> PluginSnapshot:
        return PluginSnapshot(self._plugin_backend(selection).list_installed())

    def change_plugin(self, request: PluginRequest) -> PluginSnapshot:
        backend = self._plugin_backend(request.selection)
        if request.action is PluginAction.INSTALL:
            result = backend.install(request.value)
        else:
            result = backend.remove(request.value)
        return PluginSnapshot(
            items=backend.list_installed(),
            message=result.get(
                "message", "Plugin changed. Restart KOReader to apply it."
            ),
        )

    def list_customisations(
        self, selection: ReaderSelection, *, online: bool = False
    ) -> CustomisationSnapshot:
        values = self._customisation_backend(selection).snapshot(refresh=online)
        return CustomisationSnapshot.from_backend(values)

    def plan_customisation(self, request: CustomisationRequest) -> CustomisationPlan:
        values = self._customisation_backend(request.selection).plan(
            request.action.value,
            request.item_id,
        )
        return CustomisationPlan(**values)

    def change_customisation(
        self, request: CustomisationRequest
    ) -> CustomisationSnapshot:
        values = self._customisation_backend(request.selection).apply(
            request.action.value,
            request.item_id,
        )
        return CustomisationSnapshot.from_backend(values)

    def load_preview(self, item_id: str) -> CustomisationPreview:
        return CustomisationPreview(item_id, self._load_preview(item_id))

    def _verify_selection(self, selection: ReaderSelection) -> dict:
        values = self.manager.status()
        current = ReaderSelection(values.get("path", ""), bool(values.get("installed")))
        if current != selection:
            raise ValueError(
                "The selected KOReader installation changed. Refresh and try again."
            )
        return values

    def open_reader(self, selection: ReaderSelection) -> None:
        self._verify_selection(selection)
        argv = self.manager.launch_command()
        self._launch(argv, argv)
