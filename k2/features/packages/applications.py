"""Package-owned instructions and explicit application launch entries."""

import json
from collections.abc import Iterable
from pathlib import Path

from ...core.packages import Application, CatalogPackage


def empty_application(name: str, error: str = "") -> Application:
    return {
        "name": name,
        "instructions": "",
        "argv": [],
        "canOpen": False,
        "commands": [],
        "error": error,
    }


def describe_application(
    package: CatalogPackage, files: Iterable[str], root: Path
) -> Application:
    result = empty_application(package["name"])
    if not package.get("installed"):
        return result
    if not package.get("configured"):
        result["instructions"] = (
            "Package setup did not finish. Review Activity before using it."
        )
        return result
    descriptor = f"/usr/share/k2/applications/{package['name']}.json"
    paths = {"/" + path.lstrip("./") for path in files}
    if descriptor in paths:
        try:
            path = Path(root) / descriptor.lstrip("/")
            if path.stat().st_size > 32768:
                raise ValueError("Application entry is too large")
            data = json.loads(path.read_text())
            if not isinstance(data, dict):
                raise ValueError("Application entry must be an object")
            argv = data.get("argv", [])
            instructions = data.get("instructions", "")
            name = data.get("name", package["name"])
            if not isinstance(name, str) or not isinstance(instructions, str):
                raise ValueError("Application name and instructions must be text")
            if (
                not isinstance(argv, list)
                or len(argv) > 64
                or any(not isinstance(arg, str) or "\x00" in arg for arg in argv)
                or (argv and (not argv[0].startswith("/") or argv[0] not in paths))
            ):
                raise ValueError(
                    "Launch command must name an executable owned by this package"
                )
            result.update(
                {
                    "name": name,
                    "instructions": instructions,
                    "argv": argv,
                    "canOpen": bool(argv),
                }
            )
        except (OSError, ValueError, TypeError) as error:
            result["error"] = (
                f"Could not read this package’s launch instructions: {error}"
            )
    result["commands"] = sorted(
        {
            Path(path).name
            for path in paths
            if str(Path(path).parent) in {"/usr/bin", "/usr/sbin", "/bin", "/sbin"}
        }
    )
    if not result["instructions"] and not result["canOpen"]:
        if result["commands"]:
            commands = result["commands"]
            result["instructions"] = (
                "Use these commands from a terminal:\n" + ", ".join(commands[:8])
            )
            if len(commands) > 8:
                result["instructions"] += f"\n…and {len(commands) - 8} more."
        else:
            result["instructions"] = (
                "No launch instructions are included with this package."
            )
    return result
