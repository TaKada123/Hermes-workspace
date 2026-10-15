"""Upstream workflow contract inputs, deliberately outside GitHub's active tree.

These tests exercise imported release scripts and their authentic upstream
callers, not this fork's deployment policy. Never fall back to active workflows:
a missing snapshot is an import failure and must fail the contract suite.
"""
from pathlib import Path

UPSTREAM_WORKFLOWS = Path(__file__).resolve().parents[1] / "fixtures/upstream-workflows/workflows"
