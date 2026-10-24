"""One-shot background work with results delivered on the owning Qt thread."""

import logging
from collections.abc import Callable
from dataclasses import dataclass

from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaskFailure:
    message: str


@dataclass(frozen=True)
class _Outcome:
    result: object = None
    failure: TaskFailure | None = None


class _Worker(QThread):
    completed = pyqtSignal()

    def __init__(
        self, action: str, call: Callable[[], object], parent: QObject
    ) -> None:
        super().__init__(parent)
        self.action = action
        self.call = call
        self.outcome: _Outcome | None = None

    def run(self) -> None:
        try:
            result = self.call()
        except (OSError, ValueError) as error:
            logger.warning("%s failed: %s", self.action, error)
            self.outcome = _Outcome(failure=TaskFailure(str(error)))
        except Exception as error:
            logger.exception("Unexpected failure in %s", self.action)
            message = str(error) or type(error).__name__
            self.outcome = _Outcome(failure=TaskFailure(message))
        else:
            self.outcome = _Outcome(result=result)
        self.completed.emit()


class TaskRunner(QObject):
    """Retain one worker until it finishes, then permit a follow-up task.

    Callables must capture service objects and request data before ``start``;
    they must not read or mutate a view model from the worker thread.
    Lifecycle methods and completion handlers run on this object's owning thread.
    """

    completed = pyqtSignal(str, object, object)
    finished = pyqtSignal(str)
    busyChanged = pyqtSignal()

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self._task: _Worker | None = None
        self._delivered = False

    @property
    def busy(self) -> bool:
        return self._task is not None

    @property
    def action(self) -> str:
        return self._task.action if self._task else ""

    def start(self, action: str, call: Callable[[], object]) -> bool:
        if self.busy:
            return False
        task = _Worker(action, call, self)
        task.completed.connect(self._completed)
        task.finished.connect(self._finished)
        self._task = task
        self._delivered = False
        self.busyChanged.emit()
        task.start()
        return True

    def _deliver(self, task: _Worker) -> None:
        if task is not self._task or self._delivered or task.outcome is None:
            return
        self._delivered = True
        self.completed.emit(task.action, task.outcome.result, task.outcome.failure)

    @pyqtSlot()
    def _completed(self) -> None:
        task = self.sender()
        if isinstance(task, _Worker):
            self._deliver(task)

    @pyqtSlot()
    def _finished(self) -> None:
        task = self.sender()
        if isinstance(task, _Worker):
            self._finish(task)

    def _finish(self, task: _Worker) -> None:
        # wait() can finalize a worker before its queued Qt signals arrive.
        # Those old signals must not complete a newer follow-up task.
        if task is not self._task:
            return
        self._deliver(task)
        if task is not self._task:
            return
        self._task = None
        task.deleteLater()
        self.finished.emit(task.action)
        # Completion handlers may start another task. Publish its actual state,
        # without briefly announcing idle between related operations.
        self.busyChanged.emit()

    def wait(self) -> None:
        """Join and deliver accepted work without pumping unrelated GUI events.

        Stop scheduling new requests first. Finished handlers may drain work
        already accepted before shutdown; each such worker is joined in turn.
        """
        while self._task is not None:
            task = self._task
            task.wait()
            self._finish(task)
