"""Programmatic view of `ACTION_REGISTRY.md`.

`HERMES_HOME/policies/action_registry.json` is the machine-readable registry a
router reads to pick an `action_id`; `ACTION_REGISTRY.md` stays the
human-readable source of the same records. Nothing here executes an action —
this module only loads and validates records, so a future JEV router can route
on `action_id` instead of generating shell commands.

Usage:
    from registry import load_registry, validate_registry, get_action

    registry = load_registry()
    problems = validate_registry(registry)
    action = get_action(registry, "main.reasoning_fallback")
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home

REQUIRED_FIELDS = (
    "id",
    "type",
    "description",
    "when_to_use",
    "profile",
    "permissions",
    "risk",
    "verification",
    "version",
    "status",
)
ALLOWED_TYPES = frozenset({"agent", "script", "workflow", "tool", "fallback"})
ALLOWED_RISK = frozenset({"low", "medium", "high"})
ALLOWED_STATUS = frozenset({"experimental", "stable", "deprecated", "replaced"})
# Changing state is what makes verification mandatory.
VERIFICATION_REQUIRED_TYPES = frozenset({"script", "workflow", "tool"})
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


def registry_path() -> Path:
    return get_hermes_home() / "policies" / "action_registry.json"


def load_registry(path: Path | None = None) -> dict[str, Any]:
    """Load the registry. Raises FileNotFoundError / ValueError on a bad file."""
    target = path or registry_path()
    data = json.loads(target.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{target} is not a JSON object")
    return data


def action_ids(data: dict[str, Any]) -> list[str]:
    """Every declared action_id, in registry order."""
    return [
        action["id"]
        for action in data.get("actions", [])
        if isinstance(action, dict) and isinstance(action.get("id"), str)
    ]


def get_action(data: dict[str, Any], action_id: str) -> dict[str, Any] | None:
    for action in data.get("actions", []):
        if isinstance(action, dict) and action.get("id") == action_id:
            return action
    return None


def validate_registry(data: dict[str, Any]) -> list[str]:
    """Return every schema violation found; an empty list means valid."""
    actions = data.get("actions")
    if not isinstance(actions, list) or not actions:
        return ["registry has no actions"]

    known = set(action_ids(data))
    errors: list[str] = []
    seen: set[str] = set()

    for index, action in enumerate(actions):
        label = f"actions[{index}]"
        if not isinstance(action, dict):
            errors.append(f"{label} is not an object")
            continue

        action_id = action.get("id")
        if isinstance(action_id, str) and action_id:
            label = action_id

        for field in REQUIRED_FIELDS:
            value = action.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{label}: missing {field}")

        if isinstance(action_id, str):
            if not _ID_PATTERN.match(action_id):
                errors.append(f"{label}: id must be namespace.action_name")
            if action_id in seen:
                errors.append(f"{label}: duplicate id")
            seen.add(action_id)

        if action.get("type") not in ALLOWED_TYPES:
            errors.append(f"{label}: unsupported type {action.get('type')!r}")
        if action.get("risk") not in ALLOWED_RISK:
            errors.append(f"{label}: unsupported risk {action.get('risk')!r}")

        status = action.get("status")
        if status not in ALLOWED_STATUS:
            errors.append(f"{label}: unsupported status {status!r}")
        if action.get("type") in VERIFICATION_REQUIRED_TYPES and not str(action.get("verification", "")).strip():
            errors.append(f"{label}: verification is required for type {action.get('type')}")
        if status == "replaced":
            description = " ".join(str(action.get(key, "")) for key in ("description", "when_to_use", "permissions"))
            replacements = [other for other in known if other != action_id and other in description]
            if not replacements:
                errors.append(f"{label}: replaced action must name its replacement action_id")

    return errors


if __name__ == "__main__":
    registry = load_registry()
    problems = validate_registry(registry)
    print(f"action_registry: {len(action_ids(registry))} action(s)")
    for action_id in action_ids(registry):
        print(f"  - {action_id}")
    if problems:
        print("\n".join(problems))
    else:
        print("registry OK")
    raise SystemExit(1 if problems else 0)
