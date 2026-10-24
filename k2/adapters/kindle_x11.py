"""Use the Kindle X server's grayscale visual and window-scoped refresh API."""

import ctypes
import os


def grayscale_visual():
    class VisualInfo(ctypes.Structure):
        _fields_ = [
            ("visual", ctypes.c_void_p),
            ("visualid", ctypes.c_ulong),
            ("screen", ctypes.c_int),
            ("depth", ctypes.c_int),
            ("visual_class", ctypes.c_int),
            ("red_mask", ctypes.c_ulong),
            ("green_mask", ctypes.c_ulong),
            ("blue_mask", ctypes.c_ulong),
            ("colormap_size", ctypes.c_int),
            ("bits_per_rgb", ctypes.c_int),
        ]

    # Load the SDK's XCB provider before stock X11 can pull in its older copy.
    # Both libraries share a SONAME; the first loaded copy is reused by Qt.
    _xcb = ctypes.CDLL("libxcb.so.1")
    # The ABI profile supplies X11 through either the SDK or stock firmware.
    # Resolve its SONAME with the same loader search path as the Qt platform.
    x11 = ctypes.CDLL("libX11.so.6")
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XDefaultScreen.argtypes = [ctypes.c_void_p]
    x11.XDefaultScreen.restype = ctypes.c_int
    x11.XMatchVisualInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(VisualInfo),
    ]
    x11.XMatchVisualInfo.restype = ctypes.c_int
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    display = x11.XOpenDisplay(os.environ.get("DISPLAY", ":0").encode())
    if not display:
        raise RuntimeError("Cannot connect to the Kindle X display")
    try:
        visual = VisualInfo()
        # StaticGray = 0. PseudoColor, the server's default, has no Qt raster
        # paint engine; StaticGray supplies the native 8-bit intensity ramp.
        if not x11.XMatchVisualInfo(
            display, x11.XDefaultScreen(display), 8, 0, ctypes.byref(visual)
        ):
            raise RuntimeError("The Kindle X display has no 8-bit grayscale visual")
        return hex(visual.visualid)
    finally:
        x11.XCloseDisplay(display)
