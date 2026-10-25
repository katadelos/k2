"""Package request eligibility and the content of a transaction review."""

from dataclasses import dataclass

from ...core.packages import CatalogPackage, PackagePlan, PackageRequest
from ...ui.confirmations import ConfirmationContent


def _size(value: int) -> str:
    if value >= 1024 * 1024:
        return f"{value / (1024 * 1024):.1f} MB"
    return f"{value / 1024:.0f} KB"


def plan_summary(plan: PackagePlan, request: PackageRequest) -> str:
    if not plan.changes:
        return "Nothing needs to change."
    sentences = []
    for action, verb in (
        ("upgrade", "Update"),
        ("install", "Install"),
        ("remove", "Remove"),
        ("configure", "Finish setting up"),
    ):
        count = sum(change.action == action for change in plan.changes)
        if count:
            sentences.append(f"{verb} {count} package{'s' if count != 1 else ''}.")
    # Installed-Size excludes allocation overhead and package-script effects.
    if plan.download_bytes is not None and request.action != "remove":
        sentences.append(f"Download: up to {_size(plan.download_bytes)}.")
    if plan.restart_reader_required:
        sentences.append("Restart your reader after this change.")
    elif plan.restart_automatically:
        sentences.append("k2 will restart automatically after this update.")
    elif plan.restart_required:
        sentences.append("Exit and reopen k2 after this update.")
    if plan.reload_kpp_required:
        sentences.append(
            "After packages finish, exit k2 and open KPP Mods to apply the changes."
        )
    return " ".join(sentences)


@dataclass(frozen=True)
class PackageReview:
    request: PackageRequest
    title: str
    label: str

    def content(self, success: bool, plan: PackagePlan) -> ConfirmationContent:
        if success:
            body, error = plan_summary(plan, self.request), ""
        else:
            action = {
                "install": "installation",
                "upgrade": "update",
                "remove": "removal",
            }[self.request.action]
            body = f"Couldn’t prepare this {action}."
            error = plan.error or "Couldn’t work out which packages are needed."
        return ConfirmationContent(
            title=self.title,
            label=self.label,
            ready=success and bool(plan.changes),
            body=body,
            error=error,
            changes=tuple(change.to_mapping() for change in plan.changes),
        )


def prepare_review(
    request: PackageRequest, selected: CatalogPackage | None, update_count: int
) -> PackageReview | None:
    action, name = request.action, request.name
    if action == "upgrade" and not name:
        return (
            PackageReview(request, "Update all packages?", "Update all")
            if update_count
            else None
        )
    if (
        action not in {"install", "upgrade", "remove"}
        or not selected
        or name != selected["name"]
    ):
        return None
    if action == "remove" and selected["protected"]:
        return None
    verb = {"install": "Install", "upgrade": "Update", "remove": "Remove"}[action]
    finishing = (
        action == "install" and selected["installed"] and not selected["configured"]
    )
    if finishing:
        verb = "Finish setting up"
    return PackageReview(
        request, f"{verb} {name}?", "Finish setup" if finishing else verb
    )
