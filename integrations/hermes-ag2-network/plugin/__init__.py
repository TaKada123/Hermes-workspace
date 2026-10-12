"""Optional Hermes plugin exposing the profile-bound native AG2 Network tools."""
from __future__ import annotations

import json
from typing import Any

from .client import available, request


def _schema(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }


_STRING = {"type": "string"}
_ARTIFACT_REFS = {
    "type": "array", "maxItems": 16,
    "items": {
        "type": "object", "additionalProperties": False,
        "required": ["kind", "uri", "media_type", "size_bytes", "sha256", "label"],
        "properties": {
            "kind": {"type": "string", "enum": ["file", "image", "check_report", "git_reference", "result", "error", "status"]},
            "uri": {"type": "string", "maxLength": 2048},
            "media_type": {"type": "string", "maxLength": 127},
            "size_bytes": {"type": "integer", "minimum": 0},
            "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "label": {"type": "string", "maxLength": 256},
        },
    },
}
TOOLS = (
    (
        "agent_network_peers",
        "List specialists enrolled for this Hermes profile or project.",
        _schema("agent_network_peers", "List specialists enrolled for this Hermes profile or project.", {
            "project_id": {**_STRING, "description": "Optional project scope to apply its peer grants."},
        }, []),
        "GET", "/v1/peers", ["project_id"], None,
    ),
    (
        "agent_network_open",
        "Open or resume a persistent conversation with an allowed specialist for a project.",
        _schema("agent_network_open", "Open or resume a persistent specialist channel.", {
            "peer": {**_STRING, "description": "Enrolled specialist name."},
            "project_id": {**_STRING, "description": "Opaque project scope label; not a filesystem sandbox."},
        }, ["peer", "project_id"]),
        "POST", "/v1/open", ["peer", "project_id"], None,
    ),
    (
        "agent_network_send",
        "Send an asynchronous request through an owned specialist channel.",
        _schema("agent_network_send", "Send a request to the specialist owning this channel.", {
            "channel_id": {**_STRING, "description": "Channel ID returned by agent_network_open."},
            "text": {**_STRING, "description": "New message only; history is not resent."},
            "operation_id": {**_STRING, "description": "Stable ID for this intended operation."},
            "artifact_refs": {**_ARTIFACT_REFS, "description": "Typed refs from artifact_publish provide verified project content; external URLs remain inert metadata. No file paths."},
        }, ["channel_id", "text", "operation_id"]),
        "POST", "/v1/send", ["channel_id", "text", "operation_id", "artifact_refs"], None,
    ),
    (
        "agent_network_ask",
        "Ask an enrolled specialist and wait for its correlated reply.",
        _schema("agent_network_ask", "Ask an allowed specialist and wait for the correlated response.", {
            "channel_id": {**_STRING, "description": "Channel ID returned by agent_network_open."},
            "text": {**_STRING, "description": "New question only; history is not resent."},
            "operation_id": {**_STRING, "description": "Stable ID for this intended operation."},
            "artifact_refs": {**_ARTIFACT_REFS, "description": "Typed refs from artifact_publish provide verified project content; external URLs remain inert metadata. No file paths."},
            "timeout_seconds": {"type": "number", "minimum": 1, "maximum": 300},
        }, ["channel_id", "text", "operation_id"]),
        "POST", "/v1/ask", ["channel_id", "text", "operation_id", "artifact_refs"], "timeout_seconds",
    ),
    (
        "agent_network_artifact_publish",
        "Snapshot an approved project file as a verified opaque reference; never shares private memory.",
        _schema("agent_network_artifact_publish", "Publish a bounded approved-root snapshot. For typed final output return JSON: {\"network_result\":{\"text\":\"summary\",\"artifact_refs\":[the_returned_ref]}}.", {
            "channel_id": _STRING, "path": _STRING,
            "kind": _ARTIFACT_REFS["items"]["properties"]["kind"],
            "media_type": _STRING, "label": _STRING,
        }, ["channel_id", "path"]),
        "POST", "/v1/artifacts/publish", ["channel_id", "path", "kind", "media_type", "label"], None,
    ),
    (
        "agent_network_artifact_read",
        "Consume verified same-host project content; hash and size are checked again. No remote fetching.",
        _schema("agent_network_artifact_read", "Read a granted content-addressed project snapshot.", {
            "channel_id": _STRING, "artifact_ref": _ARTIFACT_REFS["items"],
        }, ["channel_id", "artifact_ref"]),
        "POST", "/v1/artifacts/read", ["channel_id", "artifact_ref"], None,
    ),
    (
        "agent_network_history",
        "Read the native conversation history for a channel owned by this profile.",
        _schema("agent_network_history", "Read request/reply/status history for an owned channel.", {
            "channel_id": {**_STRING, "description": "Channel ID returned by agent_network_open."},
        }, ["channel_id"]),
        "GET", "/v1/history", ["channel_id"], None,
    ),
)


def register(ctx) -> None:
    """Register optional network/content tools using public PluginContext methods."""
    def handler_for(method: str, path: str, fields: list[str] | None, timeout_field: str | None):
        def handler(args: dict | None = None, **kwargs: Any) -> str:
            args = args if isinstance(args, dict) else {}
            body = {key: args[key] for key in fields or [] if key in args} if method == "POST" else {}
            query = {key: args[key] for key in fields or [] if key in args} if method == "GET" else {}
            if timeout_field and timeout_field in args:
                body[timeout_field] = args[timeout_field]
            result = request(ctx, method, path, payload=body or None, query=query or None,
                             run_context_id=kwargs.get("run_context_id"))
            return json.dumps(result, ensure_ascii=False)
        return handler

    for name, description, schema, method, path, fields, timeout_field in TOOLS:
        ctx.register_tool(
            name=name,
            toolset="agent_network",
            schema=schema,
            handler=handler_for(method, path, fields, timeout_field),
            check_fn=lambda _ctx=ctx: available(_ctx),
            description=description,
            emoji="🤝",
        )
