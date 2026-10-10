#!/usr/bin/env python3
"""Fail before pytest collection when the declared test SDKs are unavailable."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable

REQUIRED_MODULES = ("acp", "fal_client", "parallel")


def missing_test_modules(import_module: Callable[[str], object] = importlib.import_module) -> list[str]:
    """Return required import names unavailable in the active interpreter."""
    missing = []
    for name in REQUIRED_MODULES:
        try:
            import_module(name)
        except ImportError:
            missing.append(name)
    return missing


def main(import_module: Callable[[str], object] = importlib.import_module) -> int:
    missing = missing_test_modules(import_module)
    if not missing:
        return 0

    print(
        "Missing test dependencies in this interpreter: " + ", ".join(missing) + ".\n"
        "Build the canonical test environment with:\n"
        "  python -m pm.build_env --source . --out .venv --group dev --group test\n"
        "or activate/sync the checkout's PM test environment before running tests.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
