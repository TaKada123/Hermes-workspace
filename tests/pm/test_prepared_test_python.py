"""The PM worker fixture is prepared locally from the locked test runtime."""
from importlib.metadata import version
import json
from pathlib import Path
import subprocess

import pytest


def test_prepared_worker_python_uses_locked_pm_deps_without_stage_runtime(tmp_path, monkeypatch):
    from tests.pm import _fixtures

    def no_uv_stage(*args, **kwargs):
        pytest.fail("worker preparation must not resolve or download PM runtime wheels")

    # The runner selects the locked test install; staging must preserve its versions.
    expected_versions = {
        name: version(name)
        for name in ("packaging", "tomli-w", "truststore", "ruamel.yaml")
    }
    monkeypatch.setattr("pm.runtime_stage.stage_runtime", no_uv_stage)
    python = _fixtures.prepare_test_python(tmp_path / "python")
    probe = subprocess.run(
        [str(python), "-I", "-B", "-c",
         "import importlib.metadata as m, importlib.util as u, json; "
         "names=('packaging','tomli-w','truststore','ruamel.yaml'); "
         "print(json.dumps({n:m.version(n) for n in names})); "
         "assert u.find_spec('openai') is None; assert u.find_spec('yaml') is None"],
        capture_output=True, text=True, timeout=30,
    )
    assert probe.returncode == 0, probe.stderr
    assert json.loads(probe.stdout) == expected_versions
    assert Path(python).is_file()