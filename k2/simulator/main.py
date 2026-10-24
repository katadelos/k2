"""Desktop and headless entry point."""

import argparse
import os

from PyQt5.QtGui import QGuiApplication

from ..ui.runtime import Runtime
from .backends.device import SimulatedDevice
from .backends.packages import SimulatedPackages
from .bootstrap import create_simulated_app
from .capture import install_capture
from .console import Console
from .scenarios import PROFILES


def main():
    parser = argparse.ArgumentParser(description="k2 PC simulator (no device writes)")
    parser.add_argument("--device", choices=PROFILES, default="pw5")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="reload QML while retaining controller state",
    )
    parser.add_argument(
        "--screenshot", help="save a frame; with --watch, refresh it after edits"
    )
    parser.add_argument(
        "--page",
        choices=(
            "home",
            "apps",
            "device",
            "storage",
            "files",
            "about",
            "activity",
            "koreader",
            "koreader-customise",
        ),
        default="home",
    )
    parser.add_argument(
        "--scenario",
        choices=(
            "normal",
            "empty",
            "offline",
            "loading",
            "supernet",
            "supernet-setup",
            "home-assistant",
            "koreader-installed",
            "koreader-conflict",
            "koreader-offline",
        ),
        default="normal",
    )
    parser.add_argument("--scale", type=float, help="window scale (headless default 1)")
    args = parser.parse_args()
    if args.scale is not None and not 0.1 <= args.scale <= 2:
        parser.error("--scale must be between 0.1 and 2")
    if args.headless:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    if args.headless:
        os.environ["QT_QUICK_BACKEND"] = "software"
    else:
        os.environ.pop("QT_QUICK_BACKEND", None)
    os.environ["QML_DISABLE_DISK_CACHE"] = "1"
    app = QGuiApplication(["k2-sim"])
    width, height, _, _ = PROFILES[args.device]
    scale = args.scale or (
        1
        if args.headless
        else min(0.9 * app.primaryScreen().availableGeometry().height() / height, 1)
    )
    packages = SimulatedPackages(args.scenario)
    controller = create_simulated_app(
        packages, SimulatedDevice(args.device, args.scenario), args.page
    )
    runtime = Runtime(app, controller, width, height, scale=scale)
    try:
        if not runtime.load():
            return 1
        packages.refresh()
        if args.watch:
            runtime.watch()
        if args.screenshot:
            install_capture(
                runtime, args.screenshot, watch=args.watch, scenario=args.scenario
            )
        if args.headless and (not args.screenshot or args.watch):
            Console(runtime)
        return app.exec_()
    finally:
        runtime.close()


if __name__ == "__main__":
    raise SystemExit(main())
