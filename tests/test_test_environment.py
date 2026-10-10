"""The canonical test runner rejects incomplete test environments before collection."""

import runpy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKER = REPO_ROOT / "scripts" / "check_test_environment.py"


def test_missing_test_sdk_fails_with_rebuild_remediation(capsys):
    checker = runpy.run_path(str(CHECKER))

    def import_with_missing_acp(module):
        if module == "acp":
            raise ModuleNotFoundError(module)
        return object()

    assert checker["main"](import_with_missing_acp) == 1
    error = capsys.readouterr().err
    assert "Missing test dependencies in this interpreter: acp" in error
    assert "--group dev --group test" in error
