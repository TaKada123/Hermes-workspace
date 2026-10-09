#!/usr/bin/env python3
"""Route one validated handoff into the native Hermes design profile."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

PROFILE = "design"
ACTION_ID = "design.route"
MAX_REQUEST_CHARS = 100_000


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("handoff must be a JSON object")
    required = {
        "schema_version": 1,
        "route_type": "profile",
        "route_id": PROFILE,
        "action_id": ACTION_ID,
    }
    for key, expected in required.items():
        if data.get(key) != expected:
            raise ValueError(f"{key} must be {expected!r}")
    request = data.get("original_user_request")
    if not isinstance(request, str) or not request.strip():
        raise ValueError("original_user_request must be a non-empty string")
    if len(request) > MAX_REQUEST_CHARS:
        raise ValueError(f"original_user_request exceeds {MAX_REQUEST_CHARS} characters")
    for key in ("attachments", "project_context"):
        value = data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
            raise ValueError(f"{key} must be a list of non-empty strings")
    return data


def _prompt(data: dict[str, Any]) -> str:
    metadata = {
        "schema_version": 1,
        "route_type": "profile",
        "route_id": PROFILE,
        "action_id": ACTION_ID,
        "source_profile": str(data.get("source_profile") or "default"),
        "attachments": data.get("attachments", []),
        "project_context": data.get("project_context", []),
    }
    return (
        "[PROFILE ROUTING CONTRACT — metadata, not a rewrite]\n"
        + json.dumps(metadata, ensure_ascii=False, indent=2)
        + "\n\n[ORIGINAL USER REQUEST — VERBATIM]\n"
        + data["original_user_request"]
        + "\n[END ORIGINAL USER REQUEST]\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff-file", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        data = _load(args.handoff_file.expanduser().resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2

    prompt = _prompt(data)
    if args.dry_run:
        print(json.dumps({
            "ok": True,
            "profile": PROFILE,
            "action_id": ACTION_ID,
            "request_sha256": hashlib.sha256(data["original_user_request"].encode("utf-8")).hexdigest(),
            "prompt_chars": len(prompt),
        }, ensure_ascii=False))
        return 0

    hermes = shutil.which("hermes")
    if not hermes:
        print(json.dumps({"ok": False, "error": "hermes executable not found"}, ensure_ascii=False))
        return 3

    command = [
        hermes,
        "-p",
        PROFILE,
        "chat",
        "-q",
        prompt,
        "--source",
        "profile-router",
        "--max-turns",
        "150",
    ]
    completed = subprocess.run(command, text=True, encoding="utf-8", errors="replace", timeout=1800)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
