"""The complete downgrade CLI operation is read-only for canonical storage (ADR-0001)."""

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from agent.memory_store_v2 import MemoryStoreV2

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "memv2_downgrade_export.py"


def hashes(directory):
    # SHM is SQLite's lock/read-mark bookkeeping, not persisted memory. A
    # mode=ro reader may create an EMPTY WAL alongside it; nonempty WAL
    # contents remain part of the byte-preservation contract.
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in directory.iterdir()
        if p.is_file() and p.name != "memory.db-shm"
        and not (p.name == "memory.db-wal" and p.stat().st_size == 0)
    }


def cli(home, dry_run):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--home", str(home), *(["--dry-run"] if dry_run else [])],
        env={**os.environ, "HERMES_HOME": str(home)}, capture_output=True, text=True, timeout=30,
    )


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("migrated", [False, True])
def test_cli_never_initializes_or_migrates_existing_store(tmp_path, monkeypatch, dry_run, migrated):
    home = tmp_path / "profile"
    monkeypatch.setenv("HERMES_HOME", str(home))
    store = MemoryStoreV2()
    store.load_from_disk()
    assert store.add("memory", "Canonical post-cutover record")["success"]
    assert store.add("user", "Canonical user record")["success"]
    store.close()
    memories = home / "memories"
    # An existing V2 database may lack the one-shot marker; export must
    # NEVER interpret this as permission to import flat files.
    with sqlite3.connect(memories / "memory.db") as db:
        if not migrated:
            db.execute("DELETE FROM meta WHERE key IN ('legacy_migrated','migration_manifest')")
        else:
            db.execute("UPDATE meta SET value='2000-01-01T00:00:00+00:00' WHERE key='legacy_migrated'")
    db.close()  # sqlite's context manager commits but does not close/checkpoint.
    (memories / "MEMORY.md").write_text("Legacy source not canonical", encoding="utf-8")
    (memories / "USER.md").write_text("Legacy user not canonical", encoding="utf-8")
    before = hashes(memories)
    proc = cli(home, dry_run)
    assert proc.returncode == 0, proc.stderr
    after = hashes(memories)
    assert after["memory.db"] == before["memory.db"]
    report = json.loads(proc.stdout)
    assert report["memory_db"]["sha256_before"] == before["memory.db"]
    assert report["memory_db"]["sha256_after"] == before["memory.db"]
    assert report["targets"]["memory"]["expected"] == 1
    assert report["targets"]["user"]["expected"] == 1
    assert report["targets"]["memory"]["post_cutover"] == int(migrated)
    if dry_run:
        assert after == before  # no schema, manifest, backup, projection or audit writes
    else:
        assert (memories / "MEMORY.md").read_text() == "Canonical post-cutover record"
        assert (memories / "USER.md").read_text() == "Canonical user record"
        for name in ("MEMORY.md", "USER.md"):
            backups = list(memories.glob(name + ".bak.*"))
            assert len(backups) == 1
            assert hashlib.sha256(backups[0].read_bytes()).hexdigest() == before[name]
        if "migration-manifest.json" in before:
            assert after["migration-manifest.json"] == before["migration-manifest.json"]


@pytest.mark.parametrize("kind", ["missing", "non_v2"])
@pytest.mark.parametrize("dry_run", [False, True])
def test_cli_diagnoses_missing_or_non_v2_without_creating_store(tmp_path, kind, dry_run):
    home = tmp_path / "profile"
    memories = home / "memories"
    memories.mkdir(parents=True)
    (memories / "MEMORY.md").write_text("Legacy data must remain intact", encoding="utf-8")
    if kind == "non_v2":
        with sqlite3.connect(memories / "memory.db") as db:
            db.execute("CREATE TABLE unrelated(value TEXT)")
    before = hashes(memories)
    proc = cli(home, dry_run)
    assert proc.returncode == 2
    assert "memory.db" in proc.stderr
    assert ("missing" if kind == "missing" else "V2") in proc.stderr
    assert proc.stdout == ""
    assert hashes(memories) == before


@pytest.mark.parametrize("dry_run", [False, True])
def test_cli_reads_committed_wal_without_checkpoint_or_access_writes(tmp_path, monkeypatch, dry_run):
    home = tmp_path / "profile"
    monkeypatch.setenv("HERMES_HOME", str(home))
    store = MemoryStoreV2()
    store.load_from_disk()
    try:
        assert store.add("memory", "Committed WAL-only record")["success"]
        memories = home / "memories"
        wal = memories / "memory.db-wal"
        assert wal.is_file() and wal.stat().st_size > 0
        before = hashes(memories)
        rows_before = store.visible_rows("memory")
        proc = cli(home, dry_run)
        assert proc.returncode == 0, proc.stderr
        report = json.loads(proc.stdout)
        assert report["targets"]["memory"]["expected"] == 1
        after = hashes(memories)
        assert after["memory.db"] == before["memory.db"]
        assert after["memory.db-wal"] == before["memory.db-wal"]
        assert store.visible_rows("memory") == rows_before
        if dry_run:
            assert after == before
        else:
            assert (memories / "MEMORY.md").read_text() == "Committed WAL-only record"
    finally:
        store.close()
