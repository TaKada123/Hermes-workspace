#!/usr/bin/env python3
"""Verify that the customized Hermes runtime configuration is actually wired."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from agent.prompt_builder import load_soul_md
from hermes_cli.config import load_config, read_raw_config
from hermes_cli.plugins_dispatch import (
    MAX_SYSTEM_PROMPT_SECTION_CHARS,
    MAX_SYSTEM_PROMPT_SECTIONS_TOTAL_CHARS,
    RenderedPluginSystemPromptSection,
    format_system_prompt_sections,
)
from hermes_constants import get_hermes_home
from tools.memory_tool_store import MemoryStore

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_PATH = REPO_ROOT / "plugins" / "gumar-runtime-policy" / "__init__.py"
PLUGIN_ID = "gumar-runtime-policy"


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


def _load_policy_plugin():
    spec = importlib.util.spec_from_file_location("gumar_runtime_policy_verify", PLUGIN_PATH)
    _require(spec is not None and spec.loader is not None, f"cannot load plugin module: {PLUGIN_PATH}")
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

    # 1) Native identity loader.
    soul = load_soul_md(home_override=home) or ""
    _require("Главный Hermes" in soul, "SOUL.md was not loaded by Hermes native identity loader")
    _require("Русский язык по умолчанию" in soul, "SOUL.md identity rules are missing")

    # 2) Native USER.md memory surface.
    store = _runtime_memory_store()
    store.load_from_disk()
    user = store.format_for_system_prompt("user") or ""
    _require("EndeavourOS" in user, "USER.md was not loaded by Hermes MemoryStore")
    _require("AI, агенты, обвязки и автоматизация" in user, "USER.md goals are missing from prompt snapshot")

    # 3) Plugin is enabled through config.
    raw = read_raw_config() or {}
    plugins = raw.get("plugins") if isinstance(raw, dict) else {}
    enabled = plugins.get("enabled", []) if isinstance(plugins, dict) else []
    _require(PLUGIN_ID in enabled, f"{PLUGIN_ID} is not enabled in config.yaml")

    # 4) Policy plugin really registers and renders prompt sections.
    module = _load_policy_plugin()
    probe = _PromptProbe()
    module.register(probe)
    expected_ids = {
        "gumar.runtime.01-governance",
        "gumar.runtime.02-architecture",
    }
    _require(set(probe.sections) == expected_ids, "runtime policy plugin did not register both prompt sections")

    rendered: list[RenderedPluginSystemPromptSection] = []
    texts: dict[str, str] = {}
    for section_id in sorted(probe.sections):
        spec = probe.sections[section_id]
        provider = spec["content"]
        text = provider({}) if callable(provider) else str(provider)
        _require(bool(text.strip()), f"{section_id} rendered empty")
        _require(len(text) <= spec["max_chars"], f"{section_id} exceeds declared max_chars")
        _require(len(text) <= MAX_SYSTEM_PROMPT_SECTION_CHARS, f"{section_id} exceeds Hermes section limit")
        texts[section_id] = text
        rendered.append(
            RenderedPluginSystemPromptSection(
                id=section_id,
                content=text,
                position=spec["position"],
                plugin=PLUGIN_ID,
            )
        )

    full_plugin_prompt = format_system_prompt_sections(rendered)
    _require(
        len(full_plugin_prompt) <= MAX_SYSTEM_PROMPT_SECTIONS_TOTAL_CHARS,
        "combined runtime policy sections exceed Hermes aggregate prompt budget",
    )

    governance = texts["gumar.runtime.01-governance"]
    architecture = texts["gumar.runtime.02-architecture"]

    _require("git push" in governance and "подтверждение обязательно" in governance,
             "PERMISSIONS policy is not present in runtime prompt")
    _require("Не использовать generative LLM" in governance,
             "EXECUTION_POLICY is not present in runtime prompt")
    _require("решает исходную задачу" in governance,
             "QUALITY_POLICY is not present in runtime prompt")
    _require("JEV выбирает только зарегистрированный" in architecture,
             "ARCHITECTURE/ACTION_REGISTRY rules are not present in runtime prompt")
    _require("SUBAGENT" in architecture and "orchestrator" in architecture,
             "ARCHITECTURE orchestration rules are not present in runtime prompt")

    print("Gumar runtime verification: OK")
    print(f"  HERMES_HOME: {home}")
    print("  SOUL.md: native identity loader OK")
    print("  USER.md: native MemoryStore prompt snapshot OK")
    print(f"  plugin: {PLUGIN_ID} enabled")
    print(f"  governance prompt chars: {len(governance)}")
    print(f"  architecture prompt chars: {len(architecture)}")
    print(f"  combined framed prompt chars: {len(full_plugin_prompt)}")
    print("  permissions/execution/quality/architecture markers: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
