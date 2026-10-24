"""Shared JSON-line transport and preview commands for the two desktop apps."""

import json
import os
import sys

from PyQt5.QtCore import QObject, QPoint, QSocketNotifier, Qt, QTimer
from PyQt5.QtTest import QTest


class JsonConsole(QObject):
    def __init__(self, runtime, snapshot, commands):
        super().__init__(runtime)
        self.runtime = runtime
        self.snapshot = snapshot
        self.commands = commands
        self.buffer = b""
        self.notifier = QSocketNotifier(sys.stdin.fileno(), QSocketNotifier.Read, self)
        self.notifier.activated.connect(self.read)

    def read(self):
        chunk = os.read(sys.stdin.fileno(), 65536)
        if not chunk:
            self.notifier.setEnabled(False)
            return
        self.buffer += chunk
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            request = {}
            try:
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise ValueError("Command must be a JSON object")
                self.dispatch(request)
            except Exception as error:
                self.reply(
                    request.get("id") if isinstance(request, dict) else None,
                    error=str(error),
                )

    def reply(self, ident, result=None, error=None):
        print(
            json.dumps(
                {"id": ident, "error": error}
                if error
                else {"id": ident, "result": result}
            ),
            flush=True,
        )

    def dispatch(self, request):
        rt, c = self.runtime, self.runtime.controller
        command, ident = request["command"], request.get("id")
        if command == "state":
            self.reply(
                ident,
                dict(
                    self.snapshot(c), revision=rt.revision, reloadOk=rt.last_reload_ok
                ),
            )
            return
        if command == "reload":
            rt.load()
        elif command == "tap":
            QTest.mouseClick(
                rt.window,
                Qt.LeftButton,
                pos=QPoint(int(request["x"]), int(request["y"])),
            )
        elif command == "screenshot":

            def capture():
                try:
                    self.reply(ident, rt.screenshot(request["path"]))
                except Exception as error:
                    self.reply(ident, error=str(error))

            QTimer.singleShot(150, capture)
            return
        elif command in self.commands:
            self.commands[command](request)
        else:
            raise ValueError("Unknown command: " + command)
        self.reply(ident, self.snapshot(c))
