"""Canonical transaction for an explicitly user-approved visible-card mutation."""


def mutate_visible_entry(store, target, selector, replacement):
    """The selector runs against current visible contents INSIDE the transaction.

    Journey already obtained user consent (editor submit/delete confirmation).
    No autonomous memory-tool proposal or second approval prompt is introduced.
    SQLite char limits govern snapshots, not evidence retention.
    """
    from agent.memory_store_v2 import _now
    from tools.memory_tool_store import _error

    if target not in ("memory", "user"):
        return _error(f"Unknown target '{target}'.")
    if not store.target_enabled(target):
        return _error(f"Memory target '{target}' is disabled.")
    if replacement is not None:
        replacement = replacement.strip()
        if not replacement:
            return _error("Content cannot be empty. Use delete to remove it.")
        if error := store._scan_for_add(replacement):
            return _error(error)

    def _apply(conn):
        rows = conn.execute(
            "SELECT id, content FROM memories WHERE target=? AND status IN ('active','pinned')"
            " ORDER BY (status='pinned') DESC, importance DESC, datetime(created_at) ASC", (target,)
        ).fetchall()
        memory_count = conn.execute(
            "SELECT count(*) FROM memories WHERE target='memory' AND status IN ('active','pinned')"
        ).fetchone()[0]
        index = selector([r["content"] for r in rows], memory_count)
        if index is None or not 0 <= index < len(rows):
            return _error("memory node id is stale — refresh the graph")
        ident = rows[index]["id"]
        if replacement is None:
            conn.execute("DELETE FROM memories WHERE id=?", (ident,))
        else:
            conn.execute("UPDATE memories SET content=?, updated_at=? WHERE id=?", (replacement, _now(), ident))
        return {"success": True}

    result = store._execute_write(_apply)
    if result.get("success"):
        store._rewrite_projection(target)
    return result
