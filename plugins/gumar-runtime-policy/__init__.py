"""Runtime policy bridge for the customized Hermes fork.

SOUL.md and USER.md are loaded natively by Hermes. This plugin keeps the
always-on runtime prompt to the minimum: it injects only the rule-bearing
sections of `HERMES_HOME/policies`, verbatim (markdown structure stripped), and
points at everything else as on-demand reading, so full policy text never costs
prompt space on every request.

Always-on:
- `MASTER_SPEC.md` — only its instruction priority and source-of-truth core;
- `PERMISSIONS.md`, `EXECUTION_POLICY.md`, `RESPONSE_POLICY.md` — only their
  rule sections;
- `MEMORY_POLICY.md` — only the memory mode plus the save/secret rules;
- `SELF_IMPROVEMENT.md` — only the two runtime skill rules, because
  `skill_manage` is deferred and its native prompt guidance is gated on the
  tool being visible.
- Main profile only — one short Design Agent routing hint. No design manual,
  skill body or Design memory is injected.

Never injected:
- `ARCHITECTURE.md` and `ACTION_REGISTRY.md` (read on demand; the registry is
  also exposed programmatically through `policies/action_registry.json`);
- `CHANGELOG.md` (audit only);
- `reference/HERMES_USER_PROFILE.md` (provenance, not installed).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from hermes_constants import get_hermes_home

SECTION_IDS = (
    "gumar.runtime.01-governance",
    "gumar.runtime.02-memory-and-skills",
    "gumar.runtime.03-main-router",
)

# (policy file, H2 headings) whose rules stay in every request.
GOVERNANCE_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "PERMISSIONS.md",
        (
            "LOW RISK — самостоятельно",
            "MEDIUM RISK — при наличии защиты",
            "HIGH RISK — подтверждение обязательно",
        ),
    ),
    ("EXECUTION_POLICY.md", ("Главный принцип", "Рабочий порядок", "Интернет")),
    (
        "RESPONSE_POLICY.md",
        ("Первые строки", "Глубина", "Незнакомая тема", "Практические задачи", "Рекомендации"),
    ),
)
MEMORY_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("MEMORY_POLICY.md", ("Запись и обновление", "Не сохранять автоматически", "Секреты")),
)
# `skill_manage` is deferred (tools.tool_search.defer), and Hermes gates its native
# skill guidance on that tool being visible — so the two rules it carried live here.
SKILLS_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("SELF_IMPROVEMENT.md", ("Runtime-правила скиллов",)),
)
MASTER_SPEC_FILE = "MASTER_SPEC.md"
MASTER_CORE_SECTIONS = ("Приоритет инструкций", "Source of truth")
# Metadata key copied from the memory policy header (the line above its first H2).
MEMORY_HEADER_KEYS = ("Mode:",)
DESIGN_ROUTING_HINT = (
    "Design routing: Main обязан передавать запросы о дизайне, сайтах, презентациях, портфолио, "
    "визуальных системах, графике, layout, branding или visual editing в on-demand skill `design-router` "
    "через action `design.route`; не выполнять их в Main."
)

# On-demand pointers: (when it applies, policy file to read first).
ON_DEMAND: tuple[tuple[str, str], ...] = (
    ("архитектура, Profile, specialist, subagent, делегирование", "ARCHITECTURE.md"),
    ("выбор, регистрация или изменение действия", "ACTION_REGISTRY.md"),
    ("уровни памяти CORE/DOMAIN/EPISODIC и изоляция агентов", "MEMORY_POLICY.md"),
    ("новый постоянный script или action", "EXECUTION_POLICY.md"),
    ("финальный quality gate", "QUALITY_POLICY.md"),
    ("перевод проверенного решения в reusable/stable", "SELF_IMPROVEMENT.md"),
    ("временные задачи, планы и их статусы", "ACTIVE_TASKS_POLICY.md"),
)
REGISTRY_FILE = "action_registry.json"
_METADATA_KEYS = ("Version:", "Updated:", "Mode:", "Status:")


def compact(text: str) -> str:
    """Drop markdown headings, metadata lines and fenced schemas/examples."""
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
        if stripped.startswith("**") and any(key in stripped for key in _METADATA_KEYS):
            continue
        output.append(stripped)

    return "\n".join(output).strip()


def _read(policy_dir: Path, name: str) -> str:
    path = policy_dir / name
    return path.read_text(encoding="utf-8-sig") if path.is_file() else ""


def _section(text: str, heading: str, *, label: bool = True) -> str:
    """Body of one H2 section, markdown structure stripped.

    The heading is kept as a leading label: without it a rule list loses its
    meaning (which risk tier, which memory rule) once markdown is stripped.
    """
    marker = f"## {heading}"
    lines = text.splitlines()
    start = next((index for index, line in enumerate(lines) if line.strip() == marker), None)
    if start is None:
        return ""

    body: list[str] = []
    for raw in lines[start + 1 :]:
        if raw.startswith("## "):
            break
        if raw.strip():
            body.append(raw)
    compacted = compact("\n".join(body))
    if not compacted:
        return ""
    return f"{heading}:\n{compacted}" if label else compacted


def _header_value(text: str, key: str) -> str:
    """A `**Key:** value` metadata line from the file header, above the first H2."""
    for raw in text.splitlines():
        if raw.startswith("## "):
            return ""
        line = raw.strip()
        if line.startswith("**") and key in line:
            return line.replace("**", "").strip()
    return ""


def extract_section(policy_dir: Path, name: str, heading: str) -> str:
    """Resolve one declared always-on section (the verifier uses this seam)."""
    return _section(_read(policy_dir, name), heading)


def declared_sections() -> tuple[tuple[str, str], ...]:
    """(file, heading) pairs that must resolve to non-empty always-on rules."""
    pairs = [
        (name, heading)
        for name, headings in GOVERNANCE_SECTIONS + MEMORY_SECTIONS + SKILLS_SECTIONS
        for heading in headings
    ]
    pairs += [(MASTER_SPEC_FILE, heading) for heading in MASTER_CORE_SECTIONS]
    return tuple(pairs)


def _render_files(policy_dir: Path, spec: Iterable[tuple[str, tuple[str, ...]]]) -> str:
    blocks: list[str] = []
    for name, headings in spec:
        text = _read(policy_dir, name)
        if not text:
            continue
        body = "\n".join(part for part in (_section(text, heading) for heading in headings) if part)
        if body:
            blocks.append(f"[{name}]\n{body}")
    return "\n\n".join(blocks)


def _render_governance() -> str:
    policy_dir = get_hermes_home() / "policies"
    master = _read(policy_dir, MASTER_SPEC_FILE)
    core = "\n".join(
        part
        for part in (_section(master, heading, label=False) for heading in MASTER_CORE_SECTIONS)
        if part
    )
    parts = [
        f"[{MASTER_SPEC_FILE} core]\n{core}" if core else "",
        _render_files(policy_dir, GOVERNANCE_SECTIONS),
    ]
    return "\n\n".join(part for part in parts if part)


def _render_main_router() -> str:
    home = get_hermes_home()
    return "" if home.name == "design" and home.parent.name == "profiles" else DESIGN_ROUTING_HINT


def _on_demand_index() -> str:
    items = "; ".join(f"{when}→{name}" for when, name in ON_DEMAND)
    return (
        "[On demand — прочитать названный файл перед такой работой]\n"
        f"{items}.\n"
        f"Действия выбираются только по зарегистрированному action_id из policies/{REGISTRY_FILE}; "
        "произвольные shell-команды запрещены. CHANGELOG.md никогда не загружается в prompt."
    )


def _render_memory() -> str:
    policy_dir = get_hermes_home() / "policies"
    text = _read(policy_dir, "MEMORY_POLICY.md")
    header = " ".join(value for value in (_header_value(text, key) for key in MEMORY_HEADER_KEYS) if value)
    blocks = [
        part
        for part in (
            header,
            _render_files(policy_dir, MEMORY_SECTIONS),
            _render_files(policy_dir, SKILLS_SECTIONS),
        )
        if part
    ]
    return "\n\n".join(blocks) + "\n\n" + _on_demand_index()


def register(ctx) -> None:
    ctx.register_system_prompt_section(
        SECTION_IDS[0],
        lambda _session: _render_governance(),
        position="after_memory",
        max_chars=3900,
    )
    ctx.register_system_prompt_section(
        SECTION_IDS[1],
        lambda _session: _render_memory(),
        position="after_memory",
        max_chars=3000,
    )
    ctx.register_system_prompt_section(
        SECTION_IDS[2],
        lambda _session: _render_main_router(),
        position="after_memory",
        max_chars=500,
    )
