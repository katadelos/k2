"""Merge resolver-selected candidates and installed opkg records."""

from ...core.packages import PROTECTED, CatalogPackage, InstalledPackage
from .parsing import control_records, package_lines


def installed_records(output: str) -> dict[str, dict[str, str]]:
    return {
        item["Package"]: item
        for item in control_records(output)
        if item.get("Status", "").split()[-1:]
        not in ([], ["not-installed"], ["config-files"])
    }


def installed_snapshot(output: str) -> dict[str, InstalledPackage]:
    return {
        name: InstalledPackage(item.get("Version", ""), item["Status"].split()[-1])
        for name, item in installed_records(output).items()
    }


def read_catalog(results: dict[str, str]) -> list[CatalogPackage]:
    # list-candidates delegates version, architecture, hold and provider policy
    # to opkg. Neither traversal order nor Python version sorting reproduces it.
    candidates = {
        item["Requested-Package"]: item
        for item in control_records(results["candidates"])
    }
    installed = installed_records(results["installed"])
    updates = {name: version for name, _, version in package_lines(results["updates"])}
    catalog: list[CatalogPackage] = []
    for name in sorted(candidates.keys() | installed.keys()):
        old = installed.get(name, {})
        details = candidates.get(name, old)
        description = details.get("Description", "Installed package" if old else "")
        catalog.append(
            {
                "name": name,
                "version": details.get("Version", ""),
                "summary": description.splitlines()[0] if description else "",
                "description": description,
                "metadata": details,
                "installed": old.get("Version", ""),
                "installState": old.get("Status", ""),
                "configured": old.get("Status", "").split()[-1:] == ["installed"],
                "update": updates.get(name, ""),
                "available": details.get("Candidate-Available") == "yes",
                "protected": name in PROTECTED
                or details.get("Essential") == "yes"
                or old.get("Essential") == "yes",
            }
        )
    return catalog
