"""Behavior contracts for the canonical CI audit/artifact CLI seam."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def test_audit_receipts_cover_default_discovery_once(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/ci/suite_shards.py"),
         "--output", str(tmp_path)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    coverage = json.loads((tmp_path / "coverage.json").read_text())
    assert coverage["shards"] == 20
    canonical = coverage["canonical_files"]
    partitions = [(tmp_path / f"slice-{i:02d}.txt").read_text().splitlines()
                  for i in range(1, 21)]
    union = [file for partition in partitions for file in partition]
    assert canonical
    expected = sorted(str(path.relative_to(ROOT)) for path in (ROOT / "tests").rglob("test_*.py")
                      if not {"docker", "e2e", "integration"}.intersection(path.parts))
    assert sorted(canonical) == expected
    assert sorted(union) == expected
    assert coverage["canonical_file_count"] == coverage["union_count"] == len(expected)
    assert coverage["slice_file_counts"] == [len(partition) for partition in partitions]
    assert len(union) == len(set(union))
    assert all(partitions)
    assert coverage["head_sha"] == subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert coverage["cache_independent"] is True
    assert coverage["excluded_directory_parts"] == ["docker", "e2e", "integration"]


def test_failed_canonical_command_retains_exact_slice_result(tmp_path, monkeypatch):
    from scripts.ci import suite_shards

    root = tmp_path / "checkout"
    (root / "tests").mkdir(parents=True)
    (root / "scripts").mkdir()
    for name in ("test_one.py", "test_two.py"):
        (root / "tests" / name).write_text("def test_ok(): pass\n")
    (root / "scripts/run_tests.sh").write_text('printf "%s\\n" "$@"; exit 7\n')
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=CI fixture",
                    "-c", "user.email=fixture@example.invalid", "commit", "-m", "fixture"],
                   check=True, capture_output=True)
    monkeypatch.setattr(suite_shards, "ROOT", root)
    output = tmp_path / "receipts"
    assert suite_shards.run_slice(2, 2, output, 5) == 7
    result = json.loads((output / "result.json").read_text())
    assert result["status"] == "failed"
    assert result["exit_code"] == 7
    assert result["slice"] == "2/2"
    assert result["files"] == ["tests/test_two.py"]
    assert result["command"][:4] == ["bash", "scripts/run_tests.sh", "--slice", "2/2"]
    assert "2/2" in (output / "canonical.log").read_text()
    assert result["head_sha"] == json.loads((output / "coverage.json").read_text())["head_sha"]

    (root / "scripts/run_tests.sh").write_text("sleep 10\n")
    assert suite_shards.run_slice(1, 2, output, 0.05) == 124
    result = json.loads((output / "result.json").read_text())
    assert result["status"] == "timed_out"
    assert result["exit_code"] == 124
    assert result["slice"] == "1/2"

