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
        }, ["channel_id", "text", "operation_id"]),
        "POST", "/v1/send", ["channel_id", "text", "operation_id"], None,
    ),
    (
        "agent_network_ask",
        "Ask an enrolled specialist and wait for its correlated reply.",
        _schema("agent_network_ask", "Ask an allowed specialist and wait for the correlated response.", {
            "channel_id": {**_STRING, "description": "Channel ID returned by agent_network_open."},
            "text": {**_STRING, "description": "New question only; history is not resent."},
            "operation_id": {**_STRING, "description": "Stable ID for this intended operation."},
            "timeout_seconds": {"type": "number", "minimum": 1, "maximum": 300},
        }, ["channel_id", "text", "operation_id"]),
        "POST", "/v1/ask", ["channel_id", "text", "operation_id"], "timeout_seconds",
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
    """Register five optional network tools using only public PluginContext methods."""
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
