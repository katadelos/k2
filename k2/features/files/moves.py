"""Move storage entries without ever replacing a destination entry."""

import ctypes
import errno
import os
import sys
from pathlib import Path

_UNSUPPORTED = {errno.ENOSYS, errno.EINVAL, errno.ENOTSUP, errno.EOPNOTSUPP}


def _exclusive_rename(source: Path, target: Path) -> bool:
    """Return false when this kernel/filesystem lacks exclusive rename."""
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "linux":
        rename = getattr(libc, "renameat2", None)
        if rename is None:
            return False
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        # AT_FDCWD and RENAME_NOREPLACE from Linux's public ABI. Older kernels
        # and filesystems (including pre-4.9 vfat) can reject this operation.
        result = rename(-100, os.fsencode(source), -100, os.fsencode(target), 1)
    elif sys.platform == "darwin":
        rename = libc.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(os.fsencode(source), os.fsencode(target), 4)  # RENAME_EXCL
    else:
        return False
    if result == 0:
        return True
    error = ctypes.get_errno()
    if error in _UNSUPPORTED:
        return False
    raise OSError(error, os.strerror(error), str(target))


def move_without_replacing(source: Path, target: Path) -> None:
    """Leave both paths untouched when atomic exclusive rename is unavailable."""
    if _exclusive_rename(source, target):
        return
    raise OSError(
        "This filesystem cannot safely rename or move this item without "
        "replacing another item. Copy it, then delete the original."
    )
