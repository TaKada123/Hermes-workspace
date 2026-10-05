"""Runtime policy bridge for the customized Hermes fork.

SOUL.md and USER.md are loaded natively by Hermes. This plugin injects the
remaining behavioral policies from HERMES_HOME/policies into bounded,
session-frozen system-prompt sections.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from hermes_constants import get_hermes_home

_GOVERNANCE = (
    "PERMISSIONS.md",
    "EXECUTION_POLICY.md",
    "QUALITY_POLICY.md",
    "ACTIVE_TASKS_POLICY.md",
)
_ARCHITECTURE = (
    "ARCHITECTURE.md",
    "ACTION_REGISTRY.md",
    "SELF_IMPROVEMENT.md",
)


def _compact_policy(text: str) -> str:
    """Remove source metadata/fence noise while preserving behavioral meaning."""
    output: list[str] = []
    skipped_h1 = False
    in_yaml_example = False
    for raw in text.splitlines():
        stripped = raw.strip()
        if in_yaml_example:
            if stripped == "```":
                in_yaml_example = False
            continue
        if stripped == "```yaml":
            in_yaml_example = True
            continue
        if not skipped_h1 and stripped.startswith("# "):
            skipped_h1 = True
            continue
        if stripped.startswith("**Version:**") or stripped.startswith("**Updated:**"):
            continue
        if stripped in {"```", "```text"}:
            continue
        if not stripped:
            continue
        output.append(raw)

    return "\n".join(output).strip()


def _render_group(names: Iterable[str], policy_dir: Path | None = None) -> str:
    root = policy_dir or (get_hermes_home() / "policies")
    blocks: list[str] = []
    for name in names:
        path = root / name
        if not path.is_file():
            continue
        content = _compact_policy(path.read_text(encoding="utf-8-sig"))
        if content:
            blocks.append(f"[{name}]\n{content}")
    body = "\n\n".join(blocks)
    if body:
        body += (
            "\n\nFull schemas/examples remain authoritative in HERMES_HOME/policies. "
            "Before changing profiles, action registry entries, or active-task record formats, "
            "read the relevant source policy file."
        )
    return body


def register(ctx) -> None:
    ctx.register_system_prompt_section(
        "gumar.runtime.01-governance",
        lambda _session: _render_group(_GOVERNANCE),
        position="after_memory",
        max_chars=4000,
    )
    ctx.register_system_prompt_section(
        "gumar.runtime.02-architecture",
        lambda _session: _render_group(_ARCHITECTURE),
        position="after_memory",
        max_chars=4000,
    )
