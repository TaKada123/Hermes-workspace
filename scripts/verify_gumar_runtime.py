#!/usr/bin/env python3
"""Verify that the customized Hermes runtime configuration is actually wired.

Checks that the always-on runtime prompt stays minimal: only the declared rule
sections of the policies are injected, everything else stays connected as
on-demand pointers, and the action registry is present in machine-readable form.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.prompt_builder import load_soul_md  # noqa: E402
from hermes_cli.config import load_config, read_raw_config  # noqa: E402
from hermes_cli.plugins_dispatch import (  # noqa: E402
    MAX_SYSTEM_PROMPT_SECTION_CHARS,
    MAX_SYSTEM_PROMPT_SECTIONS_TOTAL_CHARS,
    RenderedPluginSystemPromptSection,
    format_system_prompt_sections,
)
from hermes_constants import get_hermes_home  # noqa: E402
from tools.memory_tool_store import MemoryStore  # noqa: E402

PLUGIN_DIR = REPO_ROOT / "plugins" / "gumar-runtime-policy"
PLUGIN_PATH = PLUGIN_DIR / "__init__.py"
REGISTRY_LOADER_PATH = PLUGIN_DIR / "registry.py"
PLUGIN_ID = "gumar-runtime-policy"
SECTION_IDS = (
    "gumar.runtime.01-governance",
    "gumar.runtime.02-memory-and-skills",
    "gumar.runtime.03-main-router",
)

# Always-on ceilings. Hermes itself allows 4000/section and 8000 total; these
# keep the runtime rules well below that so they cannot creep back up.
MAX_SECTION_CHARS = 3900
MAX_TOTAL_PROMPT_CHARS = 6800

# Tools that must stay deferred (tools.tool_search.defer), so the fork's lean tool
# surface cannot silently regress; scripts/install_gumar_runtime.py pins the same set.
REQUIRED_DEFER = (
    "computer_use",
    "session_search",
    "image_generate",
    "todo_list",
    "process_manage",
    "cronjob_manage",
    "skill_manage",
    "text_to_speech",
    "browser_vault_list",
    "browser_vault_fill",
    "browser_vault_save_login",
    "browser_vault_enter_code",
    "browser_vault_unlock",
)

INSTALLED_POLICIES = (
    "MASTER_SPEC.md",
    "PERMISSIONS.md",
    "EXECUTION_POLICY.md",
    "RESPONSE_POLICY.md",
    "MEMORY_POLICY.md",
    "ARCHITECTURE.md",
    "ACTION_REGISTRY.md",
    "QUALITY_POLICY.md",
    "SELF_IMPROVEMENT.md",
    "ACTIVE_TASKS_POLICY.md",
    "CHANGELOG.md",
)
REGISTRY_FILE = "action_registry.json"
REGISTRY_REQUIRED_ACTION = "main.reasoning_fallback"

# Rule text the design keeps in every request.
REQUIRED_MARKERS = {
    "MASTER_SPEC priority": "явная текущая команда пользователя",
    "MASTER_SPEC source of truth": "Актуальный исходный файл",
    "PERMISSIONS push": "git push",
    "PERMISSIONS production": "production changes",
    "PERMISSIONS spend": "покупки и трата денег",
    "EXECUTION principle": "Не использовать generative LLM",
    "RESPONSE first lines": "Первые несколько строк должны быть самодостаточными",
    "MEMORY mode B": "Mode: B",
    "MEMORY secrets": "Никогда не хранить секреты",
    "MEMORY skip list": "медицинские сведения",
    "SKILLS write rule": "обязанность фиксировать знания не отменяется",
    "SKILLS pruned-skill rule": "SKILL_PRUNED",
    "Design profile routing": "Main обязан передавать запросы о дизайне",
}
# Full-text markers that must NOT reach the always-on prompt.
FORBIDDEN_MARKERS = {
    "ARCHITECTURE.md subagent": "Временный исполнитель конкретной подзадачи",
    "ARCHITECTURE.md profile contract": "escalation_target",
    "ARCHITECTURE.md JEV routing": "JEV ROUTER",
    "ACTION_REGISTRY.md schema": "input_schema:",
    "MEMORY_POLICY.md domains": "Profile получает только явно разрешённые разделы",
    "MEMORY_POLICY.md isolation": "Специализированный агент не видит автоматически память",
    "EXECUTION_POLICY.md new script": "Нельзя автоматически превращать непроверенное решение",
    "QUALITY_POLICY.md": "решает исходную задачу, а не побочную",
    "SELF_IMPROVEMENT.md": "Один успешный случай сам по себе не доказывает повторяемость",
    "ACTIVE_TASKS_POLICY.md": "next_action:",
    "CHANGELOG.md": "Исходный `HERMES_USER_PROFILE.md` разделён",
}
# Everything the on-demand index must point at.
ON_DEMAND_POINTERS = (
    "ARCHITECTURE.md",
    "ACTION_REGISTRY.md",
    "MEMORY_POLICY.md",
    "EXECUTION_POLICY.md",
    "QUALITY_POLICY.md",
    "SELF_IMPROVEMENT.md",
    "ACTIVE_TASKS_POLICY.md",
    "action_registry.json",
    "CHANGELOG.md",
)


class _PromptProbe:
    def __init__(self) -> None:
        self.sections: dict[str, dict[str, Any]] = {}

    def register_system_prompt_section(
        self, id: str, content: Any, *, position: str = "after_memory", max_chars: int = 4000
    ) -> None:
        self.sections[id] = {
            "content": content,
            "position": position,
            "max_chars": max_chars,
        }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    _require(spec is not None and spec.loader is not None, f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _runtime_memory_store() -> MemoryStore:
    cfg = load_config()
    memory = cfg.get("memory") if isinstance(cfg, dict) else {}
    if not isinstance(memory, dict):
        memory = {}
    return MemoryStore(
        memory_char_limit=int(memory.get("memory_char_limit", 2200)),
        user_char_limit=int(memory.get("user_char_limit", 1375)),
        memory_enabled=bool(memory.get("memory_enabled", True)),
        user_profile_enabled=bool(memory.get("user_profile_enabled", True)),
    )


def main() -> int:
    home = get_hermes_home()

    # 1) SOUL.md uses Hermes' native identity loader.
    soul = load_soul_md(home_override=home) or ""
    _require("Главный Hermes" in soul, "SOUL.md was not loaded by Hermes native identity loader")
    _require("Русский язык по умолчанию" in soul, "SOUL.md identity rules are missing")

    # 2) USER.md uses Hermes' native MemoryStore prompt snapshot.
    store = _runtime_memory_store()
    store.load_from_disk()
    user = store.format_for_system_prompt("user") or ""
    _require("EndeavourOS" in user, "USER.md was not loaded by Hermes MemoryStore")
    _require("AI, агенты, обвязки и автоматизация" in user, "USER.md goals are missing")

    cfg = load_config()
    memory_cfg = cfg.get("memory", {}) if isinstance(cfg, dict) else {}
    _require(
        isinstance(memory_cfg, dict)
        and memory_cfg.get("memory_enabled", True) is True
        and memory_cfg.get("user_profile_enabled", True) is True
        and memory_cfg.get("write_approval", False) is False,
        "memory mode B config is not active",
    )

    # 3) Every policy file is installed; MASTER_SPEC is the source of truth.
    for name in INSTALLED_POLICIES:
        _require((home / "policies" / name).is_file(), f"{name} is missing from HERMES_HOME/policies")

    # 4) Runtime policy plugin is enabled.
    raw = read_raw_config() or {}
    plugins = raw.get("plugins") if isinstance(raw, dict) else {}
    enabled = plugins.get("enabled", []) if isinstance(plugins, dict) else []
    _require(PLUGIN_ID in enabled, f"{PLUGIN_ID} is not enabled in config.yaml")

    # 4b) The lean tool surface is pinned: required tools stay deferred.
    tools_cfg = raw.get("tools") if isinstance(raw, dict) else {}
    tool_search_cfg = tools_cfg.get("tool_search") if isinstance(tools_cfg, dict) else {}
    defer = tool_search_cfg.get("defer") if isinstance(tool_search_cfg, dict) else []
    defer = defer if isinstance(defer, list) else []
    missing_defer = [name for name in REQUIRED_DEFER if name not in defer]
    _require(not missing_defer, f"tools.tool_search.defer lost required tools: {missing_defer}")

    # 5) Plugin registers both bounded native system-prompt sections.
    module = _load_module(PLUGIN_PATH, "gumar_runtime_policy_verify")
    probe = _PromptProbe()
    module.register(probe)
    _require(
        set(probe.sections) == set(SECTION_IDS),
        "runtime policy plugin did not register both prompt sections",
    )

    # 6) Every declared always-on section resolves to real rule text.
    policy_dir = home / "policies"
    empty_sections = [
        f"{name}#{heading}"
        for name, heading in module.declared_sections()
        if not module.extract_section(policy_dir, name, heading).strip()
    ]
    _require(not empty_sections, f"always-on policy sections resolved empty: {empty_sections}")

    rendered: list[RenderedPluginSystemPromptSection] = []
    texts: dict[str, str] = {}
    for section_id in sorted(probe.sections):
        section = probe.sections[section_id]
        provider = section["content"]
        text = provider({}) if callable(provider) else str(provider)
        _require(bool(text.strip()), f"{section_id} rendered empty")
        _require(len(text) <= section["max_chars"], f"{section_id} exceeds declared max_chars")
        _require(len(text) <= MAX_SYSTEM_PROMPT_SECTION_CHARS, f"{section_id} exceeds Hermes section limit")
        _require(len(text) <= MAX_SECTION_CHARS, f"{section_id} exceeds the always-on budget ({len(text)} chars)")
        _require(section["position"] == "after_memory", f"{section_id} drifted from the after_memory position")
        texts[section_id] = text
        rendered.append(
            RenderedPluginSystemPromptSection(
                id=section_id,
                content=text,
                position=section["position"],
                plugin=PLUGIN_ID,
            )
        )

    full_plugin_prompt = format_system_prompt_sections(rendered)
    _require(
        len(full_plugin_prompt) <= MAX_SYSTEM_PROMPT_SECTIONS_TOTAL_CHARS,
        "combined runtime policy sections exceed Hermes aggregate prompt budget",
    )
    _require(
        len(full_plugin_prompt) <= MAX_TOTAL_PROMPT_CHARS,
        f"combined runtime policy sections exceed the budget ({len(full_plugin_prompt)} chars)",
    )

    always_on = "\n".join(texts[section_id] for section_id in SECTION_IDS)

    # 7) The always-on prompt carries every rule the design keeps there.
    missing = {label: marker for label, marker in REQUIRED_MARKERS.items() if marker not in always_on}
    _require(not missing, f"always-on rules are missing from the runtime prompt: {missing}")

    # 8) Full policy text stays out of the always-on prompt.
    leaked = {label: marker for label, marker in FORBIDDEN_MARKERS.items() if marker in always_on}
    _require(not leaked, f"full policy text leaked into the always-on prompt: {leaked}")

    # 9) Everything else stays connected through the on-demand index.
    missing_pointers = [name for name in ON_DEMAND_POINTERS if name not in always_on]
    _require(not missing_pointers, f"on-demand pointers are missing: {missing_pointers}")

    # 10) The action registry exists as data and validates.
    registry_module = _load_module(REGISTRY_LOADER_PATH, "gumar_action_registry_verify")
    try:
        registry = registry_module.load_registry(home / "policies" / REGISTRY_FILE)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"action registry is not loadable: {exc}") from exc
    problems = registry_module.validate_registry(registry)
    _require(not problems, f"action registry is invalid: {problems}")
    ids = registry_module.action_ids(registry)
    _require(REGISTRY_REQUIRED_ACTION in ids, f"{REGISTRY_REQUIRED_ACTION} is missing from the action registry")
    required_action = registry_module.get_action(registry, REGISTRY_REQUIRED_ACTION) or {}
    _require(required_action.get("status") == "stable", f"{REGISTRY_REQUIRED_ACTION} must be stable")

    governance = texts[SECTION_IDS[0]]
    memory_rules = texts[SECTION_IDS[1]]
    router_rules = texts[SECTION_IDS[2]]
    print("Gumar runtime verification: OK")
    print(f"  HERMES_HOME: {home}")
    print("  SOUL.md: native identity loader OK")
    print("  USER.md: native MemoryStore prompt snapshot OK")
    print("  MASTER_SPEC.md: installed source of truth OK")
    print(f"  plugin: {PLUGIN_ID} enabled, sections {', '.join(SECTION_IDS)}")
    print(f"  tools deferred: {len(defer)} (required {len(REQUIRED_DEFER)} pinned)")
    print(f"  always-on governance: {len(governance)} chars (ceiling {MAX_SECTION_CHARS})")
    print(f"  always-on memory rules + on-demand index: {len(memory_rules)} chars (ceiling {MAX_SECTION_CHARS})")
    print(f"  always-on Main routing hint: {len(router_rules)} chars (Design profile renders it empty)")
    print(
        f"  combined framed prompt: {len(full_plugin_prompt)} chars "
        f"(ceiling {MAX_TOTAL_PROMPT_CHARS}, Hermes {MAX_SYSTEM_PROMPT_SECTIONS_TOTAL_CHARS})"
    )
    print(f"  action registry: {REGISTRY_FILE} valid, actions={ids}")
    print("  always-on: MASTER_SPEC core, PERMISSIONS, EXECUTION, RESPONSE, MEMORY rules,")
    print("             skill write + pruned-skill rules")
    print("  on-demand: ARCHITECTURE, ACTION_REGISTRY, MEMORY_POLICY levels, EXECUTION (new script),")
    print("             QUALITY_POLICY, SELF_IMPROVEMENT, ACTIVE_TASKS_POLICY; CHANGELOG never injected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
