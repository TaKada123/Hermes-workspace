#!/usr/bin/env python3
"""Memory Tool - persistent curated memory (MEMORY.md = agent notes, USER.md = user
profile). Both enter the system prompt as a FROZEN snapshot at session start;
mid-session writes hit disk but never change the prompt (prefix cache intact).
Single `memory` tool: add/replace/remove or a batch `operations` list."""

import copy
import json
import logging
from contextvars import ContextVar
from pathlib import Path
from hermes_constants import get_hermes_home
from typing import Dict, Any, List, Optional, Tuple

from utils import is_truthy_value
from tools.registry import no_cache_check_fn

# fcntl is Unix-only; Windows uses msvcrt. MemoryStore reads both lazily from
# this module (tests patch ``memory_tool.fcntl``).
msvcrt = None
try:
    import fcntl
except ImportError:
    fcntl = None
    try:
        import msvcrt  # noqa: F401
    except ImportError:
        pass

logger = logging.getLogger(__name__)

# One tool-definition pass must use ONE config decision for availability and the
# dynamic target schema: the check_fn result flows to the immediately following
# dynamic_schema_overrides call; ContextVar isolates concurrent profile builds.
_memory_surface_flags: ContextVar[Optional[Tuple[bool, bool]]] = ContextVar("memory_surface_flags", default=None)


def get_memory_dir() -> Path:
    """Profile-scoped memories dir, resolved per call (HERMES_HOME may switch after import)."""
    return get_hermes_home() / "memories"


from tools.memory_tool_store import (  # noqa: E402,F401  (re-exports)
    ENTRY_DELIMITER, MEMORY_BLOCK_HEADERS, MemoryStore, _scan_memory_content)


def resolve_memory_backend(config: Optional[Dict[str, Any]] = None) -> str:
    """Resolve ``memory.backend`` to ``'file'`` or ``'sqlite_v2'``.

    The values are matched EXACTLY (``backend == \"sqlite_v2\"``): any unknown,
    malformed or missing value resolves to the legacy ``'file'`` backend, so a
    bad flag can never activate the v2 store or break startup. This is the ONE
    resolver both ``agent_init`` and ``load_on_disk_store`` must use, so the
    live agent and agent-less contexts (gateway, Desktop, ``/memory`` CLI)
    cannot diverge — the same invariant ``get_builtin_memory_store_flags``
    documents for the enable flags.
    """
    section = get_builtin_memory_config(config)
    return "sqlite_v2" if section.get("backend") == "sqlite_v2" else "file"


def load_on_disk_store() -> "MemoryStore":
    """Fresh on-disk MemoryStore with configured limits/flags for contexts with no live
    agent (gateway, Desktop, ``/memory``) so approvals enforce the SAME caps as
    ``agent_init``. Backend follows ``memory.backend`` (default legacy ``file``);
    falls back to defaults if config can't load; never raises."""
    try:
        from hermes_cli.config import load_config
        config = load_config() or {}
        mem_cfg = get_builtin_memory_config(config)
        memory_enabled, user_profile_enabled = get_builtin_memory_store_flags(config)
        store_kwargs = dict(memory_enabled=memory_enabled, user_profile_enabled=user_profile_enabled)
        limits = (int(mem_cfg.get("memory_char_limit", 2200)), int(mem_cfg.get("user_char_limit", 1375)))
        if resolve_memory_backend(config) == "sqlite_v2":
            from agent.memory_store_v2 import MemoryStoreV2
            store = MemoryStoreV2(*limits, **store_kwargs)
        else:
            store = MemoryStore(*limits, **store_kwargs)
    except Exception:
        store = MemoryStore()  # config optional — fall back to defaults rather than break /memory
    store.load_from_disk()
    return store


def _pin_matched_entries(store: "MemoryStore", payload: Dict[str, Any]) -> Optional[str]:
    """Record on each staged replace/remove/deprecate the FULL entry its old_text
    selects now. Approval then applies to exactly the entry the approver reviewed
    and refuses if it changed: re-running the old_text search at approve time could
    hit a newer entry that still contains it. ``supersede`` is pinned by its
    ``old_id`` (an exact UUID needs no text resolution). Returns the JSON error when
    the search fails now, as the direct write would."""
    target = payload.get("target", "memory")
    if payload.get("action") == "batch":
        result = store.resolve_batch_entries(target, payload["operations"])
        if result.get("success"):
            payload["operations"] = [op if entry is None else {**op, "matched_entry": entry}
                                     for op, entry in zip(payload["operations"], result["matched_entries"])]
    elif payload.get("action") in _PIN_BY_TEXT_ACTIONS and not (
            payload.get("action") == "deprecate" and payload.get("old_id")):
        result = store.resolve_entry(target, payload.get("old_text") or "", payload["action"])
        if result.get("success"):
            payload["matched_entry"] = result["matched_entry"]
    else:
        return None
    return None if result.get("success") else json.dumps(result, ensure_ascii=False)


def _gate_or_stage(store: "MemoryStore", summary: str, detail: str, payload: Dict[str, Any]) -> Optional[str]:
    """JSON tool-result string when the write must NOT proceed (blocked or staged
    for approval), None to proceed. Fails open if the gate module can't load."""
    try:
        from tools import write_approval as wa
    except Exception:
        return None
    decision = wa.evaluate_gate(wa.MEMORY, inline_summary=summary, inline_detail=detail)
    if decision.allow:
        return None
    if decision.blocked:
        return tool_error(decision.message, success=False)
    if (unmatched := _pin_matched_entries(store, payload)) is not None:
        return unmatched
    record = wa.stage_write(wa.MEMORY, payload, summary=f"{summary}: {detail[:120]}", origin=wa.current_origin())
    return json.dumps({"success": True, "staged": True, "pending_id": record["id"], "message": decision.message},
                      ensure_ascii=False)


# action -> (store call, gate (summary, detail) text) for the live tool path and staged replay.
_STORE_ACTIONS = {
    "add": (lambda store, target, content, old_text, entry=None: store.add(target, content),
            lambda label, content, old_text: (f"add to {label}", content or "")),
    "replace": (lambda store, target, content, old_text, entry=None: store.replace(target, old_text, content, entry),
                lambda label, content, old_text: (f"replace in {label}",
                                                  f"entry matching: {old_text}\nwhole entry becomes: {content}")),
    "remove": (lambda store, target, content, old_text, entry=None: store.remove(target, old_text, entry),
               lambda label, content, old_text: (f"remove from {label}", old_text or ""))}


def _store_is_v2(store: "MemoryStore") -> bool:
    """Duck-type switch: the typed action surface exists only on MemoryStoreV2."""
    return hasattr(store, "supersede") and hasattr(store, "deprecate") and hasattr(store, "recall")


def _v2_apply_single_action(
    store: "MemoryStore",
    action: str,
    target: str,
    content: str,
    old_text: str,
    *,
    old_id: Optional[str] = None,
    superseded_by_id: Optional[str] = None,
    reason: Optional[str] = None,
    entry_type: Optional[str] = None,
    importance: Optional[float] = None,
    written_by: Optional[str] = None,
    matched_entry: Optional[str] = None,
) -> Dict[str, Any]:
    """The v2 single-op store dispatch — ONE implementation shared by the
    live tool path and the staged-write replay, so the two cannot drift.

    Forwards only the kwargs each action accepts (``deprecate`` has no
    ``entry_type``/``importance``; ``add``/``replace`` have no ``reason``).
    Raises ``KeyError`` for a non-v2 action (callers gate on action first).
    """
    if action == "supersede":
        return store.supersede(
            target, old_id=old_id, content=content, entry_type=entry_type,
            importance=importance, reason=reason or "", written_by=written_by,
        )
    if action == "deprecate":
        return store.deprecate(
            target, old_text=old_text or "", reason=reason or "",
            old_id=old_id, superseded_by_id=superseded_by_id,
            matched_entry=matched_entry,
        )
    if action == "add":
        return store.add(
            target, content, entry_type=entry_type,
            importance=importance, written_by=written_by,
        )
    if action == "replace":
        return store.replace(
            target, old_text, content, matched_entry,
            entry_type=entry_type, importance=importance,
        )
    raise KeyError(action)


_TYPED_MEMORY_REQUIRES_V2 = "Typed memory requires the v2 store (set memory.backend: sqlite_v2 in config)."


def _write_gate_text(action: str, label: str, payload: Dict[str, Any]) -> Tuple[str, str]:
    """(summary, detail) for the write-approval inline prompt / staged record."""
    content = payload.get("content") or ""
    old_text = payload.get("old_text") or ""
    old_id = payload.get("old_id") or ""
    if action == "add":
        return f"add to {label}", content
    if action == "replace":
        return f"replace in {label}", f"entry matching: {old_text}\nwhole entry becomes: {content}"
    if action == "remove":
        return f"remove from {label}", old_text
    if action == "supersede":
        return f"supersede in {label}", f"old entry id: {old_id}\nnew entry becomes: {content}"
    if action == "deprecate":
        return f"deprecate in {label}", f"entry: {old_id or old_text}"
    raise KeyError(action)


def _batch_op_line(op: Dict[str, Any]) -> str:
    op = op or {}
    act, content, old = op.get("action", "?"), op.get("content") or op.get("new_text") or "", op.get("old_text", "")
    old_id = op.get("old_id") or ""
    if act == "remove":
        return f"- remove: {old}"
    if act == "deprecate":
        return f"- deprecate: {old_id or old}"
    if act == "supersede":
        return f"- supersede entry {old_id} -> new entry: {content}"
    # Whole-entry contract (#117952): the approver must not read this as a span patch.
    return (f"- replace entry matching '{old}' -> whole entry becomes: {content}" if act == "replace"
            else f"- {act}: {content}")


def _apply_write_gate(store: "MemoryStore", action: str, target: str, content: Optional[str],
                      old_text: Optional[str], operations: Optional[List[Dict[str, Any]]] = None,
                      **extra: Any) -> Optional[str]:
    """Gate one mutating op, or (``operations`` set) a whole batch as a single unit.
    ``extra`` carries the v2 fields (old_id, superseded_by_id, reason, entry_type,
    importance, written_by) so a staged record replays the FULL write."""
    label = "user profile" if target == "user" else "memory"
    if operations is not None:
        return _gate_or_stage(store, f"apply {len(operations)} op(s) to {label}",
                              "\n".join(_batch_op_line(op) for op in operations),
                              {"action": "batch", "target": target, "operations": operations})
    payload = {"action": action, "target": target, "content": content, "old_text": old_text}
    for key in ("old_id", "superseded_by_id", "reason", "entry_type", "importance", "written_by"):
        if extra.get(key) is not None:
            payload[key] = extra[key]
    summary, detail = _write_gate_text(action, label, payload)
    return _gate_or_stage(store, summary, detail, payload)


def _validate_single_op(store, action, target, content, old_text,
                        old_id: Optional[str] = None, query: Optional[str] = None) -> Optional[str]:
    """Validate BEFORE the gate so an invalid write is rejected now, not at approve time.
    Missing ``old_text`` is recoverable (it can't be schema-required — needs a combinator
    the Codex backend rejects): return the inventory plus a retry instruction."""
    if action == "add" and not content:
        return tool_error("Content is required for 'add' action.", success=False)
    if action in ("replace", "remove") and not old_text:
        replace_hint = (" For 'replace', content is the COMPLETE new entry -- the whole "
                        "matched entry is overwritten, not just the old_text span."
                        if action == "replace" else "")
        return json.dumps({
            "success": False,
            "error": (f"'{action}' needs old_text -- a short unique substring of the entry "
                      f"to {action}. None was provided. Reissue the {action} with old_text "
                      f"set to part of one of the current_entries below.{replace_hint}"),
            "current_entries": store._entries_for(target), "usage": store._usage(target)}, ensure_ascii=False)
    if action == "replace" and not content:
        return tool_error("content is required for 'replace' action.", success=False)
    if action == "supersede":
        if not old_id:
            return tool_error(
                "old_id is required for 'supersede' (the id of the entry being replaced; "
                "read first if unknown).", success=False)
        if not content:
            return tool_error("content (the new decision) is required for 'supersede'.", success=False)
    if action == "deprecate" and not old_id and not old_text:
        return tool_error("old_id or old_text is required for 'deprecate' action.", success=False)
    if action == "read" and not query and not content:
        return tool_error("query is required for 'read' action.", success=False)
    return None


# Destructive actions for the background-review gate (add stays free).
_BG_DELETE_ACTIONS = ("replace", "remove", "deprecate", "supersede")
# Destructive actions whose staged payload is pinned by resolved entry TEXT
# (supersede is pinned by its exact old_id instead).
_PIN_BY_TEXT_ACTIONS = ("replace", "remove", "deprecate")


def destructive_ops(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The destructive ops of a staged memory payload, single-op or batch shape:
    replace/remove plus the v2 revocations deprecate/supersede."""
    ops = (payload.get("operations") or []) if payload.get("action") == "batch" else [payload]
    return [op for op in ops if (op or {}).get("action") in _BG_DELETE_ACTIONS]


def _background_delete_gate(store, action, operations, target="memory", content=None,
                            old_text=None, **extra) -> Optional[str]:
    """Fail-closed operation gate for unattended background-review forks (#105921): ``add``
    stays available (it is all any review prompt asks for), while destructive ops —
    ``replace``/``remove`` and the v2 revocations ``deprecate``/``supersede`` — single or
    inside a batch, are never applied unattended. The op is staged in the pending store
    instead of merely denied: the fork's own review summary is never published back, so
    a plain denial would drop the consolidation request with no surfacing path at all. A
    staging failure fails closed to a plain denial."""
    from tools.skill_provenance import is_unattended_review

    if not is_unattended_review():
        return None
    payload = ({"action": "batch", "target": target, "operations": operations}
               if operations is not None else
               {"action": action, "target": target, "content": content, "old_text": old_text})
    for key in ("old_id", "superseded_by_id", "reason", "entry_type", "importance", "written_by"):
        if extra.get(key) is not None:
            payload[key] = extra[key]
    if not destructive_ops(payload):
        return None
    detail = ("; ".join(_batch_op_line(op) for op in operations) if operations is not None
              else _batch_op_line(payload))
    try:
        if (unmatched := _pin_matched_entries(store, payload)) is not None:
            return unmatched
        from tools import write_approval as wa
        record = wa.stage_write(
            wa.MEMORY, payload,
            summary=(f"background review consolidation ({'batch' if operations is not None else action} "
                     f"on {target}): {detail}")[:200],
            origin=wa.current_origin())
        return json.dumps({
            "success": True, "staged": True, "proposal_staged": True, "pending_id": record["id"],
            "message": ("Background review may not delete memory entries unattended. The proposed "
                        f"{'batch' if operations is not None else action} was staged for your approval — "
                        "review it with /memory pending (approve to apply, discard to drop)."),
        }, ensure_ascii=False)
    except Exception:
        logger.warning("Failed to stage background-review consolidation; denying", exc_info=True)
        return tool_error(
            "Background review may not delete memory entries ('replace'/'remove'/'deprecate'/'supersede', "
            "including in a batch); 'add' is still available.", success=False)


def memory_tool(action: str = None, target: str = "memory", content: str = None, old_text: str = None,
                new_text: str = None, operations: Optional[List[Dict[str, Any]]] = None,
                store: Optional[MemoryStore] = None, entry_type: str = None, importance: float = None,
                query: str = None, reason: str = None, written_by: str = None, old_id: str = None,
                superseded_by_id: str = None) -> str:
    """Tool entry point; returns a JSON string. Single op (action + content/old_text)
    or batch (``operations``, atomic against the final budget). ``new_text``
    aliases ``content`` -- for 'replace' both mean the COMPLETE new entry (the
    whole matched entry is overwritten; old_text only locates it).

    Typed actions (supersede/deprecate/read) and the type/importance params
    require the v2 store; on the legacy flat-file store they degrade with a
    clear error instead of silently misbehaving."""
    if store is None:
        return tool_error("Memory is not available. It may be disabled in config or this environment.", success=False)
    outcome, result = _memory_tool(action, target, content, old_text, new_text, operations, store,
                                   entry_type=entry_type, importance=importance, query=query,
                                   reason=reason, written_by=written_by, old_id=old_id,
                                   superseded_by_id=superseded_by_id)
    from hermes_cli.observability.shared_metrics_loop import record_builtin_memory_call
    record_builtin_memory_call(action, operations, outcome=outcome)
    return result


def _applied(result: Dict[str, Any]) -> Tuple[str, str]:
    return ("success" if result.get("success") else "failed"), json.dumps(result, ensure_ascii=False)


def _memory_tool(action, target, content, old_text, new_text, operations, store,
                 entry_type=None, importance=None, query=None, reason=None,
                 written_by=None, old_id=None, superseded_by_id=None) -> Tuple[str, str]:
    """``(outcome, result_json)``: ``rejected`` when refused or held before touching the store."""
    if content is None and new_text is not None:
        content = new_text
    # Strict providers send JSON null for optional fields; treat as omitted.
    target = "memory" if target is None else target
    target_error = _memory_target_error(store, target)
    if target_error is not None:
        return "rejected", json.dumps(target_error)
    if operations:
        if not isinstance(operations, list):
            return "rejected", tool_error("operations must be a list of {action, content?, old_text?} objects.", success=False)
        denied = _background_delete_gate(store, action, operations, target)
        if denied is not None:
            return "rejected", denied
        # Approval gate: stages (background/gateway) or prompts inline (CLI); off by default.
        gate_result = _apply_write_gate(store, "batch", target, None, None, operations)
        if gate_result is not None:
            return "rejected", gate_result
        return _applied(store.apply_batch(target, operations))
    # Reject calls that provide neither action (single-op) nor operations
    # (batch).  Without this guard the dispatch falls through to the generic
    # "Unknown action 'None'" error, which gives the model no signal about
    # *why* the call was malformed and can trigger repeated retries. (#64291)
    if not action and not operations:
        return "rejected", tool_error(
            "Missing required parameter: provide 'action' (add/replace/remove/supersede/deprecate/read) "
            "or 'operations' (batch list). Got neither.",
            success=False,
        )
    is_v2 = _store_is_v2(store)
    if action == "read":
        if not is_v2:
            return "rejected", tool_error(_TYPED_MEMORY_REQUIRES_V2, success=False)
        search_query = query or content or old_text
        if not search_query:
            return "rejected", tool_error("query is required for 'read' action.", success=False)
        return _applied(store.recall(search_query, target=target))
    if action in ("supersede", "deprecate"):
        if not is_v2:
            return "rejected", tool_error(_TYPED_MEMORY_REQUIRES_V2, success=False)
        invalid = (_validate_single_op(store, action, target, content, old_text, old_id, query)
                   or _background_delete_gate(store, action, None, target, content, old_text,
                                              old_id=old_id, superseded_by_id=superseded_by_id,
                                              reason=reason)
                   or _apply_write_gate(store, action, target, content, old_text,
                                        old_id=old_id, superseded_by_id=superseded_by_id,
                                        reason=reason))
        if invalid is not None:
            return "rejected", invalid
        return _applied(_v2_apply_single_action(
            store, action, target, content or "", old_text,
            old_id=old_id, superseded_by_id=superseded_by_id, reason=reason,
            entry_type=entry_type, importance=importance, written_by=written_by,
        ))
    if action in _STORE_ACTIONS:
        if action in ("add", "replace") and not is_v2 and (entry_type or importance is not None):
            return "rejected", tool_error(_TYPED_MEMORY_REQUIRES_V2, success=False)
        invalid = (_validate_single_op(store, action, target, content, old_text)
                   or _background_delete_gate(store, action, None, target, content, old_text)
                   or _apply_write_gate(store, action, target, content, old_text,
                                        entry_type=entry_type, importance=importance,
                                        written_by=written_by))
        if invalid is not None:
            return "rejected", invalid
        if is_v2 and action in ("add", "replace"):
            return _applied(_v2_apply_single_action(
                store, action, target, content or "", old_text,
                entry_type=entry_type, importance=importance, written_by=written_by,
            ))
        return _applied(_STORE_ACTIONS[action][0](store, target, content, old_text))
    return "rejected", tool_error(
        f"Unknown action '{action}'. Use: add, replace, remove, supersede, deprecate, read",
        success=False)


def get_builtin_memory_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Normalized ``memory`` config section ({} when missing/malformed → flags default to
    enabled). ``agent_init`` reads the same section so availability and store cannot diverge."""
    if config is None:
        try:
            from hermes_cli.config import load_config_readonly
            config = load_config_readonly()
        except Exception:
            logger.debug("Could not read memory config for availability", exc_info=True)
            return {}
    section = config.get("memory") if isinstance(config, dict) else None
    return section if isinstance(section, dict) else {}


def get_builtin_memory_store_flags(config: Optional[Dict[str, Any]] = None) -> Tuple[bool, bool]:
    """Return ``(memory_enabled, user_profile_enabled)`` from resolved config."""
    section = get_builtin_memory_config(config)
    return tuple(is_truthy_value(section.get(k), default=True) for k in ("memory_enabled", "user_profile_enabled"))


@no_cache_check_fn
def check_memory_requirements() -> bool:
    """Snapshot store flags and report whether the built-in tool is available."""
    _memory_surface_flags.set(None)
    flags = get_builtin_memory_store_flags()
    _memory_surface_flags.set(flags)
    return flags[0] or flags[1]


def _memory_target_error(store: "MemoryStore", target: str) -> Optional[Dict[str, Any]]:
    """Return a shared validation error for an invalid or disabled target."""
    if target not in {"memory", "user"}:
        from tools.registry import _bound_error_text
        return {"success": False,
                "error": _bound_error_text(f"Invalid memory target '{target}'. Use 'memory' or 'user'.")}
    if store.target_enabled(target):
        return None
    label = "USER.md" if target == "user" else "MEMORY.md"
    return {"success": False, "error": f"Built-in {label} writes are disabled in memory config.", "target": target}


def _destructive_pin_error(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Error when a destructive staged op lacks the pin its approve-time replay
    requires — ``matched_entry`` for text-addressed ops, ``old_id`` for the
    id-addressed v2 revocations — or None when the payload is verifiable."""
    for op in destructive_ops(payload):
        act = op.get("action")
        if act == "supersede":
            if not op.get("old_id"):
                return {"success": False, "error": (
                    "This supersede pending write predates id pinning and cannot be "
                    "verified; nothing was applied. Reject it and recreate the change.")}
            continue
        if act == "deprecate":
            if op.get("old_id") or op.get("matched_entry"):
                continue
            return {"success": False, "error": (
                "This deprecate pending write predates entry pinning and cannot be "
                "verified; nothing was applied. Reject it and recreate the change.")}
        if not op.get("matched_entry"):
            return {"success": False, "error": (
                "This destructive pending write predates entry pinning and cannot be "
                "verified; nothing was applied. Reject it and recreate the change.")}
    return None


def apply_memory_pending(payload: Dict[str, Any], store: "MemoryStore") -> Dict[str, Any]:
    """Replay a staged write against the store, bypassing the gate (/memory approve). A
    replace/remove/deprecate applies to exactly its pinned ``matched_entry`` (or ``old_id``)
    or is refused; a record staged before pinning has no verifiable target, so it is refused
    rather than replayed by old_text (which could hit a newer entry the approver never saw)."""
    action, target = payload.get("action"), payload.get("target", "memory")
    target_error = _memory_target_error(store, target)
    if target_error is not None:
        return target_error
    if pin_error := _destructive_pin_error(payload):
        return pin_error
    if action == "batch":
        return store.apply_batch(target, payload.get("operations") or [])
    is_v2 = _store_is_v2(store)
    if action in ("supersede", "deprecate"):
        if not is_v2:
            return {"success": False, "error": _TYPED_MEMORY_REQUIRES_V2}
        return _v2_apply_single_action(
            store, action, target,
            payload.get("content") or "", payload.get("old_text") or "",
            old_id=payload.get("old_id"), superseded_by_id=payload.get("superseded_by_id"),
            reason=payload.get("reason"), entry_type=payload.get("entry_type"),
            importance=payload.get("importance"), written_by=payload.get("written_by"),
            matched_entry=payload.get("matched_entry"),
        )
    if action in ("add", "replace") and is_v2:
        return _v2_apply_single_action(
            store, action, target,
            payload.get("content") or "", payload.get("old_text") or "",
            matched_entry=payload.get("matched_entry"),
            entry_type=payload.get("entry_type"),
            importance=payload.get("importance"),
            written_by=payload.get("written_by"),
        )
    if action not in _STORE_ACTIONS:
        return {"success": False, "error": f"Unknown staged action '{action}'."}
    return _STORE_ACTIONS[action][0](store, target, payload.get("content") or "", payload.get("old_text") or "",
                                     payload.get("matched_entry"))


MEMORY_SCHEMA = {
    "name": "memory",
    "description": (
        "Save durable facts to persistent memory that survive across sessions. Memory is "
        "injected into every future turn, so keep entries compact and high-signal.\n\n"
        "HOW: make ALL your changes in ONE call via an 'operations' array (each item: "
        "{action, content?, old_text?}). The batch applies atomically and the char limit is "
        "checked only on the FINAL result — so a single call can remove/replace stale entries "
        "to free room AND add new ones, even when an add alone would overflow. The response "
        "reports current/limit chars and confirms completion; one batch call finishes the "
        "update, so don't repeat it. Use the bare action/content/old_text fields only for a "
        "single lone change.\n\n"
        "WHEN: only for facts that apply to EVERY session regardless of task: who the user "
        "is, stable environment facts, standing conventions with no task home. Anything "
        "learned while doing a task (procedures, pitfalls, and the user's preferences and "
        "corrections for that kind of work) belongs in the task's skill via skill_manage, "
        "where it loads only when relevant; memory is injected into every turn and must "
        "stay small.\n\n"
        "IF FULL: an add is rejected with the current entries shown. Reissue as ONE batch that "
        "removes or shortens enough stale entries and adds the new one together.\n\n"
        "TARGETS: 'user' = who the user is (name, role, preferences, style). 'memory' = your "
        "notes (environment, conventions, tool quirks, lessons).\n\n"
        "SKIP: trivial/obvious info, easily re-discovered facts, raw data dumps, task progress, "
        "completed-work logs, temporary TODO state (use session_search for those). Reusable "
        "procedures belong in a skill, not memory. "
        "TYPED ACTIONS (v2 store only — on the legacy store they return a clear error): "
        "supersede (atomic decision change: old_id + content — adds the new entry, deprecates "
        "the old one and writes the provenance link in one operation), "
        "deprecate (retire an entry — old_id or old_text; optional superseded_by_id links an "
        "already-added successor), "
        "read (search memory by query before proposing ideas or making decisions). With the "
        "v2 store, entries are never deleted to make room: the char limit bounds the PROMPT "
        "snapshot only, and overflow entries stay in the database and remain searchable via "
        "read."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "replace", "remove", "supersede", "deprecate", "read"],
                "description": "The action to perform (single-op shape). Omit when using 'operations'."
            },
            "target": {
                "type": "string",
                "enum": ["memory", "user"],
                "description": "Which memory store: 'memory' for personal notes, 'user' for user profile."
            },
            "content": {
                "type": "string",
                "description": "The entry content. Required for 'add' and 'replace'. For 'replace' it is the COMPLETE new entry text: the whole matched entry is overwritten, so include everything you want to keep. Alias: 'new_text' is also accepted (same full-entry meaning)."
            },
            "old_text": {
                "type": "string",
                "description": "REQUIRED for 'replace' and 'remove' (single-op shape): a short unique substring IDENTIFYING the existing entry to modify -- it locates the entry, it is not spliced out. Omit only for 'add'. Also accepted by 'deprecate' as an alternative to old_id."
            },
            "new_text": {
                "type": "string",
                "description": "Alias for 'content' (single-op shape): the COMPLETE new entry for 'replace', not a patch of old_text. If both are set, 'content' wins."
            },
            "old_id": {
                "type": "string",
                "description": "Entry id for 'supersede' (the entry being replaced) and 'deprecate'. Accepts the full UUID or an unambiguous 8+ char prefix — the short form shown in read results works directly."
            },
            "superseded_by_id": {
                "type": "string",
                "description": "Id of the successor entry for 'deprecate' — links the pair when the new entry was already added separately. Full UUID or unambiguous 8+ char prefix. Invalid, ambiguous or deprecated successor ids fail the whole call without changing anything."
            },
            "type": {
                "type": "string",
                "enum": ["fact", "decision", "constraint", "pattern", "preference"],
                "description": "Entry type for 'add' (v2 store only). decision = a choice the user made (include the reason); constraint = a rule/limit to respect; preference = user taste; pattern = recurring behavior; fact = everything else."
            },
            "importance": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Intrinsic long-term value 0..1 (v2 store only). Omit it and a type default applies (decision 0.85, constraint 0.9, preference 0.6, fact/pattern 0.5); an explicit value is stored as-is, never rewritten. Prompt eviction never changes importance."
            },
            "query": {
                "type": "string",
                "description": "Search query for the 'read' action."
            },
            "reason": {
                "type": "string",
                "description": "Why the entry changed (for 'supersede' and 'deprecate') — human-readable, becomes the deprecate_reason in the audit trail. Linking is done by ids, not by reason text."
            },
            "operations": {
                "type": "array",
                "description": (
                    "Batch shape: a list of operations applied atomically in one call "
                    "against the final char budget. Preferred when making multiple changes "
                    "or consolidating to make room. Each item is {action, content?, old_text?}."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["add", "replace", "remove"]},
                        "content": {"type": "string", "description": "Entry content for add/replace. For replace, the COMPLETE new entry (whole entry is overwritten). Alias: 'new_text'."},
                        "new_text": {"type": "string", "description": "Alias for 'content' in a batch op."},
                        "old_text": {"type": "string", "description": "Substring identifying the entry for replace/remove."},
                    },
                    "required": ["action"],
                },
            },
        },
        "required": ["target"],
    },
}


# Schema text when only one built-in store is enabled: (target description, TARGETS replacement).
_SINGLE_TARGET_TEXT = {
    ("memory",): ("The enabled built-in store: 'memory' for personal notes.",
                  "TARGET: only 'memory' is enabled for personal notes (environment, conventions, "
                  "tool quirks, lessons)."),
    ("user",): ("The enabled built-in store: 'user' for user profile.",
                "TARGET: only 'user' is enabled for user profile facts (name, role, preferences, style).")}


def _build_memory_schema_overrides() -> Dict[str, Any]:
    """Narrow the advertised target surface using the availability snapshot."""
    flags = _memory_surface_flags.get() or get_builtin_memory_store_flags()
    _memory_surface_flags.set(None)
    targets = [t for t, on in zip(("memory", "user"), flags) if on]
    parameters = copy.deepcopy(MEMORY_SCHEMA["parameters"])
    target_schema, description = parameters["properties"]["target"], MEMORY_SCHEMA["description"]
    target_schema["enum"] = targets
    if narrowed := _SINGLE_TARGET_TEXT.get(tuple(targets)):
        target_schema["description"], replacement = narrowed
        description = description.replace(
            "TARGETS: 'user' = who the user is (name, role, preferences, style). 'memory' = your "
            "notes (environment, conventions, tool quirks, lessons).", replacement)
    return {"description": description, "parameters": parameters}


from tools.registry import registry, tool_error  # noqa: E402  (registration at import time)

registry.register(
    name="memory",
    toolset="memory",
    schema=MEMORY_SCHEMA,
    handler=lambda args, **kw: memory_tool(
        action=args.get("action", ""), target=args.get("target", "memory"), store=kw.get("store"),
        entry_type=args.get("type"), importance=args.get("importance"), query=args.get("query"),
        reason=args.get("reason"), written_by=args.get("written_by"),
        old_id=args.get("old_id"), superseded_by_id=args.get("superseded_by_id"),
        **{k: args.get(k) for k in ("content", "old_text", "new_text", "operations")}),
    check_fn=check_memory_requirements,
    emoji="🧠",
    dynamic_schema_overrides=_build_memory_schema_overrides)
