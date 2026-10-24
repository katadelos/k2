"""Application composition exposed to the shell QML, without feature workflows."""

from typing import TYPE_CHECKING

from PyQt5.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from .. import __version__

if TYPE_CHECKING:
    from ..core.ports import DeviceBackend, DeviceInfo
    from ..features.device.viewmodel import DeviceViewModel
    from ..features.file_sharing.viewmodel import FileSharingViewModel
    from ..features.files.viewmodel import FilesViewModel
    from ..features.koreader.viewmodel import KOReaderViewModel
    from ..features.packages.viewmodel import PackagesViewModel
    from ..features.remote_access.viewmodel import RemoteAccessViewModel
    from ..ui.confirmations import Confirmations
    from ..ui.navigation import Navigation
    from ..ui.operations import Operations


class AppShell(QObject):
    # Aggregate changes support simulator capture; QML properties use focused signals.
    changed = pyqtSignal()
    exitRequested = pyqtSignal()
    infoChanged = pyqtSignal()
    awakeChanged = pyqtSignal()

    def __init__(
        self,
        device: DeviceBackend,
        *,
        packages: PackagesViewModel,
        reader: KOReaderViewModel,
        remote: RemoteAccessViewModel,
        controls: DeviceViewModel,
        files: FilesViewModel,
        sharing: FileSharingViewModel,
        navigation: Navigation,
        operations: Operations,
        confirmations: Confirmations,
    ) -> None:
        super().__init__()
        self.device = device
        self._packages = packages
        self._reader = reader
        self._remote = remote
        self._controls = controls
        self._files = files
        self._sharing = sharing
        self._navigation = navigation
        self._operations = operations
        self._confirmations = confirmations
        self._quitting = False
        self._stopping_models = False
        self.models = (packages, reader, remote, controls, files, sharing)
        for model in self.models:
            model.setParent(self)
            model.changed.connect(self.changed)
        for service in (navigation, operations, confirmations):
            service.setParent(self)
            service.changed.connect(self.changed)
        controls.infoChanged.connect(self.infoChanged)
        operations.awakeChanged.connect(self.awakeChanged)
        operations.idleChanged.connect(self._finish_quit)

    @pyqtProperty(QObject, constant=True)
    def packages(self) -> PackagesViewModel:
        return self._packages

    @pyqtProperty(QObject, constant=True)
    def reader(self) -> KOReaderViewModel:
        return self._reader

    @pyqtProperty(QObject, constant=True)
    def remote(self) -> RemoteAccessViewModel:
        return self._remote

    @pyqtProperty(QObject, constant=True)
    def controls(self) -> DeviceViewModel:
        return self._controls

    @pyqtProperty(QObject, constant=True)
    def files(self) -> FilesViewModel:
        return self._files

    @pyqtProperty(QObject, constant=True)
    def sharing(self) -> FileSharingViewModel:
        return self._sharing

    @pyqtProperty(QObject, constant=True)
    def navigation(self) -> Navigation:
        return self._navigation

    @pyqtProperty(QObject, constant=True)
    def operations(self) -> Operations:
        return self._operations

    @pyqtProperty(QObject, constant=True)
    def confirmations(self) -> Confirmations:
        return self._confirmations

    @pyqtProperty(str, constant=True)
    def version(self) -> str:
        return __version__

    @pyqtProperty("QVariantMap", notify=infoChanged)
    def info(self) -> DeviceInfo:
        return self.controls.info

    @pyqtProperty(bool, notify=awakeChanged)
    def needsAwake(self) -> bool:
        return self.operations.needsAwake

    @pyqtSlot()
    def back(self) -> None:
        if self.confirmations.active:
            self.confirmations.cancel()
        elif self.controls.controlsOpen:
            self.controls.closeControls()
        else:
            self.navigation.back()

    @pyqtSlot()
    def quit(self) -> None:
        if not self.operations.canExit:
            return
        self._quitting = True
        self._stopping_models = True
        try:
            self.operations.stop()
            for model in self.models:
                model.stop()
        finally:
            self._stopping_models = False
        self._finish_quit()

    @pyqtSlot()
    def _finish_quit(self) -> None:
        if self._quitting and not self._stopping_models and self.operations.idle:
            self._quitting = False
            self.exitRequested.emit()

    def close(self) -> None:
        self.operations.stop()
        for model in self.models:
            model.close()
