#!/usr/bin/env python3
"""Archive a clone's committed workflows as inert, provenance-pinned test inputs.

Run before importing source. The destination must not exist: refusing to merge
snapshots prevents stale definitions from surviving a later upstream deletion.
No workflow is installed into the destination repository's .github/workflows.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PureWindowsPath
import subprocess


def is_safe_workflow_basename(name: str) -> bool:
    # Git tree names are POSIX data even when the destination host is Windows.
    # Reject both path grammars before creating any part of the destination.
    return (
        bool(name)
        and name not in {".", ".."}
        and "/" not in name
        and "\\" not in name
        and not PureWindowsPath(name).drive
        and Path(name).suffix in {".yml", ".yaml"}
    )


def snapshot(source: Path, destination: Path) -> None:
    def git(*args: str) -> bytes:
        return subprocess.check_output(["git", "-C", str(source), *args], timeout=60)

    revision = git("rev-parse", "HEAD").decode().strip()
    entries = git("ls-tree", "-z", f"{revision}:.github/workflows").split(b"\0")
    files = {}
    for entry in filter(None, entries):
        metadata, raw_name = entry.split(b"\t", 1)
        mode, kind, blob = metadata.decode().split()
        name = raw_name.decode()
        if mode != "100644" or kind != "blob" or not is_safe_workflow_basename(name):
            raise ValueError(f"unexpected workflow entry: {name}")
        files[name] = (blob, git("cat-file", "blob", blob))
    if not files:
        raise ValueError("upstream has no workflow definitions")

    destination.mkdir(parents=True, exist_ok=False)
    workflows = destination / "workflows"
    workflows.mkdir()
    manifest = {"repository": "https://github.com/NousResearch/hermes-agent", "revision": revision,
                "source_directory": ".github/workflows", "files": {}}
    for name, (blob, content) in sorted(files.items()):
        (workflows / name).write_bytes(content)
        manifest["files"][name] = {"git_blob": blob, "sha256": hashlib.sha256(content).hexdigest()}
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    snapshot(args.source, args.destination)


if __name__ == "__main__":
    main()
