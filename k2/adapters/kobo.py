"""Kobo controls through the e-reader HAL."""

from .device import Device


class KoboDevice(Device):
    def __init__(self) -> None:
        super().__init__("kobo")
