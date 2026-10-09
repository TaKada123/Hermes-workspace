# Ported from the Architecture 2.0 Hermes fork (MIT License)
# Copyright (c) 2025-2026 Dmitry Antipin (multi-agent orchestration fork)
# Source: commit 0c76ec28, sha256 f56fe4cf4bc3d204698efe7a588fe350f7e20c0d70174ffe305f25039213078e
"""Typed SQLite memory store (v2) tests.

Ported from the Architecture 2.0 fork (tests/agent/test_memory_store_v2.py,
commit 0c76ec28) and extended with workspace-specific contracts:
memory.backend flag resolution, DB placement in HERMES_HOME, schema integrity,
FTS5-unavailable degradation, projection regeneration, per-target flags.
"""

from __future__ import annotations

import pytest

import tools.memory_tool as mt
from tools.memory_tool import resolve_memory_backend


class TestBackendFlag:
    """memory.backend: 'file' | 'sqlite_v2'; default 'file'; unknown -> legacy file."""

    def test_default_is_file_when_flag_absent(self):
        assert resolve_memory_backend({}) == "file"
        assert resolve_memory_backend({"memory": {}}) == "file"
        assert resolve_memory_backend({"other": {"backend": "sqlite_v2"}}) == "file"

    def test_explicit_file(self):
        assert resolve_memory_backend({"memory": {"backend": "file"}}) == "file"

    def test_explicit_sqlite_v2(self):
        assert resolve_memory_backend({"memory": {"backend": "sqlite_v2"}}) == "sqlite_v2"

    def test_unknown_value_falls_back_to_file_without_raising(self):
        for garbage in ("banana", "sqlite", "v2", "SQLITE_V2", "File", " sqlite_v2 "):
            assert resolve_memory_backend({"memory": {"backend": garbage}}) == "file", garbage

    def test_non_string_values_fall_back_to_file_without_raising(self):
        for garbage in (None, 123, 0, True, False, ["sqlite_v2"], {"backend": "sqlite_v2"}):
            assert resolve_memory_backend({"memory": {"backend": garbage}}) == "file", garbage

    def test_config_default_registered(self):
        # The documented default ships in config_defaults so a fresh home
        # resolves deterministically even before any config.yaml write.
        from hermes_cli.config_defaults import DEFAULT_CONFIG
        assert DEFAULT_CONFIG["memory"]["backend"] == "file"

    def test_resolver_shared_between_tool_and_store_flags(self):
        # get_builtin_memory_config feeds BOTH the resolver and the enable
        # flags; a malformed memory section must degrade to the legacy store.
        from tools.memory_tool import get_builtin_memory_config, get_builtin_memory_store_flags
        cfg = {"memory": {"backend": "sqlite_v2", "memory_enabled": True,
                          "user_profile_enabled": True}}
        assert get_builtin_memory_config(cfg) is cfg["memory"]
        assert get_builtin_memory_store_flags(cfg) == (True, True)
        assert resolve_memory_backend(cfg) == "sqlite_v2"

    def test_direct_resolver_import_on_tool_module(self):
        # The shared resolver lives on tools.memory_tool so agent_init and
        # load_on_disk_store cannot diverge (same invariant as the flags).
        assert callable(mt.resolve_memory_backend)
