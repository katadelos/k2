"""Read installed file lists from the SDK opkg configuration."""

import shlex
from dataclasses import dataclass
from pathlib import Path

from .parsing import PACKAGE_NAME


@dataclass(frozen=True)
class PackageFiles:
    """Filesystem reader that can be captured independently of the Qt backend."""

    config_dir: Path

    def __call__(self, name: str) -> list[str]:
        if not PACKAGE_NAME.fullmatch(name):
            return []
        info_dir = Path("/var/lib/opkg/info")
        for config in sorted(self.config_dir.glob("*.conf")):
            try:
                for line in config.read_text().splitlines():
                    fields = shlex.split(line, comments=True)
                    if len(fields) == 3 and fields[:2] == ["option", "info_dir"]:
                        info_dir = Path(fields[2])
            except OSError, ValueError:
                continue
        files = [
            line.split("\t", 1)[0]
            for line in (info_dir / (name + ".list")).read_text().splitlines()
            if line.startswith("/")
        ]
        sdk_prefix = str(self.config_dir.parent) + "/"
        return [
            "/" + path[len(sdk_prefix) :] if path.startswith(sdk_prefix) else path
            for path in files
        ]
