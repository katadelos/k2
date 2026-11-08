"""Deliver the HAL's physical navigation buttons to the Qt event loop."""

from PyQt5.QtCore import QObject, QTimer, pyqtSignal


class DeviceButtons(QObject):
    action = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        from ereader_hal import Device

        self.device = Device()
        self.timer = QTimer(self)
        self.timer.setInterval(25)
        self.timer.timeout.connect(self._read)
        try:
            self.device.grab_buttons()
        except BaseException:
            self.device.close()
            raise
        self.timer.start()

    def _read(self):
        from ereader_hal import Action, Button, EventType

        try:
            for _ in range(32):
                event = self.device.poll_event(0)
                if event is None:
                    break
                if event.type != EventType.BUTTON:
                    continue
                value = event.data
                repeatable = value.button in {
                    Button.UP,
                    Button.DOWN,
                    Button.LEFT,
                    Button.RIGHT,
                }
                if value.action == Action.PRESS or (
                    repeatable and value.action == Action.REPEAT
                ):
                    self.action.emit(value.button.name.lower())
        except OSError as error:
            self.timer.stop()
            self.failed.emit(str(error))

    def close(self):
        self.timer.stop()
        self.device.close()
