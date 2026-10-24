"""KOReader presentation state and main-thread workflow coordination."""

from collections.abc import Callable
from datetime import datetime
from functools import partial
from typing import Any

from PyQt5.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from ...ui.confirmations import Confirmation, ConfirmationContent, Confirmations
from ...ui.navigation import Navigation
from ...ui.operations import Operation, Operations
from ...ui.tasks import TaskFailure, TaskRunner
from .actions import ReaderRequest, prepare_action
from .previews import PREVIEWS
from .service import (
    CustomisationAction,
    CustomisationPlan,
    CustomisationPreview,
    CustomisationRequest,
    CustomisationSnapshot,
    InstallationRequest,
    PluginRequest,
    PluginSnapshot,
    ReaderSelection,
    ReaderService,
    ReaderSnapshot,
    RemovalRequest,
)

_MUTATING_ACTIONS = {
    "install",
    "uninstall",
    "scriptlet",
    "plugin-install",
    "plugin-remove",
    "custom-install",
    "custom-remove",
    "custom-enable",
    "custom-disable",
}
_ACTIVITY_TITLES = {
    "status": "Looking for KOReader…",
    "popover-status": "Looking for KOReader…",
    "release": "Checking for updates…",
    "select": "Loading KOReader details…",
    "install": "Installing KOReader…",
    "uninstall": "Removing KOReader…",
    "scriptlet": "Adding library shortcut…",
    "plugins": "Loading plugins…",
    "plugin-install": "Installing plugin…",
    "plugin-remove": "Removing plugin…",
    "custom-list": "Loading customisations…",
    "custom-refresh": "Checking for updates…",
    "custom-plan": "Checking compatibility…",
    "custom-install": "Installing customisation…",
    "custom-remove": "Removing customisation…",
    "custom-enable": "Enabling customisation…",
    "custom-disable": "Disabling customisation…",
    "custom-preview": "Loading preview…",
}


class KOReaderViewModel(QObject):
    changed = pyqtSignal()
    readerChanged = pyqtSignal()
    pluginsChanged = pyqtSignal()
    customisationsChanged = pyqtSignal()
    customisationChanged = pyqtSignal()
    customiseFilterChanged = pyqtSignal()
    previewChanged = pyqtSignal()
    activityChanged = pyqtSignal()
    feedbackChanged = pyqtSignal()
    availabilityChanged = pyqtSignal()
    exitRequested = pyqtSignal()
    settled = pyqtSignal()

    def __init__(
        self,
        service: ReaderService,
        navigation: Navigation,
        operations: Operations,
        confirmations: Confirmations,
    ) -> None:
        super().__init__()
        self.service = service
        self.navigation = navigation
        self.operations = operations
        self.confirmations = confirmations
        self._state: dict = {}
        self._plugins: list[dict] = []
        self._customisations = CustomisationSnapshot(items=[])
        self._customise_tab = "All"
        self._customise_page = 0
        self._selected_customisation = ""
        self._previews: dict[str, str] = {}
        self._preview_error = ""
        self._error = ""
        self._message = ""
        self._popover_open = False
        self._shortcut_refresh_pending = False
        self._pending_customisation_refresh: bool | None = None
        self._pending_plugin_refresh = False
        self._failed_action = ""
        self._result_handler: Callable[[Any], None] | None = None
        self._failure_handler: Callable[[TaskFailure], None] | None = None
        self._runner = TaskRunner(self)
        self._runner.completed.connect(self._task_completed)
        self._runner.finished.connect(self._task_finished)
        self._runner.busyChanged.connect(self._activity_changed)
        self._activity = (False, False, "")
        self._availability = (self.canRead, self.canChange, self.canOpen)
        operations.changed.connect(self._operations_changed)
        confirmations.closed.connect(self._confirmation_closed)
        for signal in (
            self.readerChanged,
            self.pluginsChanged,
            self.customisationsChanged,
            self.customisationChanged,
            self.customiseFilterChanged,
            self.previewChanged,
            self.activityChanged,
            self.feedbackChanged,
            self.availabilityChanged,
        ):
            signal.connect(self.changed)

    @pyqtProperty(bool, notify=availabilityChanged)
    def canRead(self):
        return self.operations.allows({"reader"}, owner="reader")

    @pyqtProperty(bool, notify=availabilityChanged)
    def canChange(self):
        resources = {"reader", "packages", "network", "controls"}
        return not self.readerBusy and self.operations.allows(resources, owner="reader")

    @pyqtProperty(bool, notify=availabilityChanged)
    def canOpen(self):
        return not self.readerBusy and self.operations.allows(
            {"reader", "packages", "network"}, owner="reader"
        )

    @pyqtSlot()
    def _update_availability(self):
        availability = (self.canRead, self.canChange, self.canOpen)
        if availability != self._availability:
            self._availability = availability
            self.availabilityChanged.emit()

    @pyqtSlot()
    def _operations_changed(self):
        self._update_availability()
        self._resume_pending_refreshes(keep_feedback=True)

    @pyqtSlot()
    def _confirmation_closed(self):
        self._resume_pending_refreshes(keep_feedback=True)

    @pyqtSlot()
    def _activity_changed(self):
        operation = None
        if self.readerBusy:
            resources = (
                {"reader", "packages", "network", "controls"}
                if self.readerWorking
                else {"reader"}
            )
            operation = Operation(
                resources=frozenset(resources),
                working=self.readerWorking,
                title=self.readerActivity,
                route="koreader",
            )
        self.operations.update("reader", operation)
        self._update_availability()
        activity = (self.readerBusy, self.readerWorking, self.readerActivity)
        if activity != self._activity:
            self._activity = activity
            self.activityChanged.emit()

    def _selection(self):
        return ReaderSelection(
            path=self._state.get("path", ""),
            installed=bool(self._state.get("installed")),
        )

    def popoverChanged(self, opened):
        if opened and not self._popover_open:
            self._shortcut_refresh_pending = True
        self._popover_open = opened
        self.refreshShortcut()

    def catalogChanged(self):
        if (
            self.navigation.page == "koreader"
            and not self.readerBusy
            and not self._state
        ):
            self.refreshReader()
        elif self.navigation.page == "koreader-customise" and not self.readerBusy:
            self.refreshReaderCustomisations()
        elif self.navigation.page == "koreader-plugins" and not self.readerBusy:
            self.refreshReaderPlugins()
        self._resume_pending_refreshes(keep_feedback=True)
        self.refreshShortcut()

    def stop(self):
        self._popover_open = False
        self._shortcut_refresh_pending = False
        self._pending_customisation_refresh = None
        self._pending_plugin_refresh = False

    def close(self):
        self.stop()
        self._runner.wait()

    @pyqtProperty("QVariantMap", notify=readerChanged)
    def reader(self):
        return self._state

    @pyqtProperty(bool, notify=readerChanged)
    def popoverReaderAvailable(self):
        return bool(self._state.get("installations"))

    def refreshShortcut(self):
        if (
            not self._popover_open
            or not self._shortcut_refresh_pending
            or self.readerBusy
            or not self.canRead
            or self.confirmations.active
        ):
            return
        self._shortcut_refresh_pending = False
        self._start(
            "popover-status",
            self.service.status,
            self._apply_reader,
            keep_feedback=True,
            on_failure=self._ignore_shortcut_failure,
        )

    @pyqtProperty("QVariantList", notify=pluginsChanged)
    def readerPlugins(self):
        return self._plugins

    @pyqtProperty("QVariantList", notify=customisationsChanged)
    def readerCustomisations(self):
        return self._customisations.items

    @pyqtProperty("QVariantMap", notify=customisationChanged)
    def readerCustomisation(self):
        return next(
            (
                item
                for item in self._customisations.items
                if item["id"] == self._selected_customisation
            ),
            {},
        )

    @pyqtProperty(bool, notify=customisationChanged)
    def readerPreviewAvailable(self):
        return self._selected_customisation in PREVIEWS

    @pyqtProperty(str, notify=previewChanged)
    def readerPreview(self):
        return self._previews.get(self._selected_customisation, "")

    @pyqtProperty(str, notify=previewChanged)
    def readerPreviewError(self):
        return self._preview_error

    @pyqtProperty(str, notify=customisationsChanged)
    def readerCustomiseCheckedAt(self):
        if not self._customisations.checked_at:
            return "Included release information"
        checked = datetime.fromtimestamp(self._customisations.checked_at)
        return "Checked " + checked.strftime("%d %b, %H:%M")

    @pyqtProperty(str, notify=customisationsChanged)
    def readerCustomiseError(self):
        return self._customisations.error

    @pyqtProperty(str, notify=customiseFilterChanged)
    def readerCustomiseTab(self):
        return self._customise_tab

    @pyqtSlot(str)
    def setReaderCustomiseTab(self, value):
        if value in {"All", "Installed", "Updates"} and value != self._customise_tab:
            self._customise_tab = value
            self._customise_page = 0
            self.customiseFilterChanged.emit()

    @pyqtProperty(int, notify=customiseFilterChanged)
    def readerCustomisePage(self):
        return self._customise_page

    @pyqtSlot(int)
    def setReaderCustomisePage(self, value):
        value = max(0, value)
        if value != self._customise_page:
            self._customise_page = value
            self.customiseFilterChanged.emit()

    @pyqtProperty(bool, notify=activityChanged)
    def readerBusy(self):
        return self._runner.busy

    @pyqtProperty(bool, notify=activityChanged)
    def readerWorking(self):
        return self._runner.busy and self._runner.action in _MUTATING_ACTIONS

    @pyqtProperty(str, notify=activityChanged)
    def readerActivity(self):
        return _ACTIVITY_TITLES.get(self._runner.action, "") if self.readerBusy else ""

    @pyqtProperty(str, notify=feedbackChanged)
    def readerError(self):
        return self._error

    @pyqtProperty(str, notify=feedbackChanged)
    def readerMessage(self):
        return self._message

    def _set_feedback(self, *, error=None, message=None):
        previous = (self._error, self._message)
        if error is not None:
            self._error = error
        if message is not None:
            self._message = message
        if previous != (self._error, self._message):
            self.feedbackChanged.emit()

    def _start[T](
        self,
        action: str,
        call: Callable[[], T],
        on_result: Callable[[T], None],
        *,
        keep_feedback: bool = False,
        on_failure: Callable[[TaskFailure], None] | None = None,
    ) -> bool:
        if self.readerBusy or not self.canRead:
            return False
        if not keep_feedback:
            self._set_feedback(error="", message="")
        self._failed_action = ""
        self._result_handler = on_result
        self._failure_handler = on_failure or self._show_failure
        return self._runner.start(action, call)

    @pyqtSlot(str, object, object)
    def _task_completed(self, action, result, failure):
        if failure is not None:
            self._failed_action = action
            if self._failure_handler is not None:
                self._failure_handler(failure)
        elif self._result_handler is not None:
            self._result_handler(result)

    def _show_failure(self, failure: TaskFailure) -> None:
        self._set_feedback(error=failure.message)

    def _ignore_shortcut_failure(self, failure: TaskFailure) -> None:
        # Opening controls should not replace feedback from the reader screen.
        pass

    def _apply_reader(self, snapshot: ReaderSnapshot) -> None:
        if (snapshot.values.get("path"), snapshot.values.get("installed")) != (
            self._state.get("path"),
            self._state.get("installed"),
        ):
            self._apply_plugins(PluginSnapshot(items=[]))
            self._apply_customisations(CustomisationSnapshot(items=[]))
            self._select_customisation("")
            self.setReaderCustomisePage(0)
        if snapshot.values != self._state:
            self._state = snapshot.values
            self.readerChanged.emit()
        if snapshot.message:
            self._set_feedback(message=snapshot.message)

    def _apply_plugins(self, snapshot: PluginSnapshot) -> None:
        if snapshot.items != self._plugins:
            self._plugins = snapshot.items
            self.pluginsChanged.emit()
        if snapshot.message:
            self._set_feedback(message=snapshot.message)

    def _apply_customisations(self, snapshot: CustomisationSnapshot) -> None:
        previous_selection = self.readerCustomisation
        if snapshot != self._customisations:
            self._customisations = snapshot
            self.customisationsChanged.emit()
        if previous_selection != self.readerCustomisation:
            self.customisationChanged.emit()
        if snapshot.message:
            self._set_feedback(message=snapshot.message)
        self._apply_plugins(PluginSnapshot(items=[]))

    def _apply_preview(self, preview: CustomisationPreview) -> None:
        previous = (self.readerPreview, self._preview_error)
        self._previews[preview.item_id] = preview.url
        self._preview_error = ""
        if previous != (self.readerPreview, self._preview_error):
            self.previewChanged.emit()

    def _preview_failed(self, failure: TaskFailure) -> None:
        if self._preview_error != failure.message:
            self._preview_error = failure.message
            self.previewChanged.emit()

    def _apply_plan(
        self, proposal: Confirmation | None, plan: CustomisationPlan
    ) -> None:
        self.confirmations.update(
            proposal,
            title=plan.title,
            label=plan.label,
            body=plan.body,
            ready=plan.ready,
        )

    def _plan_failed(self, proposal: Confirmation | None, failure: TaskFailure) -> None:
        self.confirmations.update(
            proposal,
            ready=False,
            error=failure.message,
            body="Couldn’t prepare these changes.",
        )

    @pyqtSlot(str)
    def _task_finished(self, action):
        self._result_handler = None
        self._failure_handler = None
        if action == self._failed_action:
            if action == "status" and not self._state:
                self._pending_plugin_refresh = False
                self._pending_customisation_refresh = None
            self._recover_after_failure(action)
        self._resume_pending_refreshes(keep_feedback=True)
        self.refreshShortcut()
        self.settled.emit()

    def _recover_after_failure(self, action):
        if action in {"install", "uninstall", "scriptlet"}:
            self._start(
                "status", self.service.status, self._apply_reader, keep_feedback=True
            )
        elif action in {"plugin-install", "plugin-remove"}:
            self._start(
                "plugins",
                partial(self.service.list_plugins, self._selection()),
                self._apply_plugins,
                keep_feedback=True,
            )
        elif action in {
            "custom-install",
            "custom-remove",
            "custom-enable",
            "custom-disable",
        }:
            self._refresh_customisations(keep_feedback=True)

    @pyqtSlot()
    def refreshReader(self):
        self._start("status", self.service.status, self._apply_reader)

    @pyqtSlot()
    def checkReaderRelease(self):
        self._start("release", self.service.check_release, self._apply_reader)

    @pyqtSlot()
    def addReaderScriptlet(self):
        if (
            self.canChange
            and not self.confirmations.active
            and self._state.get("canAddScriptlet")
        ):
            self._start(
                "scriptlet",
                partial(self.service.add_scriptlet, self._selection()),
                self._apply_reader,
            )

    @pyqtSlot(str)
    def selectReaderInstallation(self, path):
        self._start(
            "select",
            partial(self.service.select_installation, path),
            self._apply_reader,
        )

    @pyqtSlot()
    def clearReaderFeedback(self):
        if not self.readerBusy:
            self._set_feedback(error="", message="")

    @pyqtSlot()
    def refreshReaderPlugins(self):
        if self.confirmations.active:
            return
        self._pending_plugin_refresh = True
        self._resume_pending_refreshes()

    @pyqtSlot()
    @pyqtSlot(bool)
    def refreshReaderCustomisations(self, online=False):
        if self.confirmations.active:
            return
        self._pending_customisation_refresh = bool(online) or bool(
            self._pending_customisation_refresh
        )
        self._resume_pending_refreshes()

    def _resume_pending_refreshes(self, *, keep_feedback=False):
        if self.readerBusy or not self.canRead or self.confirmations.active:
            return
        if (
            not self._pending_plugin_refresh
            and self._pending_customisation_refresh is None
        ):
            return
        if not self._state:
            self._start(
                "status",
                self.service.status,
                self._apply_reader,
                keep_feedback=keep_feedback,
            )
        elif self._pending_customisation_refresh is not None:
            online = self._pending_customisation_refresh
            self._pending_customisation_refresh = None
            self._refresh_customisations(online=online, keep_feedback=keep_feedback)
        else:
            self._pending_plugin_refresh = False
            self._start(
                "plugins",
                partial(self.service.list_plugins, self._selection()),
                self._apply_plugins,
                keep_feedback=keep_feedback,
            )

    def _refresh_customisations(self, *, online=False, keep_feedback=False):
        self._start(
            "custom-refresh" if online else "custom-list",
            partial(self.service.list_customisations, self._selection(), online=online),
            self._apply_customisations,
            keep_feedback=keep_feedback,
        )

    def _select_customisation(self, item_id):
        previous_preview = (self.readerPreview, self._preview_error)
        if item_id != self._selected_customisation:
            self._selected_customisation = item_id
            self.customisationChanged.emit()
        self._preview_error = ""
        if previous_preview != (self.readerPreview, self._preview_error):
            self.previewChanged.emit()

    @pyqtSlot(str)
    def selectReaderCustomisation(self, item_id):
        if self.readerBusy:
            return
        if any(item["id"] == item_id for item in self._customisations.items):
            if item_id != self._selected_customisation:
                self.clearReaderFeedback()
            self._select_customisation(item_id)
            self.navigation.navigate("koreader-customisation")

    @pyqtSlot()
    def loadReaderPreview(self):
        if (
            self.readerBusy
            or not self.readerPreviewAvailable
            or self.confirmations.active
        ):
            return
        if self._preview_error:
            self._preview_error = ""
            self.previewChanged.emit()
        self._start(
            "custom-preview",
            partial(self.service.load_preview, self._selected_customisation),
            self._apply_preview,
            keep_feedback=True,
            on_failure=self._preview_failed,
        )

    @pyqtSlot(str)
    def requestReaderCustomisation(self, action):
        if (
            action not in {item.value for item in CustomisationAction}
            or not self.readerCustomisation
            or not self.canChange
            or self.confirmations.active
        ):
            return
        request = CustomisationRequest(
            self._selection(), CustomisationAction(action), self._selected_customisation
        )
        proposal = self.confirmations.present(
            "reader",
            ConfirmationContent(
                title=action.capitalize()
                + " "
                + self.readerCustomisation["name"]
                + "?",
                body="Checking compatibility and existing files…",
            ),
            partial(self._confirm_customisation, request),
            lambda: self.canChange,
        )
        self._start(
            "custom-plan",
            partial(self.service.plan_customisation, request),
            partial(self._apply_plan, proposal),
            on_failure=partial(self._plan_failed, proposal),
        )

    def _confirm_customisation(self, request: CustomisationRequest) -> None:
        if self.canChange:
            self._start(
                "custom-" + request.action.value,
                partial(self.service.change_customisation, request),
                self._apply_customisations,
            )

    @pyqtSlot(str, str)
    def requestReader(self, action, value=""):
        if not self.canChange or self.confirmations.active:
            return
        proposal = prepare_action(action, value, self._state, self._plugins)
        if proposal is not None:
            self.confirmations.present(
                "reader",
                proposal.content,
                partial(self._confirm_action, proposal.request),
                lambda: self.canChange,
            )

    def _confirm_action(self, request: ReaderRequest) -> None:
        if isinstance(request, InstallationRequest):
            self._confirm_install(request)
        elif isinstance(request, RemovalRequest):
            self._confirm_uninstall(request)
        else:
            self._confirm_plugin(request)

    def _confirm_install(self, request: InstallationRequest) -> None:
        self._start(
            "install", partial(self.service.install, request), self._apply_reader
        )

    def _confirm_uninstall(self, request: RemovalRequest) -> None:
        self._pending_plugin_refresh = False
        self._pending_customisation_refresh = None
        self._start(
            "uninstall", partial(self.service.uninstall, request), self._apply_reader
        )

    def _confirm_plugin(self, request: PluginRequest) -> None:
        self._start(
            "plugin-" + request.action.value,
            partial(self.service.change_plugin, request),
            self._apply_plugins,
        )

    @pyqtSlot()
    def openReaderShortcut(self):
        if not self.canOpen or self.confirmations.active:
            return
        if len(self._state.get("installations", [])) == 1 and self._state.get(
            "canOpen"
        ):
            self.openReader()
        else:
            self.navigation.navigate("koreader")

    @pyqtSlot()
    def openReader(self):
        if not self.canOpen or not self._state.get("canOpen"):
            return
        try:
            self.service.open_reader(self._selection())
        except (OSError, ValueError) as error:
            if self._popover_open:
                self.navigation.navigate("koreader")
            self._set_feedback(error=str(error))
            return
        self.exitRequested.emit()
