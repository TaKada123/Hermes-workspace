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
    "engineering_portfolio.create",
    "engineering_portfolio.extend",
    "engineering_portfolio.edit",
}


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
    _same_file(
        SOURCE / "profiles" / PROFILE / "skills" / "engineering-portfolio" / "SKILL.md",
        profile_home / "skills" / "engineering-portfolio" / "SKILL.md",
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

    main_prompt = _prompt_size()
    design_prompt = _prompt_size(PROFILE)
    main_skills = {row["name"] for row in main_prompt["skills_breakdown"]}
    design_skills = {row["name"] for row in design_prompt["skills_breakdown"]}
    _require("design-router" in main_skills, "Main prompt lacks the compact router skill index entry")
    _require("superdesign" not in main_skills and "impeccable" not in main_skills, "Main prompt still indexes large design skills")
    _require({"engineering-portfolio", "superdesign", "impeccable"}.issubset(design_skills), "Design prompt lacks required on-demand skills")
    _require(design_prompt["skills_index"]["bytes"] < 3_000, "Design skill index is unexpectedly large")

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
    print("  Design: engineering-portfolio/Superdesign/Impeccable indexed on demand")
    print("  memory isolation and verbatim handoff: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
