"""Design routing preserves launcher identity and the isolated profile contract."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "runtime-config/skills/routing/design-router/scripts/route_design_profile.py"
)


@pytest.fixture
def router(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("design_router_skill_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    handoff = tmp_path / "handoff.json"
    handoff.write_text(json.dumps({
        "schema_version": 1,
        "route_type": "profile",
        "route_id": "design",
        "action_id": "design.route",
        "original_user_request": "Сделай сайт; $(do-not-execute)",
    }), encoding="utf-8")
    monkeypatch.setattr(module.sys, "argv", [str(SCRIPT), "--handoff-file", str(handoff)])
    return module


@pytest.mark.parametrize("returncode", [0, 17])
def test_routes_with_exact_path_launcher_and_design_profile(router, tmp_path, monkeypatch, returncode):
    launcher_dir = tmp_path / "runtime with spaces"
    launcher_dir.mkdir()
    launcher = launcher_dir / ("hermes.exe" if os.name == "nt" else "hermes")
    launcher.touch()
    launcher.chmod(0o755)
    monkeypatch.setenv("PATH", str(launcher_dir))
    run = Mock(return_value=subprocess.CompletedProcess([], returncode))
    monkeypatch.setattr(router.subprocess, "run", run)

    assert router.main() == returncode

    run.assert_called_once()
    command = run.call_args.args[0]
    assert command[:5] == [str(launcher), "-p", "design", "chat", "-q"]
    assert "\nСделай сайт; $(do-not-execute)\n" in command[5]
    assert command[6:] == ["--source", "profile-router", "--max-turns", "150"]
    assert run.call_args.kwargs == {
        "text": True, "encoding": "utf-8", "errors": "replace", "timeout": 1800,
    }


@pytest.mark.parametrize("dry_run", [False, True])
def test_missing_launcher_never_spawns_and_dry_run_needs_no_launcher(
    router, monkeypatch, capsys, dry_run,
):
    monkeypatch.setenv("PATH", "")
    if dry_run:
        monkeypatch.setattr(router.sys, "argv", [*router.sys.argv, "--dry-run"])
    run = Mock()
    monkeypatch.setattr(router.subprocess, "run", run)

    assert router.main() == (0 if dry_run else 3)

    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is dry_run
    if dry_run:
        assert result["profile"] == "design"
        assert result["action_id"] == "design.route"
    else:
        assert result["error"] == "hermes executable not found"
    run.assert_not_called()
