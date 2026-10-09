# Ported from the Architecture 2.0 Hermes fork (MIT License)
# Copyright (c) 2025-2026 Dmitry Antipin (multi-agent orchestration fork)
"""Legacy-migration manifest tests (ticket #4).

These tests pin the migration contract added on top of the arch2 port:

- every ``§``-entry imports as a ``legacy`` row with the ORIGINAL text,
  nothing is deleted, source files stay byte-identical;
- ``meta['migration_manifest']`` carries sha256 hashes of the source files,
  recognized/imported/skipped counts with per-entry reasons, a schema
  version, and the outcome — committed in the SAME transaction as the row
  imports;
- a human-readable ``<memories>/migration-manifest.json`` is emitted after
  the commit (best-effort);
- re-running imports nothing and never duplicates rows or rewrites the
  manifest;
- an interrupted import rolls back atomically (no rows, no markers, schema
  intact) and a clean retry succeeds.
"""

from __future__ import annotations

import hashlib
import json
import uuid

import pytest

import tools.memory_tool as mt
from agent.memory_store_v2 import MemoryStoreV2


@pytest.fixture()
def mem_dir(tmp_path, monkeypatch):
    """Point the memory directory at a temp dir (canonical fixture pattern)."""
    monkeypatch.setattr(mt, "get_memory_dir", lambda: tmp_path)
    return tmp_path


def _db_rows(store: MemoryStoreV2, sql: str, params: tuple = ()) -> list:
    return list(store._connect().execute(sql, params).fetchall())


def _meta(store: MemoryStoreV2, key: str):
    rows = _db_rows(store, "SELECT value FROM meta WHERE key=?", (key,))
    return rows[0][0] if rows else None


def _manifest(store: MemoryStoreV2):
    value = _meta(store, "migration_manifest")
    return json.loads(value) if value else None


class TestMigrationManifest:
    def test_manifest_records_hashes_counts_and_skip_reasons(self, mem_dir):
        mem_bytes = "Старая заметка один\n§\n\n§\nСтарая заметка два".encode("utf-8")
        user_bytes = "Юзер предпочитает тёмную тему".encode("utf-8")
        (mem_dir / "MEMORY.md").write_bytes(mem_bytes)
        (mem_dir / "USER.md").write_bytes(user_bytes)
        s = MemoryStoreV2()
        s.load_from_disk()

        manifest = _manifest(s)
        assert manifest is not None, "migration manifest must be recorded in meta"
        assert manifest["schema_version"] == 1
        assert manifest["outcome"] == "migrated"
        assert manifest["migrated_at"]

        mem_src = manifest["sources"]["memory"]
        assert mem_src["exists"] is True
        assert mem_src["sha256"] == hashlib.sha256(mem_bytes).hexdigest()
        assert mem_src["recognized"] == 3  # two entries + one empty segment
        assert mem_src["imported"] == 2
        assert mem_src["skipped"] == [{"reason": "empty entry", "content": ""}]

        user_src = manifest["sources"]["user"]
        assert user_src["sha256"] == hashlib.sha256(user_bytes).hexdigest()
        assert user_src["recognized"] == user_src["imported"] == 1
        assert user_src["skipped"] == []

        assert manifest["totals"] == {"recognized": 4, "imported": 3, "skipped": 1}

        # Imported rows carry the ORIGINAL text, typed legacy/active.
        rows = _db_rows(s, "SELECT target, type, content, status FROM memories")
        contents = {(r["target"], r["content"]) for r in rows}
        assert contents == {
            ("memory", "Старая заметка один"),
            ("memory", "Старая заметка два"),
            ("user", "Юзер предпочитает тёмную тему"),
        }
        assert all(r["type"] == "legacy" and r["status"] == "active" for r in rows)
        s.close()

    def test_manifest_artifact_written_after_commit(self, mem_dir):
        (mem_dir / "MEMORY.md").write_text("Запись А", encoding="utf-8")
        s = MemoryStoreV2()
        s.load_from_disk()
        artifact = mem_dir / "migration-manifest.json"
        assert artifact.exists()
        assert json.loads(artifact.read_text(encoding="utf-8")) == _manifest(s)
        s.close()

    def test_missing_source_file_reported_with_null_hash(self, mem_dir):
        (mem_dir / "MEMORY.md").write_text("Только память", encoding="utf-8")
        s = MemoryStoreV2()
        s.load_from_disk()
        user_src = _manifest(s)["sources"]["user"]
        assert user_src["exists"] is False
        assert user_src["sha256"] is None
        assert user_src["recognized"] == user_src["imported"] == 0
        assert user_src["skipped"] == []
        s.close()

    def test_unreadable_source_file_skipped_with_read_error(self, mem_dir):
        (mem_dir / "MEMORY.md").mkdir()  # a directory where the file should be
        (mem_dir / "USER.md").write_text("Юзер ок", encoding="utf-8")
        s = MemoryStoreV2()
        s.load_from_disk()  # must not raise
        manifest = _manifest(s)
        mem_src = manifest["sources"]["memory"]
        assert mem_src["exists"] is True
        assert mem_src["sha256"] is None
        assert mem_src["read_error"] is not None
        assert mem_src["recognized"] == mem_src["imported"] == 0
        assert manifest["sources"]["user"]["imported"] == 1
        assert _db_rows(s, "SELECT COUNT(*) AS c FROM memories")[0]["c"] == 1
        s.close()


class TestMigrationNothingDeleted:
    def test_source_files_byte_identical_and_all_entries_imported(self, mem_dir):
        (mem_dir / "MEMORY.md").write_text("Запись A\n§\nЗапись B", encoding="utf-8")
        (mem_dir / "USER.md").write_text("Юзер A", encoding="utf-8")
        before = {
            "memory": (mem_dir / "MEMORY.md").read_bytes(),
            "user": (mem_dir / "USER.md").read_bytes(),
        }
        s = MemoryStoreV2()
        s.load_from_disk()
        assert (mem_dir / "MEMORY.md").read_bytes() == before["memory"]
        assert (mem_dir / "USER.md").read_bytes() == before["user"]
        rows = _db_rows(s, "SELECT target, content FROM memories")
        assert {(r["target"], r["content"]) for r in rows} == {
            ("memory", "Запись A"),
            ("memory", "Запись B"),
            ("user", "Юзер A"),
        }
        s.close()


class TestMigrationDuplicateSkip:
    def test_duplicate_rows_skipped_with_reason(self, mem_dir):
        # A row written by another path (e.g. the installer, ticket #9) is
        # already in the store BEFORE the one-shot migration runs.
        s = MemoryStoreV2()
        conn = s._connect()
        s._init_schema(conn)
        conn.execute(
            "INSERT INTO memories(id, target, type, content, importance,"
            " confidence, status, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), "memory", "fact", "Дубль", 0.5, 0.7, "active",
             "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
        )
        (mem_dir / "MEMORY.md").write_text("Дубль\n§\nНовая", encoding="utf-8")
        s.load_from_disk()

        mem_src = _manifest(s)["sources"]["memory"]
        assert mem_src["recognized"] == 2
        assert mem_src["imported"] == 1
        assert mem_src["skipped"] == [
            {"reason": "duplicate: already present in store", "content": "Дубль"}
        ]
        rows = _db_rows(s, "SELECT content FROM memories ORDER BY content")
        assert [r["content"] for r in rows] == ["Дубль", "Новая"]
        s.close()


class TestMigrationIdempotency:
    def test_second_run_imports_nothing_and_keeps_original_manifest(self, mem_dir):
        (mem_dir / "MEMORY.md").write_text("Запись А\n§\nЗапись Б", encoding="utf-8")
        s1 = MemoryStoreV2()
        s1.load_from_disk()
        first_manifest = _meta(s1, "migration_manifest")
        artifact_before = (mem_dir / "migration-manifest.json").read_text(
            encoding="utf-8"
        )
        s1.close()

        # External edit AFTER migration must not re-import or duplicate.
        (mem_dir / "MEMORY.md").write_text(
            "Запись А\n§\nЗапись Б\n§\nНовая поздняя", encoding="utf-8"
        )
        s2 = MemoryStoreV2()
        s2.load_from_disk()
        assert _db_rows(s2, "SELECT COUNT(*) AS c FROM memories")[0]["c"] == 2
        # The manifest documents the ONE migration event: left untouched.
        assert _meta(s2, "migration_manifest") == first_manifest
        assert (
            mem_dir / "migration-manifest.json"
        ).read_text(encoding="utf-8") == artifact_before
        s2.close()


class TestMigrationInterrupted:
    def test_interrupted_import_rolls_back_and_retry_succeeds(self, mem_dir, monkeypatch):
        mem_text = "Запись один\n§\nЗапись два"
        (mem_dir / "MEMORY.md").write_text(mem_text, encoding="utf-8")
        before = (mem_dir / "MEMORY.md").read_bytes()

        real_uuid4 = uuid.uuid4
        calls = {"n": 0}
        fail_once = {"armed": True}

        def poisoned():
            calls["n"] += 1
            if calls["n"] >= 2 and fail_once["armed"]:
                fail_once["armed"] = False  # fail exactly one transaction
                raise RuntimeError("injected mid-import failure")
            return real_uuid4()

        # Second row insert of the first attempt raises inside the transaction.
        monkeypatch.setattr("agent.memory_store_v2.uuid.uuid4", poisoned)

        s = MemoryStoreV2()
        with pytest.raises(RuntimeError, match="injected mid-import failure"):
            s.load_from_disk()

        # Atomic rollback: no rows, no markers, schema intact, files untouched.
        assert _db_rows(s, "SELECT COUNT(*) AS c FROM memories")[0]["c"] == 0
        assert _meta(s, "legacy_migrated") is None
        assert _meta(s, "migration_manifest") is None
        assert _db_rows(s, "PRAGMA integrity_check")[0][0] == "ok"
        assert (mem_dir / "MEMORY.md").read_bytes() == before
        assert not (mem_dir / "migration-manifest.json").exists()

        # Clean retry on the SAME store object succeeds and produces the
        # manifest (the store stays usable after the interruption).
        s.load_from_disk()
        manifest = _manifest(s)
        assert manifest["outcome"] == "migrated"
        assert manifest["sources"]["memory"]["recognized"] == 2
        assert manifest["sources"]["memory"]["imported"] == 2
        assert manifest["sources"]["memory"]["skipped"] == []
        assert _db_rows(s, "SELECT COUNT(*) AS c FROM memories")[0]["c"] == 2
        assert _meta(s, "legacy_migrated") is not None
        artifact = json.loads(
            (mem_dir / "migration-manifest.json").read_text(encoding="utf-8")
        )
        assert artifact == manifest
        s.close()


class TestManifestArtifactBestEffort:
    def test_artifact_write_failure_does_not_fail_migration(self, mem_dir, monkeypatch):
        (mem_dir / "MEMORY.md").write_text("Запись А", encoding="utf-8")

        def boom(path, content, **kwargs):
            raise OSError("disk full (simulated)")

        monkeypatch.setattr("agent.memory_store_v2.atomic_write_text", boom)
        s = MemoryStoreV2()
        s.load_from_disk()  # must not raise: artifact is best-effort
        assert _meta(s, "legacy_migrated") is not None
        assert _manifest(s)["outcome"] == "migrated"
        assert _db_rows(s, "SELECT COUNT(*) AS c FROM memories")[0]["c"] == 1
        assert not (mem_dir / "migration-manifest.json").exists()
        s.close()
