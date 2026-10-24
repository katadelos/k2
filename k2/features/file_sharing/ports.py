"""File-sharing status and command boundary shared with the simulator."""

from typing import Literal, Protocol, TypedDict

type SharingAction = Literal["status-json", "start", "stop"]


class SharingState(TypedDict, total=False):
    schema: int
    running: bool
    canStart: bool
    usbBlocked: bool
    address: str
    name: str
    detail: str
    error: str
    windows: str
    mac: str
    direct: str
    username: str
    password: str
    url: str
    network: str
    qr: list[list[bool]]


class FileSharingBackend(Protocol):
    def call(self, action: SharingAction) -> SharingState: ...
