"""Explicit owning-runtime interpreter for real core memory fixtures."""
import sys


def pytest_addoption(parser):
    parser.addoption("--ag2-systemd-acceptance", action="store_true", default=False,
                     help="opt in to isolated temporary real systemd user-service acceptance")
    parser.addoption("--ag2-systemd-runtime-dir", default=None,
                     help="explicit owning user runtime dir when canonical runner sanitizes D-Bus env")
    parser.addoption("--ag2-systemd-receipt", default=None,
                     help="approved output path for the sanitized systemd acceptance receipt")
    parser.addoption("--hermes-core-python", default=sys.executable,
                     help="Hermes core test interpreter for the production memory/config fixture")
