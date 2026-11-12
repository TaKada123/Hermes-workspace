"""Architect pilot: public installer and executable launcher, synthetic state only."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[3]
INSTALLER = ROOT / "scripts/direct_agent.py"
DEFINITIONS = ROOT / "runtime-config/agents/architect"


@pytest.fixture
def installation(tmp_path):
    source = tmp_path / "old profile"
    source.mkdir()
    (source / "memories").mkdir()
    (source / "memories/USER.md").write_text("Synthetic user\n")
    (source / "memories/MEMORY.md").write_text("Synthetic memory\n")
    (source / "skills/example/references").mkdir(parents=True)
    (source / "skills/example/SKILL.md").write_text("Synthetic skill")
    (source / "skills/example/references/help.md").write_text("Reference")
    (source / "plugins/zaebal-hermes").mkdir(parents=True)
    (source / "plugins/zaebal-hermes/plugin.yaml").write_text("name: zaebal-hermes\n")
    config = {
        "model": {"default": "gpt-6-sol-900k", "provider": "openai-codex"},
        "memory": {"provider": "file", "memory_char_limit": 12345},
        "tools": {"tool_search": {"defer": ["skill_manage"]}},
        "mcp_servers": {"code_graph": {"command": "/external/graph"},
                        "context7": {"command": "/external/context7"}},
        "plugins": {"enabled": ["agent-network", "gumar-runtime-policy", "zaebal-hermes"],
                    "disabled": ["already-disabled"]},
    }
    (source / "config.yaml").write_text(json.dumps(config))
    db = sqlite3.connect(source / "state.db")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE VIRTUAL TABLE messages_fts USING fts5(content)")
    db.execute("INSERT INTO messages_fts VALUES ('synthetic history')")
    db.commit()  # Connection stays open: the backup must include uncheckpointed WAL.
    hermes = tmp_path / "hermes real cli"
    real_hermes = shutil.which("hermes")
    assert real_hermes, "A provisioned Hermes CLI is required; do not install dependencies in tests"
    hermes.write_text(
        f"#!{sys.executable}\nimport os,sys,json\n"
        f"if sys.argv[1:2] == ['config']: os.execv(sys.executable, [sys.executable, '-m', 'hermes_cli.main', *sys.argv[1:]])\n"
        "print(json.dumps({'home': os.environ['HERMES_HOME'], 'cwd': os.getcwd(), 'argv': sys.argv[1:], 'profile': os.environ.get('HERMES_PROFILE')}))\n"
    )
    hermes.chmod(0o700)
    target = tmp_path / "new architect"
    command = [sys.executable, str(INSTALLER), "install", "--source", str(source),
               "--target", str(target), "--definitions", str(DEFINITIONS), "--hermes", str(hermes)]
    yield source, target, hermes, command, config
    db.close()


def run(command, **kwargs):
    return subprocess.run(command, capture_output=True, text=True, timeout=90, **kwargs)


def test_install_preserves_private_state_and_capabilities(installation):
    source, target, _, command, original = installation
    before = (source / "config.yaml").read_bytes()
    result = run(command)
    assert result.returncode == 0, result.stderr
    assert "Synthetic" not in result.stdout + result.stderr
    assert target.stat().st_mode & 0o077 == 0
    for name in ["USER.md", "MEMORY.md"]:
        assert (target / "memories" / name).read_bytes() == (source / "memories" / name).read_bytes()
        assert (target / ".direct-agent/source-snapshot/memories" / name).is_file()
    with sqlite3.connect(target / "state.db") as db:
        assert db.execute("SELECT content FROM messages_fts WHERE messages_fts MATCH 'history'").fetchall() == [("synthetic history",)]
    copied = {}
    for key in ["model", "memory", "tools", "mcp_servers", "plugins"]:
        query = run([str(installation[2]), "config", "get", key, "--json"],
                    env=dict(os.environ, HERMES_HOME=str(target)))
        assert query.returncode == 0, query.stderr
        copied[key] = json.loads(query.stdout)
    for key in ["model", "memory", "mcp_servers"]:
        for field, value in original[key].items():
            assert copied[key][field] == value
    assert copied["tools"]["tool_search"]["defer"] == original["tools"]["tool_search"]["defer"]
    assert set(copied["plugins"]["disabled"]) == {"already-disabled", "agent-network", "gumar-runtime-policy"}
    assert copied["plugins"]["enabled"] == ["zaebal-hermes"]
    assert (target / "plugins/zaebal-hermes/plugin.yaml").is_file()
    assert (target / "skills/example/references/help.md").read_text() == "Reference"
    assert (source / "config.yaml").read_bytes() == before
    assert not (target / "auth.json").exists()
    assert not (target / ".env").exists()
    assert "Architect" in (target / "SOUL.md").read_text()
    assert run(command).returncode != 0  # A second install must never reset state.


@pytest.mark.platforms("posix")
def test_launcher_pins_home_preserves_cwd_and_argument_boundaries(installation, tmp_path):
    _, target, _, command, _ = installation
    alias = tmp_path / "bin/architect-direct"
    result = run([*command, "--launcher", str(alias)])
    assert result.returncode == 0, result.stderr
    project = tmp_path / "caller project"
    project.mkdir()
    args = ["chat", "-q", "literal $(touch SHOULD_NOT_EXIST); quote' and space"]
    env = dict(os.environ, HERMES_HOME="/wrong/home", HERMES_PROFILE="wrong-profile")
    for executable in (target / "architect-direct", alias):
        result = run([str(executable), *args], cwd=project, env=env)
        assert result.returncode == 0, result.stderr
        observed = json.loads(result.stdout)
        assert observed == {"home": str(target), "cwd": str(project), "argv": args, "profile": None}
        assert not (project / "SHOULD_NOT_EXIST").exists()
        for flags in (["-p", "other"], ["--profile=other"], ["-pother"], ["--profile", "other"]):
            refused = run([str(executable), *flags], cwd=project, env=env)
            assert refused.returncode != 0
            assert not refused.stdout


@pytest.mark.platforms("posix")
def test_capabilities_preserve_explicit_safe_links_and_exclude_runtime_debris(installation, tmp_path):
    source, target, _, command, _ = installation
    shared = tmp_path / "shared/skills"
    shared.mkdir(parents=True)
    (shared / "tool").mkdir()
    (shared / "tool/SKILL.md").write_text("Shared capability")
    (source / "skills/shared").symlink_to(os.path.relpath(shared / "tool", source / "skills"))
    (source / "skills/missing").symlink_to(shared / "missing")
    (source / "skills/example/ref-link").symlink_to("references/help.md")
    for relative in ("skills/example/.env", "skills/example/auth.json", "skills/example/runtime.lock",
                     "skills/example/__pycache__/compiled.pyc", "skills/example/.git/config",
                     "cron/jobs.json", "agent-network/credentials.json", "cache/stale", ".env", "auth.json"):
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Synthetic excluded state")
    result = run([*command, "--allow-capability-root", str(shared)])
    assert result.returncode == 0, result.stderr
    assert (target / "skills/shared").is_symlink()
    assert (target / "skills/shared").readlink() == shared / "tool"
    assert (target / "skills/shared/SKILL.md").read_text() == "Shared capability"
    assert (target / "skills/missing").is_symlink()
    assert (target / "skills/missing").readlink() == shared / "missing"
    assert (target / "skills/example/ref-link").resolve() == target / "skills/example/references/help.md"
    assert not (target / "skills/example/.env").exists()
    assert not (target / "skills/example/auth.json").exists()
    assert not (target / "skills/example/runtime.lock").exists()
    assert not (target / "skills/example/__pycache__").exists()
    assert not (target / "skills/example/.git").exists()
    assert not (target / "cron/jobs.json").exists()  # CLI may initialize an empty cron directory.
    assert not (target / "agent-network").exists()
    assert not (target / "cache/stale").exists()


@pytest.mark.platforms("posix")
@pytest.mark.parametrize("hazard", ["private-link", "external-link", "nested-external-link",
                                    "source-target-link", "definitions-overlap", "alias-in-source",
                                    "config-link"])
def test_install_refuses_escapes_before_writing(installation, tmp_path, hazard):
    source, target, _, command, _ = installation
    if hazard == "private-link":
        (source / "memories/link").symlink_to(source / "config.yaml")
    elif hazard == "external-link":
        (source / "skills/private").symlink_to(source / "memories")
    elif hazard == "nested-external-link":
        shared = tmp_path / "shared/skills"
        shared.mkdir(parents=True)
        (shared / "escape").symlink_to(source / "memories")
        (source / "skills/shared").symlink_to(shared)
        command += ["--allow-capability-root", str(shared)]
    elif hazard == "source-target-link":
        target.symlink_to(source, target_is_directory=True)
    elif hazard == "definitions-overlap":
        index = command.index("--definitions") + 1
        command[index] = str(target)
    elif hazard == "alias-in-source":
        command += ["--launcher", str(source / "new-alias")]
    elif hazard == "config-link":
        (source / "config.yaml").rename(source / "real-config")
        (source / "config.yaml").symlink_to("real-config")
    before = {str(p.relative_to(source)): p.read_bytes() for p in source.rglob("*")
              if p.is_file() and not p.is_symlink() and not p.name.startswith("state.db")}
    result = run(command)
    assert result.returncode != 0
    assert not target.exists() or target.is_symlink()
    assert before == {str(p.relative_to(source)): p.read_bytes() for p in source.rglob("*")
                      if p.is_file() and not p.is_symlink() and not p.name.startswith("state.db")}
    assert not (source / "new-alias").exists()
