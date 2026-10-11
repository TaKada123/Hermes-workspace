"""The canonical shell must run tests and propagate a failing test's status."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.platforms("posix")
def test_shell_runner_executes_tests_and_propagates_failure(tmp_path):
    case = tmp_path / "test_runner_canary.py"
    marker = tmp_path / "executed"
    case.write_text(
        "from pathlib import Path\nimport os\n"
        "def test_canary():\n"
        f"    Path({str(marker)!r}).write_text('executed')\n"
        "    assert os.environ['PATHEXT'] == '.COM;.EXE;.BAT;.CMD'\n"
        "    assert False, 'runner failure propagation canary'\n",
        encoding="utf-8",
    )
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["bash", str(root / "scripts/run_tests.sh"), "-j", "1", str(case)],
        cwd=tmp_path, capture_output=True, text=True, timeout=180,
        env={**os.environ, "HERMES_PYTHON": sys.executable, "HERMES_TEST_FILE_RETRIES": "0",
             "PATHEXT": ".COM;.EXE;.BAT;.CMD"},
    )
    assert marker.read_text(encoding="utf-8") == "executed", result.stdout + result.stderr
    assert result.returncode != 0, result.stdout + result.stderr
    assert "runner failure propagation canary" in result.stdout + result.stderr


@pytest.mark.platforms("posix")
def test_shell_runner_propagates_selected_interpreter_and_filters_hermes_path(tmp_path):
    hermes_home = tmp_path / ".hermes-custom"
    managed_bin = hermes_home / "bin"
    home_managed_bin = tmp_path / ".hermes" / "bin"
    managed_bin.mkdir(parents=True)
    home_managed_bin.mkdir(parents=True)
    case = tmp_path / "test_runner_environment.py"
    marker = tmp_path / "environment"
    case.write_text(
        "import json, os, sys, sysconfig\nfrom pathlib import Path\n"
        "def test_environment():\n"
        f"    Path({str(marker)!r}).write_text(json.dumps({{\n"
        "        'hermes_python': os.environ.get('HERMES_PYTHON'),\n"
        "        'executable': sys.executable, 'prefix': sys.prefix,\n"
        "        'base_prefix': sys.base_prefix, 'stdlib': sysconfig.get_path('stdlib'),\n"
        "        'site_packages': [p for p in sys.path if p and Path(p).name in ('site-packages', 'dist-packages')],\n"
        "        'path': os.environ['PATH'],\n"
        "    }))\n",
        encoding="utf-8",
    )
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["bash", str(root / "scripts/run_tests.sh"), "-j", "1", str(case)],
        cwd=tmp_path, capture_output=True, text=True, timeout=180,
        env={**os.environ, "HOME": str(tmp_path), "HERMES_HOME": str(hermes_home),
             "HERMES_PYTHON": sys.executable, "HERMES_TEST_FILE_RETRIES": "0",
             "PATH": os.pathsep.join((str(managed_bin), str(home_managed_bin), str(root / ".hermes" / "bin"), os.environ["PATH"]))},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    environment = json.loads(marker.read_text())
    hermes_homes = (hermes_home, tmp_path / ".hermes", Path.home() / ".hermes")
    assert environment["hermes_python"] == sys.executable
    assert environment["executable"] == sys.executable
    assert all(str(home) not in environment["hermes_python"] for home in hermes_homes)
    assert all(str(home) not in environment["executable"] for home in hermes_homes)
    for key in ("prefix", "base_prefix", "stdlib"):
        assert all(str(home) not in environment[key] for home in hermes_homes)
    assert environment["site_packages"]
    assert all(str(home) not in path for home in hermes_homes for path in environment["site_packages"])
    assert all(str(home) not in environment["path"] for home in hermes_homes)
