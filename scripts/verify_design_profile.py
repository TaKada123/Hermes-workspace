#!/usr/bin/env python3
"""Verify the isolated Design Agent profile and minimal Main router."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "runtime-config"
CONTRACT_PATH = SOURCE / "profiles" / "design" / "profile-contract.json"
PROFILE = "design"
REQUIRED_ACTIONS = {
    "design.route",
    "ecommerce_card.create",
    "engineering_portfolio.create",
    "engineering_portfolio.extend",
    "engineering_portfolio.edit",
}
LICENSE_COPYRIGHT = "Copyright (c) 2026 xianyu110"
LICENSE_PERMISSION_NOTICE = (
    "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
    "of this software and associated documentation files (the \"Software\"), to deal\n"
    "in the Software without restriction, including without limitation the rights\n"
    "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n"
    "copies of the Software, and to permit persons to whom the Software is\n"
    "furnished to do so, subject to the following conditions:\n\n"
    "The above copyright notice and this permission notice shall be included in all\n"
    "copies or substantial portions of the Software."
)


def _root() -> Path:
    raw = os.environ.get("HERMES_HOME")
    if not raw:
        return Path.home() / ".hermes"
    home = Path(raw).expanduser().resolve()
    return home.parent.parent if home.parent.name == "profiles" else home


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    _require(isinstance(data, dict), f"{path} is not a JSON object")
    return data


def _yaml(path: Path) -> dict[str, Any]:
    from ruamel.yaml import YAML

    data = YAML(typ="safe").load(path.read_text(encoding="utf-8-sig"))
    return data if isinstance(data, dict) else {}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _same_file(source: Path, target: Path) -> None:
    _require(target.is_file(), f"missing {target}")
    _require(_sha(source) == _sha(target), f"installed file drifted: {target}")


def _tree_files(root: Path) -> set[Path]:
    return {
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }


def _same_tree(source: Path, target: Path) -> None:
    _require(source.is_dir(), f"missing source tree {source}")
    _require(target.is_dir(), f"missing installed tree {target}")
    source_files = _tree_files(source)
    target_files = _tree_files(target)
    missing = sorted(str(path) for path in source_files - target_files)
    extra = sorted(str(path) for path in target_files - source_files)
    _require(not missing, f"installed tree {target} missing files: {missing}")
    _require(not extra, f"installed tree {target} has extra files: {extra}")
    for rel in sorted(source_files):
        _same_file(source / rel, target / rel)


def _run(*args: str) -> str:
    hermes = shutil.which("hermes")
    if hermes is None:
        raise RuntimeError("hermes executable not found")
    completed = subprocess.run(
        [hermes, *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=180,
    )
    _require(completed.returncode == 0, f"hermes {' '.join(args)} failed: {(completed.stderr or completed.stdout).strip()}")
    return completed.stdout


def _prompt_size(profile: str | None = None) -> dict[str, Any]:
    prefix = ("-p", profile) if profile else ()
    return json.loads(_run(*prefix, "prompt-size", "--json"))


def main() -> int:
    root = _root()
    profile_home = root / "profiles" / PROFILE
    contract = _json(CONTRACT_PATH)
    _require(profile_home.is_dir(), f"missing profile home {profile_home}")
    _require((profile_home / ".no-bundled-skills").exists(), "design profile is not opted out of bundled-skill seeding")

    for rel in ("SOUL.md", "memories/USER.md", "memories/MEMORY.md"):
        _same_file(SOURCE / "profiles" / PROFILE / rel, profile_home / rel)
    for namespace in contract["memory_namespaces"]:
        name = namespace.split("/", 1)[1] + ".md"
        _same_file(
            SOURCE / "profiles" / PROFILE / "memories" / "design" / name,
            profile_home / "memories" / "design" / name,
        )
    for skill in contract["profile_local_skills"]:
        _same_tree(
            SOURCE / "profiles" / PROFILE / "skills" / skill,
            profile_home / "skills" / skill,
        )
    for third_party in contract["third_party_sources"]:
        license_source = REPO_ROOT / third_party["license_path"]
        license_target = profile_home / "skills" / license_source.name
        _same_file(license_source, license_target)
        license_text = license_source.read_text(encoding="utf-8")
        _require(LICENSE_COPYRIGHT in license_text, "vendored ecommerce license copyright notice mismatch")
        _require(LICENSE_PERMISSION_NOTICE in license_text, "vendored ecommerce license permission notice mismatch")
    _same_tree(SOURCE / "profiles" / PROFILE / "agents", profile_home / "agents")
    for agent in contract["subordinate_agents"]:
        _same_file(
            SOURCE / "profiles" / PROFILE / agent["instruction"],
            profile_home / agent["instruction"],
        )
    _same_file(
        SOURCE / "skills" / "routing" / "design-router" / "SKILL.md",
        root / "skills" / "routing" / "design-router" / "SKILL.md",
    )

    cfg = _yaml(profile_home / "config.yaml")
    main_cfg = _yaml(root / "config.yaml")
    _require((cfg.get("model") or {}).get("provider") == contract["model"]["provider"], "design model provider mismatch")
    _require((cfg.get("model") or {}).get("default") == contract["model"]["default"], "design model mismatch")
    _require(set((cfg.get("platform_toolsets") or {}).get("cli", [])) == set(contract["toolsets"]), "design toolsets mismatch")
    _require("delegation" in contract["toolsets"], "design profile cannot command its ecommerce subagent")
    _require((cfg.get("delegation") or {}).get("max_spawn_depth") == 1, "design delegation depth mismatch")
    _require((cfg.get("mcp_servers") or {}) == {}, "design profile unexpectedly has MCP servers")
    _require(set((cfg.get("plugins") or {}).get("enabled", [])) == {contract["policies"]["plugin"]}, "design policy plugin mismatch")
    _require(
        ((cfg.get("tools") or {}).get("tool_search") or {}).get("defer")
        == ((main_cfg.get("tools") or {}).get("tool_search") or {}).get("defer"),
        "tools.tool_search.defer differs between Main and Design",
    )
    main_disabled = set((main_cfg.get("skills") or {}).get("disabled", []))
    _require(set(contract["main_disabled_skills"]).issubset(main_disabled), "Main still exposes design skills")

    registry = _json(SOURCE / "action_registry.json")
    ids = {row.get("id") for row in registry.get("actions", []) if isinstance(row, dict)}
    _require(REQUIRED_ACTIONS.issubset(ids), f"action registry missing {sorted(REQUIRED_ACTIONS - ids)}")
    route = next(row for row in registry["actions"] if row.get("id") == "design.route")
    _require(route.get("route") == {"route_type": "profile", "route_id": PROFILE}, "design.route contract mismatch")
    ecommerce = next(row for row in registry["actions"] if row.get("id") == "ecommerce_card.create")
    expected_agent = {
        "id": "ecommerce-card-designer",
        "instruction": "agents/ecommerce-card-designer.md",
        "action_id": "ecommerce_card.create",
        "parent": PROFILE,
        "lifecycle": "temporary-subagent",
        "may_delegate": False,
    }
    _require(contract["subordinate_agents"] == [expected_agent], "ecommerce subordinate contract mismatch")
    _require(ecommerce.get("profile") == PROFILE, "ecommerce action profile mismatch")
    _require(ecommerce.get("parent_agent") == expected_agent["parent"], "ecommerce action parent mismatch")
    _require(ecommerce.get("subagent_instruction") == expected_agent["instruction"], "ecommerce action instruction mismatch")
    _require(ecommerce.get("domain_skill") == "ecommerce-listing-suite", "ecommerce action domain skill mismatch")
    _require(ecommerce.get("lifecycle") == expected_agent["lifecycle"], "ecommerce action lifecycle mismatch")
    _require(ecommerce.get("may_delegate") is False, "ecommerce action must be a leaf")
    _require(
        ecommerce.get("approval_gate") == {
            "required_for": ["paid_generation", "external_upload"],
            "approver": "user",
            "budget_required": True,
            "missing_status": "NEEDS_APPROVAL",
        },
        "ecommerce explicit-user-approval gate mismatch",
    )

    instruction = (SOURCE / "profiles" / PROFILE / expected_agent["instruction"]).read_text(encoding="utf-8-sig")
    soul = (SOURCE / "profiles" / PROFILE / "SOUL.md").read_text(encoding="utf-8-sig")
    for marker in ("USER явно разрешил", "указал максимальный бюджет", "NEEDS_APPROVAL", "только встроенный Hermes `image_generate`"):
        _require(marker in instruction, f"ecommerce instruction lacks approval marker: {marker}")
    for marker in ("action `ecommerce_card.create`", "agents/ecommerce-card-designer.md", "delegate_task", "не имеет права делегировать дальше"):
        _require(marker in soul, f"Design SOUL lacks ecommerce delegation marker: {marker}")
    _require("не делегируйте работу дальше" in instruction.lower(), "ecommerce instruction lacks leaf/no-redelegation wording")

    forbidden_network_markers = ("GPTIMAGE_API_KEY", "GPTIMAGE_BASE_URL", "gptimage2.asia", "chatgpt-plus.top", "tryallapi.com")
    forbidden_install_markers = ("pip install", "pip3 install", "uv pip install", "uv add", "uv sync")
    ecommerce_skills = [skill for skill in contract["profile_local_skills"] if skill != "engineering-portfolio"]
    for skill in ecommerce_skills:
        source_skill = SOURCE / "profiles" / PROFILE / "skills" / skill
        _require(not (source_skill / "scripts" / "generate.py").exists(), f"{skill} retains generate.py")
        _require(not (source_skill / "scripts" / "online_link.py").exists(), f"{skill} retains online_link.py")
        skill_text = (source_skill / "SKILL.md").read_text(encoding="utf-8-sig")
        _require("built-in Hermes route only" in skill_text, f"{skill} lacks built-in image_generate route")
        _require("NEEDS_APPROVAL" in skill_text, f"{skill} lacks approval failure status")
        _require(not any(marker in skill_text for marker in forbidden_network_markers), f"{skill} retains external generation fallback")
        for path in _tree_files(source_skill):
            text = (source_skill / path).read_text(encoding="utf-8-sig")
            lowered = text.lower()
            _require(
                not any(marker in lowered for marker in forbidden_install_markers),
                f"{skill}/{path} contains a raw package-install instruction",
            )
            _require("numpy" not in lowered, f"{skill}/{path} contains a NumPy import or dependency reference")

    main_prompt = _prompt_size()
    design_prompt = _prompt_size(PROFILE)
    main_skills = {row["name"] for row in main_prompt["skills_breakdown"]}
    design_skills = {row["name"] for row in design_prompt["skills_breakdown"]}
    _require("design-router" in main_skills, "Main prompt lacks the compact router skill index entry")
    _require("superdesign" not in main_skills and "impeccable" not in main_skills, "Main prompt still indexes large design skills")
    required_design_skills = {"engineering-portfolio", "superdesign", "impeccable", *contract["profile_local_skills"]}
    _require(required_design_skills.issubset(design_skills), "Design prompt lacks required on-demand skills")
    _require(design_prompt["skills_index"]["bytes"] < 4_000, "Design skill index is unexpectedly large")

    forbidden = ("Sizing Hermes prompt cost", "Учится в университете", "finance")
    design_memory = (profile_home / "memories" / "MEMORY.md").read_text(encoding="utf-8-sig")
    design_user = (profile_home / "memories" / "USER.md").read_text(encoding="utf-8-sig")
    _require(not any(marker in design_memory + design_user for marker in forbidden), "unrelated Main memory leaked into Design")

    with tempfile.TemporaryDirectory() as tmp:
        handoff = Path(tmp) / "handoff.json"
        original = "Создай структуру нового портфолио."
        handoff.write_text(json.dumps({
            "schema_version": 1,
            "route_type": "profile",
            "route_id": PROFILE,
            "action_id": "design.route",
            "source_profile": "default",
            "original_user_request": original,
            "attachments": [],
            "project_context": [],
        }, ensure_ascii=False), encoding="utf-8")
        script = root / "skills" / "routing" / "design-router" / "scripts" / "route_design_profile.py"
        completed = subprocess.run(
            [sys.executable, str(script), "--handoff-file", str(handoff), "--dry-run"],
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=30,
        )
        _require(completed.returncode == 0, f"router dry-run failed: {completed.stderr or completed.stdout}")
        report = json.loads(completed.stdout)
        _require(report.get("profile") == PROFILE and report.get("action_id") == "design.route", "router dry-run target mismatch")
        _require(report.get("request_sha256") == hashlib.sha256(original.encode("utf-8")).hexdigest(), "router changed original request")

    print("Design profile verification: OK")
    print(f"  profile home: {profile_home}")
    print(f"  model/provider: {contract['model']['default']} / {contract['model']['provider']}")
    print(f"  toolsets: {sorted(contract['toolsets'])}")
    print(f"  MCP servers: none")
    print(f"  Main prompt: {main_prompt['system_prompt']['bytes']} bytes, skills index {main_prompt['skills_index']['bytes']} bytes")
    print(f"  Design prompt: {design_prompt['system_prompt']['bytes']} bytes, skills index {design_prompt['skills_index']['bytes']} bytes")
    print("  Main: router indexed; Superdesign/Impeccable absent")
    print("  Design: ecommerce-card subagent and 12 ecommerce skills indexed on demand")
    print("  profile-local skill and subordinate-agent trees: exact match")
    print("  ecommerce runtime dependencies and vendored MIT license: OK")
    print("  ecommerce action binding, USER approval/budget gate and leaf contract: OK")
    print("  memory isolation and verbatim handoff: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
