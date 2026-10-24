"""Schedule desktop captures after the loading view has settled."""

import sys

from PyQt5.QtCore import QTimer
from PyQt5.QtQml import QQmlProperty


def install_capture(runtime, path, *, watch, scenario):
    app, controller = runtime.app, runtime.controller
    capture_timer = QTimer(app)
    capture_timer.setSingleShot(True)
    capture_timer.setInterval(150)

    def splash_is_loading():
        return scenario != "loading" and runtime.window.property("splashVisible")

    def schedule_capture():
        if not splash_is_loading():
            capture_timer.start()

    def capture():
        if splash_is_loading():
            return
        try:
            runtime.screenshot(path)
        except RuntimeError as error:
            print(error, file=sys.stderr)
            app.exit(1)
            return
        if not watch:
            app.quit()

    def observe_splash():
        QQmlProperty(runtime.window, "splashVisible").connectNotifySignal(
            schedule_capture
        )

    capture_timer.timeout.connect(capture)
    observe_splash()
    QTimer.singleShot(1000, schedule_capture)
    if watch:
        controller.changed.connect(schedule_capture)
        previous_watch = runtime._stamp

        def capture_changes():
            nonlocal previous_watch
            if runtime._stamp != previous_watch:
                previous_watch = runtime._stamp
                observe_splash()
                schedule_capture()

        runtime.timer.timeout.connect(capture_changes)
