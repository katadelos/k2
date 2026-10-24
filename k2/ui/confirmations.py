"""Confirmation presentation, with execution owned by the requesting feature."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType

from PyQt5.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot


@dataclass(frozen=True)
class ConfirmationContent:
    title: str
    label: str = "Continue"
    body: str = ""
    ready: bool = False
    changes: tuple[Mapping[str, object], ...] = ()
    error: str = ""

    def __post_init__(self):
        changes = tuple(MappingProxyType(dict(change)) for change in self.changes)
        object.__setattr__(self, "changes", changes)

    def to_qml(self) -> dict:
        return {
            "title": self.title,
            "label": self.label,
            "body": self.body,
            "ready": self.ready,
            "changes": [dict(change) for change in self.changes],
            "error": self.error,
        }


@dataclass(eq=False)
class Confirmation:
    """An identity token that rejects results belonging to a dismissed dialog."""

    owner: str
    content: ConfirmationContent
    execute: Callable[[], None] = field(repr=False)
    allowed: Callable[[], bool] = field(repr=False)


class Confirmations(QObject):
    changed = pyqtSignal()
    pendingChanged = pyqtSignal()
    activeChanged = pyqtSignal()
    availabilityChanged = pyqtSignal()
    # Follow-up work resumes after the confirmed action has been dispatched.
    closed = pyqtSignal()

    def __init__(self, operations):
        super().__init__()
        self._request: Confirmation | None = None
        self._can_confirm = False
        operations.changed.connect(self._refresh_availability)

    @pyqtProperty(bool, notify=activeChanged)
    def active(self):
        return self._request is not None

    @pyqtProperty("QVariantMap", notify=pendingChanged)
    def pending(self):
        return self._request.content.to_qml() if self._request else {}

    @pyqtProperty(bool, notify=availabilityChanged)
    def canConfirm(self):
        request = self._request
        return bool(request and request.content.ready and request.allowed())

    @pyqtSlot()
    def _refresh_availability(self):
        available = self.canConfirm
        if available != self._can_confirm:
            self._can_confirm = available
            self.availabilityChanged.emit()

    def present(
        self,
        owner: str,
        content: ConfirmationContent,
        execute: Callable[[], None],
        allowed: Callable[[], bool],
    ) -> Confirmation | None:
        if self.active:
            return None
        request = Confirmation(owner, content, execute, allowed)
        self._request = request
        self.pendingChanged.emit()
        self.activeChanged.emit()
        self._refresh_availability()
        self.changed.emit()
        return request

    def update(self, request: Confirmation | None, **values) -> None:
        if request is None or request is not self._request:
            return
        content = replace(request.content, **values)
        if content == request.content:
            return
        request.content = content
        self.pendingChanged.emit()
        self._refresh_availability()
        self.changed.emit()

    def _clear_request(self):
        self._request = None
        self.pendingChanged.emit()
        self.activeChanged.emit()
        self._refresh_availability()
        self.changed.emit()

    @pyqtSlot()
    def cancel(self):
        if not self.active:
            return
        self._clear_request()
        self.closed.emit()

    @pyqtSlot()
    def confirm(self):
        if not self.canConfirm:
            return
        request = self._request
        if request is None:
            return
        self._clear_request()
        try:
            request.execute()
        finally:
            self.closed.emit()
