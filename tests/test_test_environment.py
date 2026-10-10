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


def test_missing_aiohttp_test_sdk_fails_before_collection(capsys):
    checker = runpy.run_path(str(CHECKER))

    def import_without_aiohttp(module):
        if module == "aiohttp":
            raise ModuleNotFoundError(module)
        return object()

    assert checker["main"](import_without_aiohttp) == 1
    error = capsys.readouterr().err
    assert "Missing test dependencies in this interpreter: aiohttp" in error
    assert "--group dev --group test" in error


def test_aiohttp_is_declared_in_test_dependency_group():
    import tomllib

    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    assert "aiohttp==3.14.3" in pyproject["dependency-groups"]["test"]
