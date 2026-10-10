"""Upstream workflow definitions are test data, never active Actions workflows."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/ci/fixtures/upstream-workflows"
ACTIVE_WORKFLOWS = ROOT / ".github/workflows"
REQUIRED_WORKFLOWS = {
    "archive-inputs.yml",
    "canary-release.yml",
    "ci-review-comment.yml",
    "ci.yaml",
    "plugin-catalog-ci.yml",
    "desktop-bundle-smoke.yml",
    "desktop-bundled-release.yml",
    "docker.yml",
    "nix.yml",
    "stable-release-publication.yml",
    "stable-release.yml",
    "termux-verify.yml",
}


def test_upstream_workflow_fixtures_are_available_outside_active_actions():
    assert REQUIRED_WORKFLOWS <= {path.name for path in FIXTURES.glob("*.y*ml")}
    assert FIXTURES.is_relative_to(ROOT / "tests")
    assert not (ACTIVE_WORKFLOWS / "desktop-bundled-release.yml").exists()
