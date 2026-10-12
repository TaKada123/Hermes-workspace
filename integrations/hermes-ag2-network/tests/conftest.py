"""Explicit owning-runtime interpreter for real core memory fixtures."""
import sys


def pytest_addoption(parser):
    parser.addoption("--hermes-core-python", default=sys.executable,
                     help="Hermes core test interpreter for the production memory/config fixture")
