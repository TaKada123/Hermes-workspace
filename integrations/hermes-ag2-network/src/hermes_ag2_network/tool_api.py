"""Authenticated loopback control interface used only by the optional Hermes plugin."""
from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from contextlib import AbstractAsyncContextManager
import hmac
from typing import Any

from aiohttp import web
from ag2.network import NotFoundError

from .network import Network
from .artifacts import ArtifactRef
from .types import ExecutionUncertain, NetworkBudgetExceeded, NetworkCycleError


class InvalidRequest(ValueError):
    """A malformed local tool request."""


class ToolAPI(AbstractAsyncContextManager["ToolAPI"]):
    """Expose one already-authenticated Network identity on loopback only.

    The listener is never bound to a caller-selected address. Authentication is
    paired with an expected-profile header so a copied/misrouted token cannot
    accidentally drive a different profile's bridge.
    """

    def __init__(self, network: Network, token: str, *, port: int = 8766):
        if not isinstance(token, str) or not token.strip():
            raise ValueError("tool API token required")
        if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535:
            raise ValueError("tool API port must be between 0 and 65535")
        self.network = network
        self._token = token
        self.port = port
        self._runner: web.AppRunner | None = None
        self.url = ""

    async def __aenter__(self) -> ToolAPI:
        app = web.Application(client_max_size=64 * 1024, middlewares=[self._authorize])
        app.add_routes([
            web.get("/v1/peers", self._peers),
            web.post("/v1/open", self._open),
            web.post("/v1/send", self._send),
            web.post("/v1/ask", self._ask),
            web.get("/v1/history", self._history),
            web.get("/v1/channels", self._channels),
            web.post("/v1/artifacts/publish", self._publish_artifact),
            web.post("/v1/artifacts/read", self._read_artifact),
        ])
        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", self.port)
        await site.start()
        sockets = getattr(site._server, "sockets", None) if site._server is not None else None
        if not sockets:
            await self._runner.cleanup()
            self._runner = None
            raise RuntimeError("tool API failed to bind its loopback socket")
        self.port = int(sockets[0].getsockname()[1])
        self.url = f"http://127.0.0.1:{self.port}"
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    @web.middleware
    async def _authorize(self, request: web.Request, handler):
        supplied = request.headers.get("Authorization", "")
        if not hmac.compare_digest(supplied, f"Bearer {self._token}"):
            return web.json_response({"ok": False, "error": "bridge authentication failed"}, status=401)
        if request.headers.get("X-Hermes-Profile") != self.network.name:
            return web.json_response({"ok": False, "error": "profile binding mismatch"}, status=403)
        try:
            return await handler(request)
        except InvalidRequest:
            return web.json_response({"ok": False, "error": "invalid network request"}, status=400)
        except NotFoundError:
            return web.json_response({"ok": False, "error": "network channel not found"}, status=404)
        except PermissionError:
            return web.json_response({"ok": False, "error": "peer or channel access denied"}, status=403)
        except NetworkBudgetExceeded as exc:
            return web.json_response({"ok": False, "error": f"{exc.summary}; {exc.remediation}",
                                      "admission": exc.public_details()}, status=429)
        except NetworkCycleError:
            return web.json_response({"ok": False,
                                      "error": "network cycle detected; request rejected before delivery"}, status=409)
        except ExecutionUncertain:
            return web.json_response({"ok": False, "error": "execution is uncertain; operator reconciliation required"}, status=409)
        except (asyncio.TimeoutError, TimeoutError):
            return web.json_response({"ok": False, "error": "network request timed out"}, status=504)
        except ValueError:
            return web.json_response({"ok": False, "error": "invalid network request"}, status=400)
        except Exception as exc:  # health: allow BLE001 -- external-network API; never echo executor details or secrets
            return web.json_response({"ok": False, "error": f"network operation failed ({type(exc).__name__})"}, status=502)

    def _success(self, result: Any) -> web.Response:
        return web.json_response({"ok": True, "profile": self.network.name, "result": result})

    @staticmethod
    async def _json_body(request: web.Request) -> dict[str, Any]:
        try:
            payload = await request.json()
        except (ValueError, UnicodeDecodeError):
            raise InvalidRequest from None
        if not isinstance(payload, dict):
            raise InvalidRequest
        return payload

    @staticmethod
    def _required_string(payload: dict[str, Any], name: str) -> str:
        value = payload.get(name)
        if not isinstance(value, str) or not value.strip():
            raise InvalidRequest
        return value

    @staticmethod
    def _artifact_refs(payload: dict[str, Any]) -> tuple[ArtifactRef, ...]:
        raw = payload.get("artifact_refs", [])
        if not isinstance(raw, list) or len(raw) > 16:
            raise InvalidRequest
        try:
            refs = tuple(ArtifactRef.from_wire(value) for value in raw)
        except ValueError:
            raise InvalidRequest from None
        if any(ref.is_local_file for ref in refs):
            raise InvalidRequest
        return refs

    async def _publish_artifact(self, request: web.Request) -> web.Response:
        payload = await self._json_body(request)
        self.network._execution_context(request.headers.get("X-Hermes-Run-Context-Id"), False)
        ref = await self.network.publish_artifact(
            self._required_string(payload, "channel_id"), Path(self._required_string(payload, "path")),
            kind=payload.get("kind", "file"), media_type=payload.get("media_type", "application/octet-stream"),
            label=payload.get("label", ""),
        )
        return self._success(ref.to_wire())

    async def _read_artifact(self, request: web.Request) -> web.Response:
        payload = await self._json_body(request)
        self.network._execution_context(request.headers.get("X-Hermes-Run-Context-Id"), False)
        ref = ArtifactRef.from_wire(payload.get("artifact_ref"))
        content = await self.network.read_artifact(self._required_string(payload, "channel_id"), ref)
        result: dict[str, Any] = {"artifact_ref": ref.to_wire(), "verified": True}
        if ref.media_type.startswith("text/") or ref.media_type == "application/json":
            result["text"] = content.decode("utf-8")
        else:
            result["base64"] = base64.b64encode(content).decode("ascii")
        return self._success(result)

    async def _peers(self, request: web.Request) -> web.Response:
        project_id = request.query.get("project_id")
        if project_id is not None and not project_id.strip():
            raise InvalidRequest
        peers = await self.network.peers(project_id=project_id)
        return self._success([{"name": peer.name, "agent_id": peer.agent_id} for peer in peers])

    async def _open(self, request: web.Request) -> web.Response:
        payload = await self._json_body(request)
        channel_id = await self.network.open(
            peer=self._required_string(payload, "peer"),
            project_id=self._required_string(payload, "project_id"),
        )
        return self._success({"channel_id": channel_id})

    async def _send(self, request: web.Request) -> web.Response:
        payload = await self._json_body(request)
        operation_id = self._required_string(payload, "operation_id")
        envelope_id = await self.network.send(
            self._required_string(payload, "channel_id"),
            self._required_string(payload, "text"),
            operation_id=operation_id,
            artifact_refs=self._artifact_refs(payload),
            _network_context_id=request.headers.get("X-Hermes-Run-Context-Id"),
            _inherit_context=False,
        )
        return self._success({"envelope_id": envelope_id, "operation_id": operation_id})

    async def _ask(self, request: web.Request) -> web.Response:
        payload = await self._json_body(request)
        timeout = payload.get("timeout_seconds", 300)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise InvalidRequest
        timeout = min(300.0, max(1.0, float(timeout)))
        operation_id = self._required_string(payload, "operation_id")
        reply = await self.network.ask(
            self._required_string(payload, "channel_id"),
            self._required_string(payload, "text"),
            operation_id=operation_id,
            timeout=timeout,
            artifact_refs=self._artifact_refs(payload),
            _network_context_id=request.headers.get("X-Hermes-Run-Context-Id"),
            _inherit_context=False,
        )
        return self._success({
            "envelope_id": reply.envelope_id,
            "request_id": reply.request_id,
            "operation_id": reply.operation_id,
            "kind": reply.kind,
            "text": reply.text,
            "session_id": reply.session_id,
            "run_id": reply.run_id,
            "artifact_refs": [ref.to_wire() for ref in reply.artifact_refs],
        })

    async def _history(self, request: web.Request) -> web.Response:
        channel_id = request.query.get("channel_id", "")
        if not channel_id.strip():
            raise InvalidRequest
        messages = await self.network.history(channel_id)
        return self._success([{
            "envelope_id": message.envelope_id,
            "sender_id": message.sender_id,
            "kind": message.kind,
            "text": message.text,
            "operation_id": message.operation_id,
            "causation_id": message.causation_id,
            "session_id": message.session_id,
            "run_id": message.run_id,
            "artifact_refs": [ref.to_wire() for ref in message.artifact_refs],
        } for message in messages])

    async def _channels(self, request: web.Request) -> web.Response:
        project = request.query.get('project_id', '')
        if not project.strip():
            raise InvalidRequest
        # Native authenticated listing includes closed channels, not just locally
        # remembered opens. Recheck project/peer grants before exposing metadata.
        result = []
        for metadata in await self.network._channels(include_terminal=True):
            if metadata.labels.get('project_id') != project:
                continue
            try:
                await self.network._channel(metadata.channel_id)
            except PermissionError:
                continue
            result.append({'channel_id': metadata.channel_id, 'project_id': project})
        return self._success(result)
