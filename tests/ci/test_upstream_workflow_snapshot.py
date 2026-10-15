"""Import boundary: preserve committed callers without activating their triggers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.ci.snapshot_upstream_workflows import is_safe_workflow_basename
from tests.ci.workflow_sources import UPSTREAM_WORKFLOWS

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "scripts/ci/snapshot_upstream_workflows.py"


def test_snapshot_keeps_committed_bytes_and_revision_without_activating_workflows(tmp_path):
    source = tmp_path / "upstream"
    source.mkdir()

    def git(*args):
        return subprocess.check_output(["git", "-C", str(source), *args]).decode().strip()

    git("init", "-q")
    workflows = source / ".github/workflows"
    workflows.mkdir(parents=True)
    original = b"name: Publish\non: push\njobs: {}\n"
    (workflows / "publish.yaml").write_bytes(original)
    git("add", ".")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture")
    revision = git("rev-parse", "HEAD")
    (workflows / "publish.yaml").write_text("uncommitted replacement\n")
    (workflows / "untracked.yml").write_text("on: push\n")
    destination = tmp_path / "fork/tests/fixtures/upstream-workflows"
    subprocess.run([sys.executable, str(SNAPSHOT), str(source), str(destination)], check=True)
    assert (destination / "workflows/publish.yaml").read_bytes() == original
    manifest = json.loads((destination / "manifest.json").read_text())
    assert manifest["revision"] == revision
    assert set(manifest["files"]) == {"publish.yaml"}
    assert manifest["files"]["publish.yaml"]["git_blob"] == git("rev-parse", "HEAD:.github/workflows/publish.yaml")
    assert not (tmp_path / "fork/.github").exists()

    # A refresh cannot mix revisions or overwrite a previous snapshot silently.
    repeated = subprocess.run([sys.executable, str(SNAPSHOT), str(source), str(destination)], capture_output=True)
    assert repeated.returncode != 0
    assert (destination / "workflows/publish.yaml").read_bytes() == original


@pytest.mark.parametrize("name", [
    r"..\..\escaped.yml",
    r"nested\escaped.yml",
    r"C:escaped.yml",
    r"C:\escaped.yml",
    r"\escaped.yml",
    r"\\server\share\escaped.yml",
])
def test_snapshot_rejects_unsafe_git_names_before_any_destination_writes(tmp_path, name):
    source = tmp_path / "upstream"
    source.mkdir()

    def git(*args, content=None):
        return subprocess.check_output(
            ["git", "-C", str(source), *args], input=content,
        ).strip()

    git("init", "-q")
    blob = git("hash-object", "-w", "--stdin", content=b"on: push\njobs: {}\n")

    def tree(entries):
        return git("mktree", "-z", content=entries).decode()

    # Build actual Git objects rather than relying on the host filesystem to
    # permit Windows-unsafe filenames. The valid entry sorts before the attack.
    workflows = tree(
        b"100644 blob " + blob + b"\t000-safe.yml\0"
        + b"100644 blob " + blob + b"\t" + name.encode() + b"\0"
    )
    github = tree(f"040000 tree {workflows}\tworkflows\0".encode())
    root = tree(f"040000 tree {github}\t.github\0".encode())
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "--allow-empty", "-qm", "fixture")
    git("read-tree", root)
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-qm", "unsafe workflow tree")
    destination = tmp_path / "not-created/snapshot"
    result = subprocess.run(
        [sys.executable, str(SNAPSHOT), str(source), str(destination)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0, result.stdout
    assert "unexpected workflow entry" in result.stderr
    assert not destination.parent.exists()
    assert not (tmp_path / "escaped.yml").exists()


@pytest.mark.parametrize("name", [
    "", ".", "..", "/escaped.yml", "../escaped.yml", "nested/escaped.yaml",
    "//server/share/escaped.yml", "C:/escaped.yml", "C:escaped.yaml",
    r"C:\escaped.yml", r"\escaped.yml", r"..\..\escaped.yml",
    r"\\server\share\escaped.yml", "not-a-workflow.txt",
])
def test_workflow_basename_validation_rejects_both_path_grammars(name):
    assert not is_safe_workflow_basename(name)


@pytest.mark.parametrize("name", ["ci.yml", "release-build.yaml", "CI checks.yml"])
def test_workflow_basename_validation_accepts_single_workflow_names(name):
    assert is_safe_workflow_basename(name)


def test_archived_workflows_match_the_import_manifest():
    manifest = json.loads((UPSTREAM_WORKFLOWS.parent / "manifest.json").read_text())
    assert manifest["repository"] == "https://github.com/NousResearch/hermes-agent"
    assert manifest["source_directory"] == ".github/workflows"
    assert len(manifest["revision"]) == 40
    actual = {path.name for path in UPSTREAM_WORKFLOWS.iterdir()}
    assert actual == set(manifest["files"])
    assert actual
    for name, expected in manifest["files"].items():
        content = (UPSTREAM_WORKFLOWS / name).read_bytes()
        assert hashlib.sha256(content).hexdigest() == expected["sha256"], name
        blob = b"blob " + str(len(content)).encode() + b"\0" + content
        assert hashlib.sha1(blob).hexdigest() == expected["git_blob"], name
