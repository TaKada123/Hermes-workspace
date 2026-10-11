"""Downgrade-export tests (ticket #11).

Pins the verified rollback path from ``sqlite_v2`` back to the legacy flat
store, mapped to the ticket's acceptance criteria:

- (a) export counts match the visible rows per target (AC «проверка
  количества»);
- (b) exported files parse as valid ``§``-entries via the flat MemoryStore
  (AC «Экспорт записей … в legacy-формат §-записей»);
- (c) entries created AFTER a simulated cutover appear in the export
  (AC «Записи, созданные в V2, видны в legacy-файлах после экспорта»);
- (d) memory.db is preserved byte-identical (AC «memory.db сохраняется
  при откате»);
- (e) ``.bak`` is created before overwriting pre-existing files;
- (f) full round-trip: file → sqlite_v2 (migration) → post-cutover adds →
  export → flat MemoryStore reads every entry (AC «Тесты покрывают оба
  направления (file→sqlite_v2 и обратно)» + AC «Возврат флага на legacy
  — агент работает на flat store»);
- (g) dry-run reports counts and writes nothing;
- (h) an empty store exports empty files without crashing;
- awareness-written telemetry rows are skipped (per export contract);
- an audit marker ``downgrade-export-report.json`` is written;
- the ``scripts/memv2_downgrade_export.py`` entry point round-trips a real
  HERMES_HOME over a subprocess.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import tools.memory_tool as mt
from agent.memory_downgrade import export_legacy
from agent.memory_store_v2 import MemoryStoreV2
from tools.memory_tool_store import MemoryStore

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "memv2_downgrade_export.py"


@pytest.fixture()
def mem_dir(tmp_path, monkeypatch):
    """Point the memory directory at a temp dir (canonical fixture pattern)."""
    monkeypatch.setattr(mt, "get_memory_dir", lambda: tmp_path)
    return tmp_path


@pytest.fixture()
def store(mem_dir):
    s = MemoryStoreV2()
    s.load_from_disk()
    yield s
    s.close()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _report_target(report, target):
    return report["targets"][target]


class TestExportCounts:
    def test_counts_match_visible_rows_per_target(self, store, tmp_path):
        """(a) expected == written == visible-row count; non-visible rows excluded."""
        for i in range(3):
            store.add("memory", f"память факт {i}", written_by="main:test")
        store.add("user", "юзер один", written_by="main:test")
        store.add("user", "юзер два", written_by="main:test")
        # Deprecated rows are not visible and must not be exported.
        store.deprecate("user", "юзер два", reason="устарело")
        out = tmp_path / "export"
        report = export_legacy(store, out_dir=out)

        mem = _report_target(report, "memory")
        assert (mem["expected"], mem["written"], mem["ok"]) == (3, 3, True)
        usr = _report_target(report, "user")
        assert (usr["expected"], usr["written"], usr["ok"]) == (1, 1, True)
        raw = (out / "USER.md").read_text(encoding="utf-8")
        assert "юзер один" in raw and "юзер два" not in raw


class TestExportedFilesAreLegacy:
    def test_exported_files_parse_as_valid_delimited_entries(self, store, tmp_path, monkeypatch):
        """(b) exported files are valid §-delimited files the flat store reads."""
        contents = ["Первый факт", "Второй факт § с знаком", "Третий факт"]
        for c in contents:
            store.add("memory", c, written_by="main:test")
        out = tmp_path / "export"
        export_legacy(store, out_dir=out)

        raw = (out / "MEMORY.md").read_text(encoding="utf-8")
        parsed = MemoryStore._parse_entries(raw)
        assert sorted(parsed) == sorted(contents)

        monkeypatch.setattr(mt, "get_memory_dir", lambda: out)
        flat = MemoryStore()
        flat.load_from_disk()
        assert sorted(flat.memory_entries) == sorted(contents)


class TestPostCutover:
    def test_entries_created_after_cutover_appear_in_export(self, mem_dir, tmp_path):
        """(c) post-migration (post-cutover) adds show up in the exported file."""
        (mem_dir / "MEMORY.md").write_text("Старая §-запись", encoding="utf-8")
        s = MemoryStoreV2()
        s.load_from_disk()  # one-shot migration == the cutover point
        try:
            s.add("memory", "Запись после cutover", written_by="main:test")
            report = export_legacy(s, out_dir=tmp_path / "export")
        finally:
            s.close()

        raw = (tmp_path / "export" / "MEMORY.md").read_text(encoding="utf-8")
        assert "Старая §-запись" in raw
        assert "Запись после cutover" in raw
        assert _report_target(report, "memory")["expected"] == 2


class TestPostCutoverCount:
    """Export report carries a per-target ``post_cutover`` count — rows
    created AFTER ``meta['legacy_migrated']`` — without changing the export
    itself (it stays full-store)."""

    def test_post_cutover_reported_per_target(self, mem_dir, tmp_path):
        (mem_dir / "MEMORY.md").write_text("До cutover", encoding="utf-8")
        s = MemoryStoreV2()
        s.load_from_disk()  # migration = cutover point
        try:
            # Timestamps are second-granular: move past the marker's second.
            time.sleep(1.1)
            s.add("memory", "После cutover", written_by="main:test")
            s.add("user", "Юзер после cutover", written_by="main:test")
            report = export_legacy(s, out_dir=tmp_path / "export")
        finally:
            s.close()

        assert report["legacy_migrated_at"] is not None
        assert _report_target(report, "memory")["post_cutover"] == 1
        assert _report_target(report, "user")["post_cutover"] == 1
        # Export semantics unchanged: the legacy file still carries EVERY
        # visible row (pre- and post-cutover alike).
        raw = (tmp_path / "export" / "MEMORY.md").read_text(encoding="utf-8")
        assert "До cutover" in raw and "После cutover" in raw

    def test_post_cutover_zero_when_no_migration_marker(self, store, tmp_path):
        # Without the marker there is no cutover point: legacy_migrated_at is
        # null and post_cutover counts 0.
        store.add("memory", "запись", written_by="main:test")
        store._connect().execute("DELETE FROM meta WHERE key='legacy_migrated'")
        report = export_legacy(store, out_dir=tmp_path / "export")
        assert report["legacy_migrated_at"] is None
        assert _report_target(report, "memory")["post_cutover"] == 0

    def test_dry_run_reports_post_cutover_too(self, mem_dir, tmp_path):
        (mem_dir / "MEMORY.md").write_text("До cutover", encoding="utf-8")
        s = MemoryStoreV2()
        s.load_from_disk()
        try:
            time.sleep(1.1)
            s.add("memory", "После cutover", written_by="main:test")
            report = export_legacy(s, out_dir=tmp_path / "export", dry_run=True)
        finally:
            s.close()
        assert report["dry_run"] is True
        assert _report_target(report, "memory")["post_cutover"] == 1
        assert not (tmp_path / "export").exists()


class TestMemoryDbPreserved:
    def test_memory_db_byte_identical_after_export(self, store, mem_dir, tmp_path):
        """(d) memory.db survives the export byte-identical."""
        store.add("memory", "факт", written_by="main:test")
        store.add("user", "юзер", written_by="main:test")
        db = mem_dir / "memory.db"
        before = _sha256(db)
        report = export_legacy(store, out_dir=tmp_path / "export")
        after = _sha256(db)

        assert db.exists()
        assert before == after
        assert report["memory_db"]["unchanged"] is True
        assert report["memory_db"]["sha256_before"] == before
        assert report["memory_db"]["sha256_after"] == after


class TestBackups:
    def test_backup_created_for_preexisting_files(self, store, tmp_path):
        """(e) pre-existing files get a timestamped .bak before overwrite."""
        store.add("memory", "новая запись", written_by="main:test")
        out = tmp_path / "export"
        out.mkdir()
        (out / "MEMORY.md").write_text("Старое содержимое вручную", encoding="utf-8")
        report = export_legacy(store, out_dir=out)

        baks = list(out.glob("MEMORY.md.bak.*"))
        assert len(baks) == 1
        assert baks[0].read_text(encoding="utf-8") == "Старое содержимое вручную"
        assert _report_target(report, "memory")["backup"] == str(baks[0])
        # USER.md did not exist: no backup, but the (empty) export is written.
        assert _report_target(report, "user")["backup"] is None
        assert (out / "USER.md").exists()


class TestRoundTrip:
    def test_full_roundtrip_file_to_v2_and_back(self, mem_dir, tmp_path, monkeypatch):
        """(f) file → sqlite_v2 (migration) → adds → export → flat store sees all."""
        (mem_dir / "MEMORY.md").write_text(
            "До cutover один\n§\nДо cutover два", encoding="utf-8")
        (mem_dir / "USER.md").write_text("Юзер до cutover", encoding="utf-8")
        s = MemoryStoreV2()
        s.load_from_disk()
        db = mem_dir / "memory.db"
        try:
            s.add("memory", "После cutover один", written_by="main:test")
            s.add("user", "Юзер после cutover", written_by="main:test")
            db_before = _sha256(db)
            report = export_legacy(s, out_dir=tmp_path / "export")
            db_after = _sha256(db)
        finally:
            s.close()

        assert db_after == db_before  # export never touched the DB
        assert all(t["ok"] for t in report["targets"].values())

        # Flag flip back to legacy: the agent's flat MemoryStore now reads the
        # exported files from the same home.
        monkeypatch.setattr(mt, "get_memory_dir", lambda: tmp_path / "export")
        flat = MemoryStore()
        flat.load_from_disk()
        assert sorted(flat.memory_entries) == sorted(
            ["До cutover один", "До cutover два", "После cutover один"])
        assert sorted(flat.user_entries) == sorted(
            ["Юзер до cutover", "Юзер после cutover"])


class TestDryRun:
    def test_dry_run_writes_nothing(self, store, tmp_path):
        """(g) dry-run reports projected counts and touches nothing on disk."""
        store.add("memory", "факт", written_by="main:test")
        out = tmp_path / "export"
        report = export_legacy(store, out_dir=out, dry_run=True)

        assert report["dry_run"] is True
        mem = _report_target(report, "memory")
        assert mem["expected"] == 1
        assert mem["written"] == 0
        assert mem["ok"] is None
        assert not out.exists()
        assert report["audit_file"] is None


class TestEmptyStore:
    def test_empty_store_exports_empty_files(self, store, tmp_path, monkeypatch):
        """(h) zero visible rows → empty files, ok=True, no crash."""
        out = tmp_path / "export"
        report = export_legacy(store, out_dir=out)

        for target in ("memory", "user"):
            t = _report_target(report, target)
            assert (t["expected"], t["written"], t["ok"]) == (0, 0, True)
        assert (out / "MEMORY.md").read_text(encoding="utf-8") == ""
        assert (out / "USER.md").read_text(encoding="utf-8") == ""

        monkeypatch.setattr(mt, "get_memory_dir", lambda: out)
        flat = MemoryStore()
        flat.load_from_disk()
        assert flat.memory_entries == [] and flat.user_entries == []


class TestAwarenessSkipped:
    def test_awareness_rows_not_exported(self, store, tmp_path):
        """Awareness telemetry (written_by ``awareness*``) never reaches legacy files."""
        store.add("memory", "обычная запись", written_by="main:test")
        store.add("memory", "телеметрия awareness", written_by="awareness:stuck")
        out = tmp_path / "export"
        report = export_legacy(store, out_dir=out)

        assert _report_target(report, "memory")["expected"] == 1
        raw = (out / "MEMORY.md").read_text(encoding="utf-8")
        assert "обычная запись" in raw
        assert "телеметрия" not in raw


class TestAuditMarker:
    def test_audit_marker_written_with_counts(self, store, tmp_path):
        store.add("memory", "факт", written_by="main:test")
        store.add("user", "юзер", written_by="main:test")
        out = tmp_path / "export"
        report = export_legacy(store, out_dir=out)

        marker = out / "downgrade-export-report.json"
        assert marker.exists()
        saved = json.loads(marker.read_text(encoding="utf-8"))
        assert saved["schema_version"] == 1
        assert saved["exported_at"]
        assert saved["dry_run"] is False
        assert saved["targets"]["memory"]["written"] == 1
        assert saved["targets"]["memory"]["ok"] is True
        assert saved["targets"]["user"]["written"] == 1
        assert report["audit_file"] == str(marker)


class TestScriptEntryPoint:
    """Thin CLI over a REAL subprocess — the cutover operator's path."""

    @staticmethod
    def _run(args, home: Path):
        env = {**os.environ, "HERMES_HOME": str(home)}
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True, text=True, env=env, cwd=REPO_ROOT, timeout=120,
        )

    @pytest.fixture()
    def v2_home(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        monkeypatch.setattr(mt, "get_memory_dir", lambda: home / "memories")
        s = MemoryStoreV2()
        s.load_from_disk()
        s.add("memory", "через скрипт", written_by="main:test")
        s.add("user", "юзер скрипта", written_by="main:test")
        s.close()
        return home

    def test_script_exports_and_prints_report(self, v2_home):
        proc = self._run(["--targets", "memory,user"], v2_home)
        assert proc.returncode == 0, proc.stderr
        report = json.loads(proc.stdout)
        assert report["dry_run"] is False
        assert _report_target(report, "memory")["ok"] is True
        assert _report_target(report, "memory")["written"] == 1
        assert _report_target(report, "user")["written"] == 1
        mem = v2_home / "memories"
        raw = (mem / "MEMORY.md").read_text(encoding="utf-8")
        assert "через скрипт" in raw
        assert (mem / "downgrade-export-report.json").exists()
        assert (mem / "memory.db").exists()  # preserved

    def test_script_dry_run_writes_nothing(self, v2_home):
        mem = v2_home / "memories"
        # The v2 store maintains its own projections; dry-run must not touch
        # them, create backups, or write the audit marker.
        projection_before = (mem / "MEMORY.md").read_bytes()
        proc = self._run(["--dry-run"], v2_home)
        assert proc.returncode == 0, proc.stderr
        report = json.loads(proc.stdout)
        assert report["dry_run"] is True
        assert _report_target(report, "memory")["expected"] == 1
        assert (mem / "MEMORY.md").read_bytes() == projection_before
        assert not list(mem.glob("*.bak.*"))
        assert not (mem / "downgrade-export-report.json").exists()

    def test_script_rejects_invalid_memory_char_limit(self, v2_home):
        """Malformed config must fail instead of silently using export defaults."""
        mem = v2_home / "memories"
        projections_before = {
            name: (mem / name).read_bytes() for name in ("MEMORY.md", "USER.md")
        }
        (v2_home / "config.yaml").write_text(
            "memory:\n  memory_char_limit: not-an-integer\n", encoding="utf-8"
        )

        proc = self._run(["--targets", "memory,user"], v2_home)

        assert proc.returncode == 2
        assert "not-an-integer" in proc.stderr
        assert proc.stdout == ""
        assert {
            name: (mem / name).read_bytes() for name in ("MEMORY.md", "USER.md")
        } == projections_before
        assert not (mem / "downgrade-export-report.json").exists()
        assert not list(mem.glob("*.bak.*"))
