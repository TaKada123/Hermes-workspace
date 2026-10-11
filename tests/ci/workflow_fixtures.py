"""Paths to upstream workflow YAML copied as inert CI test data."""
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parent / "fixtures" / "upstream-workflows"


def workflow_path(name: str) -> Path:
    return WORKFLOWS / name
