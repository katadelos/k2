"""Desktop file-sharing status."""

from ...features.file_sharing.ports import SharingAction, SharingState


class SimulatedFileSharingService:
    def call(self, action: SharingAction) -> SharingState:
        return {
            "schema": 1,
            "running": False,
            "canStart": False,
            "usbBlocked": False,
            "address": "",
            "name": "Kindle",
            "detail": "File Sharing requires a connected reader.",
            "error": "",
        }
