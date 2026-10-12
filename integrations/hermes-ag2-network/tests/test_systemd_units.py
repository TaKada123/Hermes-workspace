"""Validate installable unit syntax; lifecycle behavior lives in test_systemd_lifecycle."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

SYSTEMD = Path(__file__).parents[1] / "systemd"


def test_packaged_units_pass_systemd_validation(tmp_path: Path):
    analyzer = shutil.which("systemd-analyze")
    if analyzer is None:
        pytest.skip("systemd-analyze unavailable on this platform")
    units = []
    for name in ("hermes-ag2-hub.service", "hermes-ag2-bridge@.service"):
        target = tmp_path / name
        source = (SYSTEMD / name).read_text(encoding="utf-8")
        # Validation needs an existing executable; it never executes the service.
        source = source.replace("%h/.local/share/hermes-ag2-network/bin/hermes-ag2-network", sys.executable)
        target.write_text(source, encoding="utf-8")
        units.append(str(target))
    # Offline user-manager syntax verification needs a runtime directory, not a live bus.
    env = {**os.environ, "XDG_RUNTIME_DIR": str(tmp_path)}
    result = subprocess.run([analyzer, "--user", "verify", *units], text=True, env=env,
                            capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
