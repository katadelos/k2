"""Validate KPP's JSON protocols before consuming optional diagnostics."""

import json
from typing import Any


def object_value(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"KPP returned an invalid {label}.")
    return value


def object_list(value: object, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"KPP returned an invalid {label}.")
    return [object_value(item, label) for item in value]


def native_status(text: str) -> dict[str, Any]:
    state = object_value(json.loads(text), "status")
    if type(state.get("manager_running")) is not bool:
        raise ValueError("KPP returned an invalid manager state.")
    for process in object_list(state.get("native", []), "native process list"):
        for entry in object_list(process.get("entries", []), "native log entries"):
            if (
                type(entry.get("priority", 7)) is not int
                or not 0 <= entry.get("priority", 7) <= 7
                or not isinstance(entry.get("module", ""), str)
                or not isinstance(entry.get("message", ""), str)
            ):
                raise ValueError("KPP returned an invalid native log entry.")
    return state


def ui_events(text: str) -> list[dict[str, Any]]:
    state = object_value(json.loads(text), "UI state")
    events = object_list(state.get("events", []), "UI event list")
    result = []
    for event in events:
        if not isinstance(event.get("name"), str):
            raise ValueError("KPP returned an invalid UI event name.")
        if event["name"] != "ui:error":
            continue
        data = object_value(event.get("data", {}), "UI error")
        owner = data.get("owner", event.get("package", ""))
        message = data.get("message", "")
        if not isinstance(owner, str) or not isinstance(message, str):
            raise ValueError("KPP returned invalid UI error details.")
        result.append({"seq": event.get("seq"), "owner": owner, "message": message})
    return result


def packages(text: str) -> dict[str, dict[str, Any]]:
    result = {}
    for package in object_list(json.loads(text), "extension list"):
        identifier, needs = package.get("id"), package.get("needs", [])
        if (
            not isinstance(identifier, str)
            or not identifier
            or identifier in result
            or not isinstance(needs, list)
            or not all(isinstance(name, str) and name for name in needs)
        ):
            raise ValueError("KPP returned an invalid extension definition.")
        result[identifier] = package
    return result
