#!/usr/bin/env python3
"""Audit canonical default discovery and execute one immutable MEMV2 CI slice."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import run_tests_parallel as runner

CANDIDATE = "57a309a6bab854b83ad52cc322dabf9c4c6844a4"
SHARDS = 20


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    files = runner._discover_files([ROOT / p for p in runner._DEFAULT_ROOTS])
    assert files and len(files) == len(set(files))
    slices = [runner._slice_files(files, i, SHARDS, {}, ROOT) for i in range(1, SHARDS + 1)]
    counts = Counter(f for bucket in slices for f in bucket)
    assert set(counts) == set(files), "Shard union differs from canonical default discovery"
    assert all(n == 1 for n in counts.values()), "Overlapping slices"
    assert all(slices), "Empty slice"
    # Cached duration observations must never influence membership.
    hostile_cache = {runner._format_file(f, ROOT): float(i + 1) for i, f in enumerate(files)}
    for i, bucket in enumerate(slices, 1):
        assert runner._slice_files(files, i, SHARDS, hostile_cache, ROOT) == bucket
        (output / f"slice-{i:02d}.txt").write_text(
            "".join(runner._format_file(f, ROOT) + "\n" for f in bucket), encoding="utf-8")
    canonical = [runner._format_file(f, ROOT) for f in files]
    manifest = {
        "candidate_sha": CANDIDATE, "shards": SHARDS,
        "canonical_default_roots": runner._DEFAULT_ROOTS,
        "excluded_directory_parts": sorted(runner._SKIP_PARTS),
        "pytest_default_addopts": "-m 'not integration and not live'",
        "canonical_file_count": len(files), "union_count": len(counts),
        "disjoint": True, "cache_independent": True,
        "canonical_files_sha256": hashlib.sha256("\n".join(canonical).encode()).hexdigest(),
        "slice_file_counts": [len(bucket) for bucket in slices],
        "canonical_files": canonical,
    }
    write_json(output / "coverage.json", manifest)
    print(json.dumps({k: v for k, v in manifest.items() if k != "canonical_files"}, indent=2))
    return manifest


def run_slice(index: int, output: Path) -> int:
    assert 1 <= index <= SHARDS
    verify(output)
    command = ["bash", "scripts/run_tests.sh", "--slice", f"{index}/{SHARDS}",
               "-j", "2", "--file-retries", "0"]
    started = time.time()
    result = {"candidate_sha": CANDIDATE, "head_sha": os.environ.get("GITHUB_SHA"),
              "slice": index, "shards": SHARDS, "workers": 2, "retries": 0,
              "command": command, "started_unix": started, "exit_code": None}
    write_json(output / "result.json", result)
    with (output / "canonical.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        assert process.stdout is not None
        for line in process.stdout:
            log.write(line)
            log.flush()
            print(line, end="", flush=True)
        code = process.wait()
    result.update(exit_code=code, finished_unix=time.time(), duration_seconds=time.time() - started)
    write_json(output / "result.json", result)
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--run-slice", type=int)
    args = parser.parse_args()
    if args.run_slice is None:
        verify(args.output)
        return 0
    return run_slice(args.run_slice, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
