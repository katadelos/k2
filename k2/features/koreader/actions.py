"""Pure confirmation proposals captured before KOReader changes run."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ...ui.confirmations import ConfirmationContent
from .service import (
    InstallationRequest,
    PluginAction,
    PluginRequest,
    ReaderSelection,
    RemovalRequest,
)

type ReaderRequest = InstallationRequest | RemovalRequest | PluginRequest


@dataclass(frozen=True)
class ReaderProposal:
    content: ConfirmationContent
    request: ReaderRequest


def prepare_action(
    action: str,
    value: str,
    state: dict[str, Any],
    plugins: Sequence[dict[str, Any]],
) -> ReaderProposal | None:
    selection = ReaderSelection(state.get("path", ""), bool(state.get("installed")))
    request: ReaderRequest
    if action == "install":
        if not state.get("canInstall"):
            return None
        label = "Install"
        if state.get("installed"):
            label = "Update" if state.get("updateAvailable") else "Reinstall"
        content = ConfirmationContent(
            title=label + " KOReader?",
            label=label,
            ready=True,
            body=(
                "Install "
                + state.get("releaseVersion", "the latest release")
                + ". Your books, settings and custom plugins are kept."
            ),
        )
        installation = InstallationRequest(selection, state.get("releaseVersion", ""))
        request = installation
    elif action == "uninstall":
        if not state.get("canRemove"):
            return None
        removal = RemovalRequest(selection, tuple(state["identity"]))
        content = ConfirmationContent(
            title="Uninstall KOReader?",
            label="Uninstall",
            ready=True,
            body=(
                "Delete KOReader and everything in this folder, including its plugins, "
                "customisations, settings and reading history:\n\n"
                + removal.selection.path
                + "\n\nBooks outside this folder are kept. The library shortcut added by k2 is also removed. This cannot be undone."
            ),
        )
        request = removal
    elif action == "plugin-install":
        value = value.strip()
        if not value or not state.get("installed"):
            return None
        content = ConfirmationContent(
            title="Install plugin?",
            label="Install",
            ready=True,
            body="Plugins run code in KOReader. Install archives from sources you trust. Existing custom plugins with the same name will be updated.",
        )
        plugin_request = PluginRequest(selection, PluginAction.INSTALL, value)
        request = plugin_request
    elif action == "plugin-remove":
        plugin = next((item for item in plugins if item["id"] == value), None)
        if not plugin or not plugin.get("removable"):
            return None
        content = ConfirmationContent(
            title="Remove " + plugin["name"] + "?",
            label="Remove",
            ready=True,
            body="Remove this plugin and files stored in its folder. KOReader’s settings and reading progress are kept. Restart KOReader afterward.",
        )
        plugin_request = PluginRequest(selection, PluginAction.REMOVE, value)
        request = plugin_request
    else:
        return None
    return ReaderProposal(content, request)
