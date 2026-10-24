"""Shared Qt runtime with transactional QML reloads for host development."""

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, cast

import eboard
from PyQt5 import sip
from PyQt5.QtCore import (
    QEventLoop,
    QObject,
    QSize,
    Qt,
    QTimer,
    QUrl,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
)
from PyQt5.QtGui import QFont, QGuiApplication
from PyQt5.QtQml import QQmlApplicationEngine
from PyQt5.QtQuick import QQuickWindow

from ..core.ports import Signal
from .appearance import Appearance


class RuntimeDevice(Protocol):
    def set_active(self, active: bool) -> None: ...


class RuntimeController(Protocol):
    @property
    def device(self) -> RuntimeDevice: ...
    @property
    def info(self) -> Mapping[str, object]: ...
    @property
    def needsAwake(self) -> bool: ...
    @property
    def changed(self) -> Signal: ...
    @property
    def exitRequested(self) -> Signal: ...
    def close(self) -> None: ...


class _InstalledDevice(Protocol):
    @property
    def sdk(self) -> Path: ...


class _DisplayUpdates(Protocol):
    def close(self) -> None: ...
    def flush_pending(self) -> None: ...


class _KeyboardDisplay(Protocol):
    def attach(self, window: QQuickWindow) -> _DisplayUpdates | None: ...
    def close(self) -> None: ...


class Runtime(QObject):
    firstFrame = pyqtSignal()

    def __init__(
        self,
        app: QGuiApplication,
        controller: RuntimeController | None,
        width: int,
        height: int,
        device: bool = False,
        scale: float = 1.0,
        qml_path: str | Path | None = None,
        context_name: str = "shell",
        family: str | None = None,
        settings_path: str | Path | None = None,
    ) -> None:
        super().__init__(app)
        self.app = app
        self.controller: RuntimeController | None = None
        if family is None:
            if controller is None:
                raise ValueError("Deferred startup requires a device family")
            family = str(controller.info["family"])
        self.family = family
        self._closed = False
        self._presented = False
        self.width, self.height = width, height
        self.device, self.scale = device, scale
        if settings_path is None and device and controller is not None:
            # Device sessions supply an SDK-backed adapter; desktop controllers
            # only need the activity interface above.
            settings_path = (
                cast(_InstalledDevice, controller.device).sdk / "etc/k2/ui.ini"
            )
        self._appearance = Appearance(
            self, device=device, family=self.family, settings_path=settings_path
        )
        self.offscreen = not device and app.platformName() == "offscreen"
        # At the 600 px layout's native size, use hinted device metrics.
        # Larger panels scale the scene, where outline metrics stay sharper.
        native_text = width == 600
        QQuickWindow.setTextRenderType(
            QQuickWindow.NativeTextRendering
            if native_text
            else QQuickWindow.QtTextRendering
        )
        font = app.font()
        font.setHintingPreference(
            QFont.PreferFullHinting if native_text else QFont.PreferDefaultHinting
        )
        font.setStyleStrategy(QFont.PreferAntialias | QFont.NoSubpixelAntialias)
        app.setFont(font)
        self.qml = Path(qml_path) if qml_path else Path(__file__).parent / "shell"
        self.context_name = context_name
        self.engine: QQmlApplicationEngine | None = None
        self.display_updates: _DisplayUpdates | None = None
        self.keyboard_display: _KeyboardDisplay | None = None
        self.revision = 0
        self.last_reload_ok = True
        self._active: bool | None = None
        self.app.setQuitOnLastWindowClosed(False)
        self.timer = QTimer(self)
        self.timer.setInterval(350)
        self.timer.timeout.connect(self._watch)
        self._stamp: list[tuple[str, int]] = []
        self.app.aboutToQuit.connect(self.close)
        if controller is not None:
            self.attach_controller(controller)

    @property
    def closed(self) -> bool:
        return self._closed

    @pyqtProperty(QObject, constant=True)
    def appearance(self) -> Appearance:
        return self._appearance

    def attach_controller(self, controller: RuntimeController) -> None:
        if self._closed:
            raise RuntimeError("Cannot attach an application to a closed runtime")
        if self.controller is not None:
            raise RuntimeError("The runtime already has an application")
        self.controller = controller
        controller.exitRequested.connect(self.app.quit)
        controller.changed.connect(self._sync_activity)
        if self.engine is not None:
            self.engine.rootContext().setContextProperty(self.context_name, controller)
            self._sync_activity()

    @pyqtSlot()
    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.timer.stop()
        self._appearance.close()
        if self.controller is not None:
            self.controller.close()
        if self.display_updates is not None:
            self.display_updates.close()
            self.display_updates = None
        if self.keyboard_display is not None:
            self.keyboard_display.close()
            self.keyboard_display = None
        if self.engine is not None:
            sip.delete(self.engine)
            self.engine = None

    def load(self) -> bool:
        if self._closed:
            raise RuntimeError("Cannot load a closed runtime")
        engine = QQmlApplicationEngine()
        # Expose the same component module from source checkouts and SDK installs.
        engine.addImportPath(str(Path(__file__).parents[2]))
        keyboard_display: _KeyboardDisplay = eboard.install(
            engine, device=self.device, family=self.family
        )
        context = engine.rootContext()
        for name, value in {
            self.context_name: self.controller,
            "panelWidth": self.width,
            "panelHeight": self.height,
            "windowScale": self.scale,
            "deviceFamily": self.family,
            "offscreenPreview": self.offscreen,
            "deviceMode": self.device,
            "deferredStartup": self.controller is None,
            "appRuntime": self,
            "firstFramePresented": False,
        }.items():
            context.setContextProperty(name, value)
        engine.load(QUrl.fromLocalFile(str(self.qml / "Main.qml")))
        roots = engine.rootObjects()
        self.last_reload_ok = (
            bool(roots)
            and isinstance(roots[0], QQuickWindow)
            and not roots[0].property("applicationLoadFailed")
        )
        if not self.last_reload_ok:
            for root in roots:
                root.setProperty("visible", False)
            keyboard_display.close()
            engine.deleteLater()
            return False
        previous = self.engine
        if self.display_updates is not None:
            self.display_updates.close()
            self.display_updates = None
        if self.keyboard_display is not None:
            self.keyboard_display.close()
        self.keyboard_display = keyboard_display
        self.engine = engine
        self._presented = False
        self.display_updates = keyboard_display.attach(self.window)
        self.window.activeChanged.connect(self._sync_activity)
        self.window.activeChanged.connect(self._appearance.refresh)
        self.window.frameSwapped.connect(self._frame_presented, Qt.QueuedConnection)
        self._sync_activity()
        if previous:
            for root in previous.rootObjects():
                root.setProperty("visible", False)
            previous.deleteLater()
        self.revision += 1
        return True

    @pyqtSlot()
    def _frame_presented(self) -> None:
        if (
            self._closed
            or self._presented
            or self.engine is None
            or self.sender() != self.window
        ):
            return
        self._presented = True
        if self.display_updates is not None:
            self.display_updates.flush_pending()
        self.engine.rootContext().setContextProperty("firstFramePresented", True)
        self.firstFrame.emit()

    @pyqtSlot()
    def fail_application_load(self) -> None:
        if not self._closed:
            self.last_reload_ok = False
            self.app.exit(1)

    def _sync_activity(self) -> None:
        if self._closed or self.engine is None or self.controller is None:
            return
        active = self.window.isActive() or self.controller.needsAwake
        if active != self._active:
            self.controller.device.set_active(active)
            self._active = active

    @property
    def window(self) -> QQuickWindow:
        if self.engine is None:
            raise RuntimeError("The UI has not been loaded.")
        return self.engine.rootObjects()[0]

    def screenshot(self, path: str | Path) -> str:
        path = Path(path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        if not self.device and not self.offscreen:
            # Capture the presented scene on desktop. Offscreen item grabs can
            # succeed even when a native window's composited layers are blank.
            frame = self.window.grabWindow()
            if frame.isNull() or not frame.save(str(path)):
                raise RuntimeError(f"Could not render {path}")
            return str(path)
        grab = self.window.contentItem().grabToImage(
            QSize(self.window.width(), self.window.height())
        )
        if grab is None:
            raise RuntimeError(f"Could not render {path}")
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        grab.ready.connect(loop.quit)
        timer.start(5000)
        loop.exec_()
        timer.stop()
        if grab.image().isNull() or not grab.saveToFile(str(path)):
            raise RuntimeError(f"Could not render {path}")
        return str(path)

    def watch(self) -> None:
        self._stamp = self._files()
        self.timer.start()

    def _files(self) -> list[tuple[str, int]]:
        directories = {
            self.qml,
            Path(__file__).parent / "components",
            Path(__file__).parents[1] / "features",
        }
        return [
            (str(p), p.stat().st_mtime_ns)
            for directory in sorted(directories)
            for p in sorted(directory.rglob("*"))
            if p.is_file() and (p.suffix == ".qml" or p.name == "qmldir")
        ]

    def _watch(self) -> None:
        stamp = self._files()
        if stamp != self._stamp:
            self._stamp = stamp
            self.load()
