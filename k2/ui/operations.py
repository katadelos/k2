"""Resource ownership shared by asynchronous feature workflows."""

from collections.abc import Set
from dataclasses import dataclass, field

from PyQt5.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot


@dataclass(frozen=True)
class Operation:
    resources: frozenset[str] = field(default_factory=frozenset)
    working: bool = False
    cancellable: bool = False
    title: str = ""
    route: str = ""
    hidden_pages: tuple[str, ...] = ()


class Operations(QObject):
    changed = pyqtSignal()
    awakeChanged = pyqtSignal()
    idleChanged = pyqtSignal()
    activityChanged = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._active: dict[str, Operation] = {}
        self.stopping = False

    def update(self, owner: str, operation: Operation | None = None) -> None:
        if self._active.get(owner) == operation:
            return
        was_awake = self.needsAwake
        was_idle = self.idle
        previous_activity = self.activity
        if operation is None:
            self._active.pop(owner, None)
        else:
            self._active[owner] = operation
        if was_awake != self.needsAwake:
            self.awakeChanged.emit()
        if was_idle != self.idle:
            self.idleChanged.emit()
        if previous_activity != self.activity:
            self.activityChanged.emit()
        self.changed.emit()

    def allows(self, resources: Set[str], owner: str | None = None) -> bool:
        return not self.stopping and not any(
            resources & job.resources
            for name, job in self._active.items()
            if name != owner
        )

    @pyqtProperty(bool, notify=awakeChanged)
    def needsAwake(self):
        return any(job.working for job in self._active.values())

    @pyqtProperty(bool, notify=changed)
    def canExit(self):
        return not any(
            job.working and not job.cancellable for job in self._active.values()
        )

    @pyqtProperty(bool, notify=idleChanged)
    def idle(self):
        return not self._active

    @pyqtProperty("QVariantMap", notify=activityChanged)
    def activity(self):
        job = next((job for job in self._active.values() if job.working), None)
        if job is None:
            return {}
        return {
            "title": job.title,
            "route": job.route,
            "hiddenPages": list(job.hidden_pages),
        }

    @pyqtSlot()
    def stop(self):
        if self.stopping:
            return
        self.stopping = True
        self.changed.emit()
