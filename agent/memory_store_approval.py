"""Revision identity for destructive approvals (SQLite, never wall-clock time).

Recall counters are not reviewed state. Every write of semantic/provenance fields
gets a fresh token, including A -> B -> A and delete/reinsert with the same UUID.
Triggers also cover canonical maintenance/import writers, not only the tool.
"""


_REVISION_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_entry_revisions (
    id TEXT PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
    revision TEXT NOT NULL
);
INSERT OR IGNORE INTO memory_entry_revisions(id, revision)
    SELECT id, lower(hex(randomblob(16))) FROM memories;
CREATE TRIGGER IF NOT EXISTS memory_revision_insert AFTER INSERT ON memories BEGIN
    INSERT OR REPLACE INTO memory_entry_revisions(id, revision)
    VALUES (new.id, lower(hex(randomblob(16))));
END;
CREATE TRIGGER IF NOT EXISTS memory_revision_update AFTER UPDATE OF
    content, target, type, importance, confidence, status, project, source_session,
    deprecate_reason, written_by, created_at, updated_at ON memories BEGIN
    UPDATE memory_entry_revisions SET revision=lower(hex(randomblob(16))) WHERE id=new.id;
END;
"""


def init_revisions(conn, execute_schema):
    execute_schema(conn, _REVISION_SCHEMA)


def reviewed_entry(conn, ident):
    row = conn.execute(
        "SELECT m.id, m.target, m.content, r.revision FROM memories m"
        " JOIN memory_entry_revisions r ON r.id=m.id WHERE m.id=?", (ident,)
    ).fetchone()
    return dict(row) if row else None


def review_error(conn, expected, ident=None):
    """Must be called under the SAME BEGIN IMMEDIATE as the destructive write."""
    if expected is None:
        return None  # direct, unapproved store operation
    if not isinstance(expected, dict) or not all(expected.get(k) for k in ("id", "target", "content", "revision")):
        return {"success": False, "error": "Missing reviewed entry revision; nothing was applied. Recreate the proposal."}
    if (ident is not None and ident != expected["id"]) or reviewed_entry(conn, expected["id"]) != expected:
        return {"success": False, "error": "Reviewed entry revision is stale; nothing was applied. Refresh and recreate the proposal."}
    return None


def resolve_id_review(store, conn, target, ident):
    from tools.memory_tool_store import _error

    resolved, err = store._resolve_entry_id(conn, target, ident, role="old_id")
    if resolved is None:
        return _error(err)
    return {"success": True, "reviewed_entry": reviewed_entry(conn, resolved)}


def resolve_text_review(store, conn, target, old_text, verb):
    # Error feedback may query the store; the public wrapper emits it after unlocking.
    statuses = ("active", "pinned", "dormant") if verb == "deprecate" else ("active", "pinned", "dormant", "archived")
    row, fail = store._resolve_old_text(conn, target, old_text.strip(), statuses=statuses)
    if fail:
        return fail
    return {"success": True, "matched_entry": row["content"], "reviewed_entry": reviewed_entry(conn, row["id"])}


def resolve_batch_reviews(store, conn, target, ops):
    """Keep initial row identities while dry-running sequential text operations.

    A later op can address a row added/replaced by an earlier op. In that case
    only its original canonical ancestor needs a revision precondition.
    """
    rows = conn.execute(
        "SELECT id, content FROM memories WHERE target=? AND status IN ('active','pinned')"
        " ORDER BY (status='pinned') DESC, importance DESC, datetime(created_at) ASC", (target,)
    ).fetchall()
    working = [r["content"] for r in rows]
    origins = [r["id"] for r in rows]
    pins = {}
    matched = []
    for i, op in enumerate(ops):
        msg, prev, origin = apply_reviewed_batch_step(working, origins, op, i)
        if msg:
            return store._batch_failure(target, msg)
        matched.append(prev)
        if origin:
            pins[origin] = reviewed_entry(conn, origin)
    if rows and not working:
        return store._batch_failure(target, "Refusing to empty memory: keep at least one entry; use single remove() deliberately.")
    return {"success": True, "matched_entries": matched, "reviewed_entries": list(pins.values())}


def apply_reviewed_batch_step(working, origins, op, index):
    """Advance content AND row identity together, even when replace creates duplicates."""
    from tools.memory_tool_store import MemoryStore

    before = list(working)
    act = op.get("action")
    content = (op.get("content") or op.get("new_text") or "").strip()
    msg, prev = MemoryStore._apply_batch_op(
        working, act, content, (op.get("old_text") or "").strip(),
        f"Operation {index + 1} ({act or 'unknown'})", op.get("matched_entry"),
    )
    origin = None
    if not msg:
        if prev is not None:
            selected = before.index(prev)
            origin = origins[selected]
            origins[selected:selected + 1] = [origin] if act == "replace" else []
        elif len(working) > len(before):
            origins.append(None)  # newly added within this very batch
    return msg, prev, origin
