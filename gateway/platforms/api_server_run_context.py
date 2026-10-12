"""Opaque caller operation context bound to one admitted API run."""
from collections.abc import Mapping
import re


def parse_run_context_headers(
    headers: Mapping[str, str],
) -> tuple[str, str | None, tuple[str, str] | None]:
    """Return idempotency key, validated operation context, and optional HTTP error."""
    idempotency_key = headers.get("Idempotency-Key", "").strip()
    if len(idempotency_key) > 255 or any(ord(ch) < 33 or ord(ch) > 126 for ch in idempotency_key):
        return "", None, (
            "invalid_idempotency_key", "Idempotency-Key must be 1-255 visible ASCII characters",
        )
    context_id = headers.get("X-Hermes-Run-Context-Id", "").strip()
    if context_id and not re.fullmatch(r"[0-9a-f]{64}", context_id):
        return idempotency_key, None, (
            "invalid_run_context_id", "run context ID must be a SHA-256 hex digest",
        )
    if context_id and context_id != idempotency_key:
        return idempotency_key, None, (
            "invalid_run_context_id", "run context ID must match the idempotency key",
        )
    return idempotency_key, context_id or None, None
