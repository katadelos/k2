"""Load selected upstream screenshots on demand, keeping a local viewing cache."""

import tempfile
from pathlib import Path

from PyQt5.QtGui import QImageReader

from .http import open_https

PREVIEWS = {
    "simpleui": "https://github.com/user-attachments/assets/4ea92760-c2bf-488b-9f5a-1f663157c97f",
    "zenos": "https://raw.githubusercontent.com/xZenLabs/zen-os/v4.0.1/images/quickstart/onboarding/library_covers_full.png",
    "bookshelf": "https://raw.githubusercontent.com/AndyHazz/bookshelf.koplugin/v5.3.1/assets/screenshot-home.png",
    "bookends": "https://raw.githubusercontent.com/AndyHazz/bookends.koplugin/v5.29.1/screenshots/preset-gallery.png",
}


def load_preview(item_id: str, cache: str | Path, offline: bool = False) -> str:
    if item_id not in PREVIEWS:
        raise ValueError("This customisation does not have an upstream preview.")
    directory = Path(cache)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (item_id + "-20261003.img")
    if target.is_file() and not target.is_symlink():
        return target.resolve().as_uri()
    if offline:
        raise OSError("Could not load the preview. Check Wi-Fi and try again.")
    temporary = None
    try:
        with (
            open_https(
                PREVIEWS[item_id],
                headers={"User-Agent": "k2/0.1 KOReader previews"},
                timeout=20,
            ) as response,
            tempfile.NamedTemporaryFile(dir=directory, delete=False) as out,
        ):
            temporary = Path(out.name)
            size = 0
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > 6 * 1024 * 1024:
                    raise ValueError("The upstream preview is too large to display.")
                out.write(chunk)
        reader = QImageReader(str(temporary))
        dimensions = reader.size()
        if (
            not reader.canRead()
            or dimensions.width() <= 0
            or dimensions.height() <= 0
            or dimensions.width() * dimensions.height() > 16000000
        ):
            raise ValueError("The upstream preview is not a supported image.")
        temporary.replace(target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target.resolve().as_uri()
