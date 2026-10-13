"""Exercise the composite action's Python provisioning seam without networking."""
import os
from pathlib import Path
import subprocess

import pytest
from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("network", ["false", "true"])
def test_ci_provisions_declared_suite_extras_and_checks_imports(tmp_path, monkeypatch, network):
    from pm import operations

    action = YAML(typ="safe").load((ROOT / ".github/actions/ag2-ci-environment/action.yml").read_text())
    step = next(s for s in action["runs"]["steps"] if s["name"] == "Build fresh locked PM-owned environments")
    program = step["run"].split("\n", 2)[2].split("\nPY\n", 1)[0]
    builds, checks = [], []

    def build(**kwargs):
        builds.append(kwargs)
        return kwargs["out"] / "bin/python"

    def run(command, **kwargs):
        checks.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(operations, "build_environment", build)
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.chdir(ROOT)
    for key in ("HOME", "HERMES_HOME", "HERMES_RUNTIME_DIR", "HERMES_TEST_ENV",
                "NETWORK_TEST_ENV", "TMPDIR", "UV_CACHE_DIR", "RESULTS"):
        monkeypatch.setenv(key, str(tmp_path / key))
    monkeypatch.setenv("HERMES_BASE_PYTHON", str(tmp_path / "base/python"))
    monkeypatch.setenv("BUILD_NETWORK", network)
    exec(compile(program, "CI provisioning", "exec"), {})
    assert builds[0]["extras"] == ["acp", "fal", "parallel-web", "slack"]
    assert builds[0]["groups"] == ["dev", "test"]
    assert all(b["explicit"] for b in builds)
    assert len(builds) == (2 if network == "true" else 1)
    assert all(c[1]["check"] and c[1]["timeout"] > 0 for c in checks)
    assert "import acp, fal_client, parallel, slack_bolt" in checks[0][0][2]
    assert Path(checks[0][0][0]).is_relative_to(tmp_path)
    assert os.environ["HERMES_TEST_ENV"] == str(tmp_path / "HERMES_TEST_ENV")
