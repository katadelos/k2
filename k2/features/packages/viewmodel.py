"""Package browsing, prepared transactions and installation activity."""

from copy import deepcopy
from datetime import datetime
from functools import partial

from PyQt5.QtCore import QObject, QTimer, pyqtProperty, pyqtSignal, pyqtSlot

from ...core.packages import Application, PackageFeature, PackagePlan, PackageRequest
from ...core.ports import ApplicationsBackend, DeviceBackend, PackageBackend
from ...ui.confirmations import Confirmations
from ...ui.navigation import Navigation
from ...ui.operations import Operation, Operations
from ...ui.tasks import TaskRunner
from .applications import empty_application
from .browsing import PackageBrowser
from .featured import FeaturedCatalog
from .models import PackageListModel
from .review import PackageReview, prepare_review
from .service import CatalogMetadata, read_catalog_metadata

PACKAGE_RESOURCES = frozenset({"packages", "reader", "network"})


class PackagesViewModel(QObject):
    changed = pyqtSignal()
    catalogChanged = pyqtSignal()
    catalogRowsChanged = pyqtSignal()
    filtersChanged = pyqtSignal()
    selectionChanged = pyqtSignal()
    featuresChanged = pyqtSignal()
    activityChanged = pyqtSignal()
    loadingChanged = pyqtSignal()
    logChanged = pyqtSignal()
    resultChanged = pyqtSignal()
    availabilityChanged = pyqtSignal()
    exitRequested = pyqtSignal()
    restartRequested = pyqtSignal()
    featureRequested = pyqtSignal(object)

    def __init__(
        self,
        backend: PackageBackend,
        service: ApplicationsBackend,
        device: DeviceBackend,
        navigation: Navigation,
        operations: Operations,
        confirmations: Confirmations,
        *,
        featured: FeaturedCatalog,
    ) -> None:
        super().__init__()
        self.backend = backend
        self.service = service
        self.device = device
        self.navigation = navigation
        self.operations = operations
        self.confirmations = confirmations
        self._featured = featured
        featured.setParent(self)
        featured.changed.connect(self.changed)
        self._browser = PackageBrowser()
        self._operation: dict = {}
        self._message = ""
        self._failed = False
        self._loading = True
        self._applications: dict[str, Application] = {}
        self._application = empty_application("")
        self._activity_application = empty_application("")
        self._features: list[PackageFeature] = []
        self._feature_errors: list[str] = []
        self._stopping = False
        self._restart_pending = False
        self._restart_error = ""
        self._completion = (True, "")
        self._availability_state: tuple[bool, bool] | None = None
        self._activity_state: tuple | None = None
        self._loading_state: tuple | None = None
        self._result_state: tuple | None = None
        self._features_state: tuple | None = None
        self._selection_state: tuple | None = None
        self._metadata_task = TaskRunner(self)
        self._metadata_task.completed.connect(self._metadata_completed)
        self._metadata_task.finished.connect(self._metadata_finished)
        self._metadata_task.busyChanged.connect(self._backend_activity_changed)
        self._pending_plan: PackageReview | None = None
        self._rows = PackageListModel(self)
        self._startup_refresh_timer = QTimer(self)
        self._startup_refresh_timer.setSingleShot(True)
        self._startup_refresh_timer.setInterval(1000)
        self._startup_refresh_timer.timeout.connect(self._refresh_on_startup)
        self.backend.catalogChanged.connect(self._backend_catalog_changed)
        self.backend.activityChanged.connect(self._backend_activity_changed)
        self.backend.logChanged.connect(self.logChanged.emit)
        self.backend.resultChanged.connect(self._backend_result_changed)
        self.backend.finished.connect(self._finished)
        self.backend.restartRequested.connect(self._restart_requested)
        self.backend.planned.connect(self._planned)
        # Aggregate notification for shell/console observers; it has no side effects.
        for signal in (
            self.catalogRowsChanged,
            self.filtersChanged,
            self.selectionChanged,
            self.featuresChanged,
            self.activityChanged,
            self.loadingChanged,
            self.logChanged,
            self.resultChanged,
        ):
            signal.connect(self.changed)
        operations.changed.connect(self._refresh_availability)
        operations.idleChanged.connect(self._restart_when_idle)
        confirmations.activeChanged.connect(self._refresh_availability)
        confirmations.activeChanged.connect(self._discard_pending_plan)
        navigation.routeActivated.connect(self._discard_pending_plan)
        self._update_catalog()
        self._refresh_availability()

    @pyqtProperty(bool, notify=availabilityChanged)
    def canChange(self):
        return (
            not self.busy
            and not self._restart_pending
            and self.operations.allows(PACKAGE_RESOURCES, owner="packages")
        )

    @pyqtProperty(bool, notify=availabilityChanged)
    def canLaunch(self):
        return (
            self.canChange
            and not self.confirmations.active
            and not self.catalogWarning
            and self.operations.allows({"controls"})
        )

    @pyqtProperty(QObject, constant=True)
    def rows(self):
        return self._rows

    @pyqtProperty(QObject, constant=True)
    def featured(self):
        return self._featured

    @pyqtProperty(int, notify=catalogRowsChanged)
    def packageCount(self):
        return len(self._browser.filtered)

    @pyqtProperty(int, notify=catalogRowsChanged)
    def pageCount(self):
        return self._browser.page_count

    @pyqtSlot(int)
    def setPageSize(self, value):
        if self._browser.resize(value):
            self._update_rows()
            self.catalogRowsChanged.emit()

    def _sync_operation(self):
        operation = None
        if self.busy:
            checking = self._operation.get("action") == "update"
            operation = Operation(
                # Fetching catalog metadata does not change installed software
                # or reader state. Device controls can keep working meanwhile.
                resources=frozenset({"catalog"}) if checking else PACKAGE_RESOURCES,
                working=self.backend.busy,
                title=self.activityTitle,
                route="activity",
                hidden_pages=("apps", "file-sharing") if checking else (),
            )
        self.operations.update("packages", operation)
        self._refresh_availability()

    @pyqtSlot()
    def _refresh_availability(self):
        state = (self.canChange, self.canLaunch)
        if state != self._availability_state:
            self._availability_state = state
            self.availabilityChanged.emit()

    def _notify_activity(self):
        state = (
            dict(self._operation),
            self.activityTitle,
            self.busy,
            self._message,
            self._failed,
            self._restart_error,
            self._activity_application,
            self.activityFeatures,
            self.freshnessText,
        )
        if state != self._activity_state:
            self._activity_state = state
            self.activityChanged.emit()

    def _notify_loading(self):
        state = (self.loading, self.loadingStatus, self.loadingProgress)
        if state != self._loading_state:
            self._loading_state = state
            self.loadingChanged.emit()

    def _notify_result(self):
        state = (
            dict(self.freshness),
            self.catalogWarning,
            self.stateWarning,
            dict(self.result),
        )
        if state != self._result_state:
            self._result_state = state
            self.resultChanged.emit()

    def _notify_features(self):
        state = (self._features, self._feature_errors)
        if state != self._features_state:
            self._features_state = state
            self.featuresChanged.emit()

    def _notify_selection(self):
        state = (dict(self.selected), self._application, self.packageFeatures)
        if state != self._selection_state:
            self._selection_state = state
            self.selectionChanged.emit()

    def _update_catalog(self):
        self._browser.replace(self.backend.catalog)
        self._update_rows()
        self.catalogRowsChanged.emit()

    def _update_rows(self):
        self._rows.replace(self._browser.rows)

    @pyqtSlot()
    def _backend_catalog_changed(self):
        self._update_catalog()
        self._notify_selection()

    @pyqtSlot()
    def _backend_activity_changed(self):
        self._sync_operation()
        self._notify_activity()
        self._notify_loading()

    @pyqtSlot()
    def _backend_result_changed(self):
        self._notify_result()
        self._notify_activity()
        self._refresh_availability()

    @pyqtSlot(bool, str)
    def _finished(self, success, message):
        if self._stopping:
            return
        if self.backend.last_result:
            self._operation = dict(self.backend.last_result)
        self._completion = (success, message)
        # Only copied Python records and a detached file reader enter the worker.
        catalog = deepcopy(self.backend.catalog)
        read_metadata = partial(
            read_catalog_metadata, self.service, catalog, self.backend.package_files
        )
        self._metadata_task.start("catalog-metadata", read_metadata)

    @pyqtSlot(str, object, object)
    def _metadata_completed(
        self, action: str, metadata: CatalogMetadata | None, failure
    ):
        if self._stopping:
            return
        if metadata is None:
            self._feature_errors = [
                failure.message if failure else "Could not read package metadata."
            ]
            self._features = []
            self._applications = {}
        else:
            self._features = list(metadata.features)
            self._feature_errors = list(metadata.errors)
            self._applications = metadata.applications
        self._read_application()
        name = self._operation.get("name", "")
        result_package = next(
            (package for package in self.backend.catalog if package["name"] == name),
            None,
        )
        self._activity_application = empty_application("")
        if result_package and result_package["installed"]:
            self._activity_application = self._applications.get(
                name, empty_application("")
            )
        self._notify_features()
        self._notify_selection()
        self._notify_activity()

    @pyqtSlot(str)
    def _metadata_finished(self, action):
        if self._stopping:
            return
        success, message = self._completion
        self._failed = (
            self.result.get("state") in {"failed", "interrupted"}
            if self.result
            else not success
        )
        self._message = self.result.get("message", message) if self._failed else message
        if self._loading:
            self._loading = False
            needs_review = self.result.get("action") != "update" and self._failed
            if not success or needs_review:
                self.navigation.navigate("activity")
            else:
                self._startup_refresh_timer.start()
        self._sync_operation()
        if self._stopping:
            return
        self._notify_loading()
        self._notify_activity()
        if not self._restart_pending:
            self.catalogChanged.emit()

    @pyqtSlot()
    def _restart_requested(self):
        if self._stopping:
            return
        self._restart_pending = True
        self._restart_error = ""
        self._refresh_availability()
        self._notify_activity()
        self._restart_when_idle()

    @pyqtSlot()
    def _restart_when_idle(self):
        if (
            self._stopping
            or not self._restart_pending
            or self.busy
            or not self.operations.idle
        ):
            return
        self._restart_pending = False
        try:
            self.service.launch_application(["/usr/bin/k2"])
        except (OSError, ValueError) as error:
            self._restart_error = (
                f"k2 was updated, but could not restart: {error} Exit and reopen k2."
            )
            self._refresh_availability()
            self._notify_activity()
            return
        self.restartRequested.emit()

    @pyqtProperty(str, notify=activityChanged)
    def restartError(self):
        return self._restart_error

    def stop(self):
        self._stopping = True
        self._discard_pending_plan()
        self._startup_refresh_timer.stop()
        self._featured.stop()

    def close(self):
        self.stop()
        self._featured.close()
        self._metadata_task.wait()

    @pyqtSlot(str)
    def selectFeature(self, identifier):
        feature = next(
            (item for item in self.features if item["id"] == identifier), None
        )
        if not feature:
            return
        if feature["kind"] == "application":
            if self.canLaunch:
                self.selectPackage(feature["package"])
                self.openApplication()
        else:
            self.featureRequested.emit(feature)

    def _execute(self, request: PackageRequest):
        if not self.canChange:
            return
        self._startup_refresh_timer.stop()
        self._message = ""
        self._failed = False
        self._operation = {"action": request.action, "name": request.name}
        self._activity_application = empty_application("")
        if request.action != "update":
            self.navigation.navigate("activity")
        try:
            self.backend.perform(request.action, request.name)
        except ValueError as error:
            self._message = str(error)
            self._failed = True
            self._notify_activity()

    @pyqtProperty(str, notify=filtersChanged)
    def tab(self):
        return self._browser.tab

    @pyqtProperty(str, notify=filtersChanged)
    def query(self):
        return self._browser.query

    @pyqtProperty(int, notify=catalogRowsChanged)
    def appPage(self):
        return self._browser.page

    @pyqtSlot(int)
    def setAppPage(self, value):
        if self._browser.set_page(value):
            self._update_rows()
            self.catalogRowsChanged.emit()

    @pyqtProperty("QVariantMap", notify=activityChanged)
    def operation(self):
        return self._operation

    @pyqtProperty(str, notify=activityChanged)
    def activityTitle(self):
        if self._restart_pending:
            return "Restarting k2…"
        if self._metadata_task.busy:
            return "Reading installed applications…"
        if self.busy:
            return self.backend.status.rstrip("…") + "…"
        action, name = self._operation.get("action"), self._operation.get("name", "")
        if self.result.get("state") == "interrupted" and not self.busy:
            return (
                "Update check interrupted"
                if action == "update"
                else "k2 closed before finishing"
            )
        if not action:
            return "Couldn’t load packages" if self.failed else "Activity"
        if action == "update":
            return (
                "Couldn’t check for updates"
                if self.failed
                else "Finished checking for updates"
            )
        if action == "upgrade" and not name:
            return "Couldn’t update packages" if self.failed else "Packages updated"
        verb, completed = {
            "install": ("install", "installed"),
            "upgrade": ("update", "updated"),
            "remove": ("remove", "removed"),
        }[action]
        if self.failed:
            return f"Couldn’t {verb} {name}"
        return f"{name} {completed}"

    @pyqtProperty(bool, notify=activityChanged)
    def busy(self):
        return self.backend.busy or self._metadata_task.busy

    @pyqtProperty(bool, notify=loadingChanged)
    def loading(self):
        return self._loading

    @pyqtProperty(str, notify=loadingChanged)
    def loadingStatus(self):
        return (
            "Reading installed applications"
            if self._metadata_task.busy
            else self.backend.status
        )

    @pyqtProperty(float, notify=loadingChanged)
    def loadingProgress(self):
        return self.backend.progress

    @pyqtProperty("QVariantList", notify=featuresChanged)
    def features(self):
        return self._features

    @pyqtProperty("QVariantList", notify=featuresChanged)
    def popoverFeatures(self):
        return sorted(
            (feature for feature in self._features if "popover" in feature),
            key=lambda feature: (
                feature["popover"]["order"],
                feature["title"].casefold(),
                feature["id"],
            ),
        )

    @pyqtProperty(str, notify=featuresChanged)
    def featureErrors(self):
        return "\n".join(self._feature_errors)

    @pyqtProperty("QVariantList", notify=selectionChanged)
    def packageFeatures(self):
        return [
            feature
            for feature in self._features
            if feature["package"] == self._browser.selection
        ]

    @pyqtProperty("QVariantList", notify=activityChanged)
    def activityFeatures(self):
        return [
            feature
            for feature in self._features
            if feature["package"] == self._operation.get("name")
        ]

    @pyqtProperty(str, notify=logChanged)
    def log(self):
        return self.backend.log

    @pyqtProperty(str, notify=activityChanged)
    def message(self):
        return self._message

    @pyqtProperty(bool, notify=activityChanged)
    def failed(self):
        return self._failed

    @pyqtProperty(int, notify=catalogRowsChanged)
    def installedCount(self):
        return sum(bool(p["installed"]) for p in self.backend.catalog)

    @pyqtProperty(int, notify=catalogRowsChanged)
    def updateCount(self):
        return sum(bool(p["update"]) for p in self.backend.catalog)

    @pyqtProperty("QVariantMap", notify=selectionChanged)
    def selected(self):
        return self._browser.selected or {}

    @pyqtSlot(str)
    def setTab(self, value):
        if self._browser.set_tab(value):
            self._update_rows()
            self.catalogRowsChanged.emit()
            self.filtersChanged.emit()
            self.refreshFeatured()

    @pyqtSlot(str)
    def search(self, value):
        if self._browser.search(value):
            self._update_rows()
            self.catalogRowsChanged.emit()
            self.filtersChanged.emit()

    @pyqtSlot()
    def refreshFeatured(self):
        if not self._stopping and self._browser.tab == "Featured":
            self._featured.refresh()

    @pyqtSlot()
    def refresh(self):
        if self._stopping:
            return
        self._featured.refresh()
        self.request("update", "")

    @pyqtSlot(str)
    def openFeatured(self, identifier):
        item = next(
            (item for item in self._featured.items if item["id"] == identifier), None
        )
        if item is None:
            return
        action = item["action"]
        if action.get("route") == "koreader":
            self.navigation.navigate("koreader")
        elif "package" in action:
            name = action["package"]
            if any(package["name"] == name for package in self.backend.catalog):
                self.selectPackage(name)
            else:
                self.search(name)
                self.navigation.navigate("apps")

    @pyqtSlot(str)
    def selectPackage(self, name):
        self._browser.selection = name
        self._read_application()
        self._notify_selection()
        self.navigation.navigate("package")

    @pyqtSlot(str, str)
    def request(self, action, name):
        if not self.canChange or self.confirmations.active:
            return
        request = PackageRequest(action, name)
        if action == "update":
            self._execute(PackageRequest("update"))
            return
        review = prepare_review(request, self._browser.selected, self.updateCount)
        if review is None:
            return
        self._startup_refresh_timer.stop()
        self._pending_plan = review
        try:
            self.backend.plan(action, name)
        except ValueError as error:
            self._planned(False, PackagePlan(error=str(error)))

    @pyqtSlot()
    def _discard_pending_plan(self):
        self._pending_plan = None

    @pyqtSlot(bool, object)
    def _planned(self, success: bool, plan: PackagePlan):
        if self._pending_plan is None:
            return
        review = self._pending_plan
        self._pending_plan = None
        self.confirmations.present(
            "packages",
            review.content(success, plan),
            partial(self._execute, review.request),
            lambda: self.canChange,
        )

    @pyqtSlot()
    def retry(self):
        if not self.canChange or self.confirmations.active or not self.failed:
            return
        if self._operation:
            self._browser.selection = self._operation.get("name", "")
            self.request(self._operation["action"], self._browser.selection)
        else:
            self._failed = False
            self._message = ""
            self.backend.refresh()

    @pyqtSlot()
    def reloadPackages(self):
        if self.canChange and not self.confirmations.active:
            self.backend.refresh()

    def _refresh_on_startup(self):
        if not self.operations.idle or self.confirmations.active:
            self._startup_refresh_timer.start()
            return
        if self.device.network_available():
            self.request("update", "")

    @pyqtProperty("QVariantMap", notify=resultChanged)
    def freshness(self):
        return self.backend.freshness

    @pyqtProperty(str, notify=activityChanged)
    def freshnessText(self):
        if self.busy and self._operation.get("action") == "update":
            return "Checking for updates…"
        value = self.freshness.get("lastRefresh", 0)
        stamp = datetime.fromtimestamp(value).strftime("%d %b, %H:%M") if value else ""
        if self.freshness.get("error", "").startswith("Kernel module feed:"):
            return "Some updates couldn’t be checked"
        if self.freshness.get("error"):
            return "Couldn’t check for updates" + (
                " · last checked " + stamp if stamp else ""
            )
        return "Last checked " + stamp if stamp else "Updates not checked yet"

    @pyqtProperty(str, notify=resultChanged)
    def catalogWarning(self):
        return self.backend.catalog_error

    @pyqtProperty(str, notify=resultChanged)
    def stateWarning(self):
        return self.backend.state_error

    @pyqtProperty("QVariantMap", notify=resultChanged)
    def result(self):
        return self.backend.last_result

    @pyqtProperty("QVariantMap", notify=selectionChanged)
    def application(self):
        return self._application

    def _read_application(self):
        self._application = self._applications.get(
            self._browser.selection, empty_application("")
        )

    @pyqtProperty("QVariantMap", notify=activityChanged)
    def activityApplication(self):
        return self._activity_application

    @pyqtSlot()
    def showInstalledPackage(self):
        name = self._operation.get("name", "")
        if name:
            self.selectPackage(name)

    @pyqtSlot()
    def openActivityApplication(self):
        self.showInstalledPackage()
        self.openApplication()

    @pyqtSlot()
    def openApplication(self):
        if not self.canLaunch or not self._application.get("canOpen"):
            return
        try:
            self.service.launch_application(self._application["argv"])
        except (OSError, ValueError) as error:
            self._application = {**self._application, "error": str(error)}
            self._notify_selection()
            return
        self.exitRequested.emit()
