"""Packaging declares the SDKs required by the canonical test environment."""

from pathlib import Path
import tomllib

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_aiohttp_is_declared_in_test_dependency_group():
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    declared_packages = {
        canonicalize_name(Requirement(dependency).name)
        for dependency in pyproject["dependency-groups"]["test"]
    }
    assert "aiohttp" in declared_packages
