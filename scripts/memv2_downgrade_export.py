#!/usr/bin/env python3
"""Downgrade export CLI: dump MemoryStoreV2 rows to §-delimited legacy files.

The cutover operator's tool (ticket #11): verifies the return path from
``memory.backend: sqlite_v2`` back to the legacy flat store without losing
entries created after the cutover. Exports visible rows (status
active/pinned, awareness telemetry excluded) to MEMORY.md/USER.md with
count verification, a timestamped ``.bak`` of any pre-existing file, and an
audit report ``memories/downgrade-export-report.json``. memory.db is never
modified.

Exit codes: 0 — all requested targets verified ok (dry-run always 0);
1 — a count mismatch or export failure; 2 — usage/config error.

No interactive UI: the report JSON on stdout IS the interface.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="memv2_downgrade_export",
        description="Export MemoryStoreV2 visible rows back to legacy §-files "
                    "(count-verified; memory.db untouched).",
    )
    parser.add_argument(
        "--home",
        default=os.environ.get("HERMES_HOME"),
        help="HERMES_HOME whose canonical store to export "
             "(default: $HERMES_HOME; required when the env var is unset)",
    )
    parser.add_argument(
        "--targets",
        default="memory,user",
        help="comma-separated export targets: memory,user (default: memory,user)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report expected counts only; write nothing",
    )
    return parser


def _build_store():
    """MemoryStoreV2 with the configured limits/flags (load_on_disk_store shape)."""
    limits = (2200, 1375)
    memory_enabled = user_profile_enabled = True
    from hermes_cli.config import load_config
    from tools.memory_tool import (
        get_builtin_memory_config,
        get_builtin_memory_store_flags,
    )

    config = load_config() or {}
    mem_cfg = get_builtin_memory_config(config)
    memory_enabled, user_profile_enabled = get_builtin_memory_store_flags(config)
    limits = (
        int(mem_cfg.get("memory_char_limit", 2200)),
        int(mem_cfg.get("user_char_limit", 1375)),
    )
    from agent.memory_store_v2 import MemoryStoreV2

    return MemoryStoreV2(
        *limits,
        memory_enabled=memory_enabled,
        user_profile_enabled=user_profile_enabled,
    )


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if not args.home:
        print("error: --home or HERMES_HOME is required", file=sys.stderr)
        return 2
    # Set the env BEFORE any Hermes import resolves the home (this process is
    # fresh: no ContextVar override, so the env var wins).
    os.environ["HERMES_HOME"] = str(Path(args.home).expanduser())
    targets = tuple(t.strip() for t in args.targets.split(",") if t.strip())
    if not targets:
        print("error: --targets must name at least one of memory,user",
              file=sys.stderr)
        return 2

    from agent.memory_downgrade import export_legacy

    try:
        store = _build_store()
        store.load_from_disk()
        try:
            report = export_legacy(store, targets=targets, dry_run=args.dry_run)
        finally:
            store.close()
    except ValueError as exc:  # unknown targets / bad config
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.dry_run:
        return 0
    return 0 if all(t["ok"] for t in report["targets"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
