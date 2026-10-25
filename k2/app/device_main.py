"""Device entry point."""

import os
import sys
from pathlib import Path

from ..adapters.device import create_device


def main() -> int:
    import argparse

    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QGuiApplication

    from ..ui.runtime import Runtime

    parser = argparse.ArgumentParser(description="k2 device application")
    parser.add_argument("--family", choices=("kindle", "kobo"), required=True)
    parser.add_argument("--feature", help="Open an installed device feature by ID")
    args = parser.parse_args()
    device = create_device(args.family)
    if os.environ.get("OPKG_CONF_DIR") != str(device.sdk / "opkg"):
        parser.error(
            "Launch k2 through its installed launcher to load the SDK environment"
        )
    runtime_root = Path("/var/run/eink-sdk")
    qt_args = ["k2"]
    if args.family == "kindle":
        from ..adapters.kindle_x11 import grayscale_visual

        qt_args += ["-visual", grayscale_visual()]
    app = QGuiApplication(qt_args)
    if app.primaryScreen() is None:
        parser.exit(1, "k2 could not initialize the device display\n")
    screen = app.primaryScreen().size()
    runtime = Runtime(
        app,
        None,
        screen.width(),
        screen.height(),
        device=True,
        family=args.family,
        model=device.model,
        settings_path=device.sdk / "etc/k2/ui.ini",
    )

    def start_application() -> None:
        if runtime.closed or runtime.controller is not None:
            return
        try:
            from ..adapters.opkg.backend import OpkgBackend
            from .bootstrap import create_device_app

            backend = OpkgBackend(runtime_root / "usr/bin/opkg")
            controller = create_device_app(backend, device)
            runtime.attach_controller(controller)
            if args.feature:

                def open_feature() -> None:
                    controller.packages.catalogChanged.disconnect(open_feature)
                    if any(
                        item["id"] == args.feature
                        for item in controller.packages.features
                    ):
                        controller.packages.selectFeature(args.feature)
                    else:
                        controller.navigation.navigate("device")

                controller.packages.catalogChanged.connect(open_feature)
            backend.refresh()
        except Exception as error:
            print(f"k2 could not start: {error}", file=sys.stderr)
            app.exit(1)

    runtime.firstFrame.connect(start_application, Qt.QueuedConnection)
    try:
        if not runtime.load():
            return 1
        return app.exec_()
    finally:
        runtime.close()
        device.close()


if __name__ == "__main__":
    raise SystemExit(main())
