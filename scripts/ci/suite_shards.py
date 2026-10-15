#!/usr/bin/env python3
"""Audit default-discovery partitions and archive a canonical slice's receipts.

No branch/baseline assumptions; membership belongs to the canonical runner.
Default discovery excludes integration/e2e/docker directories and pytest's
configured integration/live markers. This is not an integration or E2E lane.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import run_tests_parallel as runner  # noqa: E402


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify(output: Path, shards: int) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        encoding="utf-8", errors="replace", timeout=30).strip()
    if os.environ.get("GITHUB_SHA") not in (None, head):
        raise ValueError("Checkout differs from GITHUB_SHA")
    files = runner._discover_files([ROOT / p for p in runner._DEFAULT_ROOTS])
    assert files and len(files) == len(set(files))
    slices = [runner._slice_files(files, i, shards, {}, ROOT) for i in range(1, shards + 1)]
    counts = Counter(f for bucket in slices for f in bucket)
    assert set(counts) == set(files), "Shard union differs from canonical default discovery"
    assert all(n == 1 for n in counts.values()), "Overlapping slices"
    assert all(slices), "Empty slice"
    hostile_cache = {runner._format_file(f, ROOT): float(i + 1) for i, f in enumerate(files)}
    for i, bucket in enumerate(slices, 1):
        assert runner._slice_files(files, i, shards, hostile_cache, ROOT) == bucket
        (output / f"slice-{i:02d}.txt").write_text(
            "".join(runner._format_file(f, ROOT) + "\n" for f in bucket), encoding="utf-8")
    canonical = [runner._format_file(f, ROOT) for f in files]
    manifest = {
        "head_sha": head, "shards": shards,
        "canonical_default_roots": runner._DEFAULT_ROOTS,
        "excluded_directory_parts": sorted(runner._SKIP_PARTS),
        "pytest_selection": "project default addopts (no marker override)",
        "canonical_file_count": len(files), "union_count": len(counts),
        "disjoint": True, "cache_independent": True,
        "canonical_files_sha256": hashlib.sha256("\n".join(canonical).encode()).hexdigest(),
        "slice_file_counts": [len(bucket) for bucket in slices],
        "canonical_files": canonical,
    }
    write_json(output / "coverage.json", manifest)
    print(json.dumps({k: v for k, v in manifest.items() if k != "canonical_files"}, indent=2))
    return manifest


def run_slice(index: int, shards: int, output: Path, timeout: float) -> int:
    import psutil
    from agent.deadline import _process_tree_snapshot, kill_process_tree

    manifest = verify(output, shards)
    command = ["bash", "scripts/run_tests.sh", "--slice", f"{index}/{shards}",
               "-j", "2", "--file-retries", "0", "-v", "--tb=short"]
    started = time.time()
    result = {"head_sha": manifest["head_sha"], "slice": f"{index}/{shards}",
              "files": (output / f"slice-{index:02d}.txt").read_text(encoding="utf-8-sig").splitlines(),
              "command": command, "started_unix": started, "exit_code": None,
              "status": "running"}
    write_json(output / "result.json", result)
    with (output / "canonical.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
            status = "passed" if code == 0 else "failed"
        except subprocess.TimeoutExpired:
            # Retain PID + creation-time identities before SIGTERM can orphan
            # detached children. Parent exit does not imply the tree is dead.
            with _process_tree_snapshot(process.pid, hard_kill=False) as descendants:
                try:
                    kill_process_tree(process.pid, sig=signal.SIGTERM)
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        kill_process_tree(process.pid)
                        process.wait(timeout=10)
                finally:
                    for child in reversed(descendants):
                        try:
                            child.kill()  # psutil rejects a recycled PID.
                        except psutil.NoSuchProcess:
                            pass
            code, status = 124, "timed_out"
    result.update(exit_code=code, status=status, finished_unix=time.time(),
                  duration_seconds=time.time() - started)
    write_json(output / "result.json", result)
    print((output / "canonical.log").read_text(encoding="utf-8-sig", errors="replace"), flush=True)
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--shards", type=int, default=20)
    parser.add_argument("--run-slice", type=int)
    parser.add_argument("--timeout", type=float, default=3300)
    args = parser.parse_args()
    if args.shards < 2 or (args.run_slice is not None and not 1 <= args.run_slice <= args.shards):
        parser.error("shards must be >= 2 and slice must be in 1..shards")
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    if args.run_slice is None:
        verify(args.output, args.shards)
        return 0
    return run_slice(args.run_slice, args.shards, args.output, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
