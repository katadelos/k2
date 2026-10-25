"""Appearance preference, using Kindle's display inversion when available."""

from pathlib import Path

from PyQt5.QtCore import (
    QObject,
    QProcess,
    QSettings,
    QTimer,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
)


class Appearance(QObject):
    changed = pyqtSignal()

    def __init__(self, parent, *, device, family, model=None, settings_path=None):
        super().__init__(parent)
        self._settings = (
            QSettings(str(settings_path), QSettings.IniFormat)
            if settings_path
            else QSettings(QSettings.IniFormat, QSettings.UserScope, "k2", "simulator")
        )
        self._local_dark = self._settings.value("appearance/darkMode", False, type=bool)
        native = (
            device
            and family == "kindle"
            # Basic 2019 exposes epdcMode but lacks the night-mode waveforms.
            # Its firmware accepts Y8INV and then blanks the display. Render
            # the dark palette in software while keeping normal waveforms.
            and model is not None
            and model != "Kindle Basic 2019"
            and all(
                Path(f"/usr/bin/lipc-{command}").is_file()
                for command in ("get-prop", "set-prop", "wait-event")
            )
        )
        self._native = None if native else False
        self._dark = False if native else self._local_dark
        self._error = ""
        self._action = None
        self._target = None
        self._refresh_pending = False
        self._closed = False
        self._command = QProcess(self)
        self._command.finished.connect(self._finished)
        self._command.errorOccurred.connect(self._process_error)
        self._deadline = QTimer(self)
        self._deadline.setSingleShot(True)
        self._deadline.setInterval(3000)
        self._deadline.timeout.connect(self._command.kill)
        self._events = QProcess(self)
        self._events.readyReadStandardOutput.connect(self._system_changed)
        if native:
            self._events.start(
                "/usr/bin/lipc-wait-event",
                ["-m", "com.lab126.winmgr", "nightModeStateChanged"],
            )
            self.refresh()

    @pyqtProperty(bool, notify=changed)
    def darkMode(self):
        return self._dark

    @pyqtProperty(bool, notify=changed)
    def paletteDarkMode(self):
        # Kindle inverts the whole display, including K2 and the stock chrome.
        # Painting a dark palette as well would invert the application twice.
        return self._native is False and self._dark

    @pyqtProperty(bool, notify=changed)
    def busy(self):
        return self._native is None or self._action is not None

    @pyqtProperty(str, notify=changed)
    def error(self):
        return self._error

    def _start(self, action, value=None):
        self._action = action
        arguments = ["-s", "com.lab126.winmgr", "epdcMode"]
        if value is not None:
            arguments.append(value)
        self._deadline.start()
        self._command.start(
            f"/usr/bin/lipc-{'get' if action == 'read' else 'set'}-prop", arguments
        )
        self.changed.emit()

    @pyqtSlot()
    def refresh(self):
        if self._closed or self._native is False:
            return
        if self._action is not None:
            self._refresh_pending = True
        else:
            self._start("read")

    @pyqtSlot(bool)
    def setDarkMode(self, enabled):
        if self._closed or self.busy or enabled == self._dark:
            return
        self._error = ""
        if self._native:
            self._target = enabled
            self._start("write", "Y8INV" if enabled else "Y8")
        else:
            self._dark = self._local_dark = enabled
            self._settings.setValue("appearance/darkMode", enabled)
            self._settings.sync()
            self.changed.emit()

    def _system_changed(self):
        self._events.readAllStandardOutput()
        self.refresh()

    def _process_error(self, error):
        if error == QProcess.FailedToStart:
            self._finished(-1, QProcess.CrashExit)

    def _finished(self, code, status):
        if self._closed or self._action is None:
            return
        self._deadline.stop()
        action, self._action = self._action, None
        value = (
            bytes(self._command.readAllStandardOutput())
            .decode(errors="replace")
            .strip()
        )
        self._command.readAllStandardError()
        success = code == 0 and status == QProcess.NormalExit
        if action == "read":
            if success and value in ("Y8", "Y8INV"):
                self._native = True
                self._dark = value == "Y8INV"
                self._error = (
                    "Kindle did not change dark mode."
                    if self._target is not None and self._target != self._dark
                    else ""
                )
            elif self._native is None:
                self._native = False
                self._dark = self._local_dark
                self._events.terminate()
            else:
                self._error = "Could not read Kindle dark mode."
            self._target = None
        elif success:
            # Read back the actual system state; the firmware can reject a mode.
            self._refresh_pending = True
        else:
            self._target = None
            self._error = "Could not change Kindle dark mode."
        if self._refresh_pending and self._native is not False:
            self._refresh_pending = False
            self.refresh()
        else:
            self.changed.emit()

    def close(self):
        self._closed = True
        self._deadline.stop()
        for process in (self._command, self._events):
            if process.state() != QProcess.NotRunning:
                process.terminate()
                if not process.waitForFinished(500):
                    process.kill()
                    process.waitForFinished(500)
