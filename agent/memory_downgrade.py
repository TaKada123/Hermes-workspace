"""Verified downgrade export: MemoryStoreV2 → legacy §-delimited files (ticket #11).

The return path of the two-level rollback: when a profile flips
``memory.backend`` back to ``file`` (or drops the flag), the flat
``MemoryStore`` reads MEMORY.md/USER.md again — this module guarantees those
files contain every entry created in V2 after the cutover, with a count
verification the operator can check.

Contract:

- exports the canonical store's *visible* rows per target — status
  ``active``/``pinned`` (``_visible_rows`` semantics), in snapshot priority
  order, with awareness telemetry (``written_by`` starting with
  ``awareness``) skipped: that channel never sat in the v2 prompt and must
  not start doing so on legacy;
- writes §-delimited files (``ENTRY_DELIMITER`` join, raw content — the same
  shape the v2 projections use) into ``HERMES_HOME/memories/`` or a
  caller-supplied directory;
- verifies counts: each target reports ``expected`` (visible rows) vs
  ``written`` (entries parsed back from the file) with an ``ok`` flag;
- before overwriting a pre-existing file creates a timestamped
  ``<file>.bak.<ts>`` copy;
- NEVER opens memory.db for writing: the file is preserved byte-identical
  (sha256 before/after recorded in the report);
- writes an audit marker ``downgrade-export-report.json`` next to the
  exported files (timestamps + counts);
- ``dry_run=True`` reports projected counts and writes nothing at all.

Round-trip semantics: after a successful export, flipping
``memory.backend`` to ``file`` makes the agent read the exported §-files via
the flat MemoryStore and see exactly the exported entries; memory.db stays
on disk untouched for a later re-cutover (the migration manifest keeps a
re-migration idempotent).
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from tools.memory_tool_store import ENTRY_DELIMITER, MemoryStore
from utils import atomic_write_text

# Version of the downgrade-export report JSON (memories/downgrade-export-
# report.json). Bump only when the shape changes; readers must check it.
EXPORT_REPORT_VERSION = 1

# target → legacy projection filename in the memories directory.
EXPORT_TARGETS = {"memory": "MEMORY.md", "user": "USER.md"}

# Rows written by the awareness controller are per-turn telemetry: excluded
# from the static v2 snapshot by policy, and excluded from the legacy export
# for the same reason (legacy files go straight into the prompt).
_AWARENESS_PREFIX = "awareness"

_REPORT_NAME = "downgrade-export-report.json"


def _sha256(path: Path) -> Optional[str]:
    """Hex sha256 of *path*, or None when it does not exist / is unreadable."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _export_rows(store, target: str) -> List[Any]:
    """Visible export rows: ``_visible_rows`` minus awareness telemetry."""
    rows = store._visible_rows(target)
    return [
        r for r in rows
        if not str(r["written_by"] or "").startswith(_AWARENESS_PREFIX)
    ]


def _backup(path: Path) -> Optional[Path]:
    """Timestamped ``<file>.bak.<ts>`` copy; None when nothing to back up."""
    if not path.exists():
        return None
    bak = path.with_suffix(path.suffix + f".bak.{int(time.time())}")
    bak.write_bytes(path.read_bytes())
    return bak


def export_legacy(
    store,
    out_dir: Optional[Path | str] = None,
    targets: Sequence[str] = ("memory", "user"),
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Export the canonical store's visible rows to §-delimited legacy files.

    ``store`` must be a loaded MemoryStoreV2 (duck-typed: needs
    ``_visible_rows`` and ``_db_path``). Returns the verification report::

        {
          "schema_version": 1,
          "exported_at": "<ISO-8601 UTC>",
          "dry_run": false,
          "out_dir": "<abs path>",
          "targets": {
            "memory": {"path": ..., "expected": N, "written": N,
                       "ok": true, "backup": "<path> | null"},
            ...
          },
          "memory_db": {"path": ..., "exists": true,
                        "sha256_before": ..., "sha256_after": ...,
                        "unchanged": true},
          "audit_file": "<path> | null",
        }

    In dry-run mode ``written`` is 0 and ``ok`` is null (nothing on disk to
    verify), ``audit_file`` is null, and no file, backup or directory is
    created. memory.db is never opened for writing in either mode.
    """
    if not hasattr(store, "_visible_rows"):
        raise TypeError(
            "export_legacy requires the MemoryStoreV2 canonical store "
            f"(got {type(store).__name__} without _visible_rows)"
        )
    if out_dir is not None:
        out_dir = Path(out_dir)
    else:
        from tools import memory_tool

        out_dir = memory_tool.get_memory_dir()
    unknown = [t for t in targets if t not in EXPORT_TARGETS]
    if unknown:
        raise ValueError(f"Unknown export targets: {', '.join(unknown)}")

    db_path = getattr(store, "_db_path", None)
    db_path = Path(db_path) if db_path else None
    sha_before = _sha256(db_path) if db_path else None

    report: Dict[str, Any] = {
        "schema_version": EXPORT_REPORT_VERSION,
        "exported_at": _iso_now(),
        "dry_run": bool(dry_run),
        "out_dir": str(out_dir),
        "targets": {},
        "memory_db": {
            "path": str(db_path) if db_path else None,
            "exists": bool(db_path and db_path.exists()),
            "sha256_before": sha_before,
            "sha256_after": None,
            "unchanged": None,
        },
        "audit_file": None,
    }

    if dry_run:
        for target in targets:
            rows = _export_rows(store, target)
            report["targets"][target] = {
                "path": str(out_dir / EXPORT_TARGETS[target]),
                "expected": len(rows),
                "written": 0,
                "ok": None,
                "backup": None,
            }
        report["memory_db"]["sha256_after"] = sha_before
        report["memory_db"]["unchanged"] = True
        return report

    out_dir.mkdir(parents=True, exist_ok=True)
    for target in targets:
        rows = _export_rows(store, target)
        contents = [r["content"] for r in rows]
        path = out_dir / EXPORT_TARGETS[target]
        backup = _backup(path)
        atomic_write_text(path, ENTRY_DELIMITER.join(contents), tmp_prefix=".mem_")
        # Count verification: re-parse exactly what the flat store will read.
        written = len(MemoryStore._parse_entries(
            path.read_text(encoding="utf-8")))
        report["targets"][target] = {
            "path": str(path),
            "expected": len(contents),
            "written": written,
            "ok": written == len(contents),
            "backup": str(backup) if backup else None,
        }

    sha_after = _sha256(db_path) if db_path else None
    report["memory_db"]["sha256_after"] = sha_after
    report["memory_db"]["unchanged"] = sha_before == sha_after

    marker = out_dir / _REPORT_NAME
    report["audit_file"] = str(marker)
    atomic_write_text(
        marker,
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        tmp_prefix=".mem_",
    )
    return report
