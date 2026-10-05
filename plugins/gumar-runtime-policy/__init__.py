"""Runtime policy bridge for the customized Hermes fork.

SOUL.md and USER.md are loaded natively by Hermes. This plugin injects the
minimum always-on policy context from HERMES_HOME/policies. MASTER_SPEC stays
the human-readable source of truth; only its priority/source-of-truth clauses
are injected. Large schemas/examples remain in their source files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from hermes_constants import get_hermes_home

_GOVERNANCE = (
    "PERMISSIONS.md",
    "EXECUTION_POLICY.md",
    "RESPONSE_POLICY.md",
)
_SYSTEM = (
    "ARCHITECTURE.md",
    "ACTION_REGISTRY.md",
    "MEMORY_POLICY.md",
)


def _compact_policy(text: str) -> str:
    """Drop markdown structure/examples while preserving executable prose."""
    output: list[str] = []
    in_fence = False

    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("**") and any(
            key in stripped for key in ("Version:", "Updated:", "Mode:", "Status:")
        ):
            continue
        output.append(stripped)

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
    return "\n\n".join(blocks)


def _extract_h2(text: str, heading: str) -> str:
    """Return one H2 section body from MASTER_SPEC without loading the whole spec."""
    lines = text.splitlines()
    marker = f"## {heading}"
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == marker)
    except StopIteration:
        return ""

    body: list[str] = []
    for raw in lines[start + 1 :]:
        if raw.startswith("## "):
            break
        stripped = raw.strip()
        if stripped:
            body.append(stripped)
    return "\n".join(body)


def _render_governance() -> str:
    root = get_hermes_home() / "policies"
    master_path = root / "MASTER_SPEC.md"
    master_blocks: list[str] = []
    if master_path.is_file():
        master = master_path.read_text(encoding="utf-8-sig")
        priority = _extract_h2(master, "Приоритет инструкций")
        source = _extract_h2(master, "Source of truth")
        if priority:
            master_blocks.append(f"[Priority]\n{priority}")
        if source:
            master_blocks.append(f"[Source of truth]\n{source}")

    policy = _render_group(_GOVERNANCE, root)
    return "\n\n".join(part for part in ("\n\n".join(master_blocks), policy) if part)


def register(ctx) -> None:
    ctx.register_system_prompt_section(
        "gumar.runtime.01-governance",
        lambda _session: _render_governance(),
        position="after_memory",
        max_chars=4000,
    )
    ctx.register_system_prompt_section(
        "gumar.runtime.02-architecture",
        lambda _session: _render_group(_SYSTEM) + "\n\n[On demand] quality→QUALITY_POLICY.md; reuse→SELF_IMPROVEMENT.md; tasks→ACTIVE_TASKS_POLICY.md.",
        position="after_memory",
        max_chars=4000,
    )
