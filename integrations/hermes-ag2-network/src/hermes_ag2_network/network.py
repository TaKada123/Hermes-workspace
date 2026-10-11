"""Public agent_network facade over native AG2 envelopes and channels."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, TYPE_CHECKING, cast
from urllib.parse import urlsplit
import uuid

from ag2.network import (
    AuthBlock, ChannelState, Envelope, EV_CHANNEL_INVITE, EV_CHANNEL_INVITE_ACK,
    EV_CHANNEL_INVITE_REJECT, EV_TEXT, HubClient, Passport, Resume, WsLink,
)
from ag2.network.client.agent_client import AgentClient
from ag2.network.client.channel import Channel
from ag2.network.transport.link import LinkFactory

if TYPE_CHECKING:
    from ag2.agent import Agent

from .ledger import Ledger
from .types import ExecutionRequest, ExecutionUncertain, Executor, Message, Peer


class ExternalIdentity:
    """Pinned AG2 1.1.2 duck-typed identity; deliberately not ag2.Agent.

    HubClient requires an Agent in its annotations but only .name here with
    attach_plugin=False. Any accidental default model handler fails closed.
    """
    def __init__(self, name: str):
        self.name = name

    async def ask(self, *args, **kwargs):
        raise RuntimeError("AG2 model execution disabled: external Hermes identity")


def _message(envelope: Envelope) -> Message:
    data = envelope.event_data
    return Message(envelope.envelope_id, envelope.sender_id, data["kind"], data.get("text", ""),
                   data["operation_id"], envelope.causation_id,
                   data.get("session_id", ""), data.get("run_id", ""))


class Network:
    """One enrolled identity. Use connect() as an async context manager.

    open/send/ask/history/peers are the externally callable seam. This first
    slice creates fresh native channels, not named continuing Hermes sessions.
    """
    client: AgentClient  # Initialized by the async connect factory.

    def __init__(self, hub_client: HubClient, name: str, allowed_peers: set[str],
                 executor: Executor | None, ledger_path: Path):
        self.hub_client = hub_client
        self.name = name
        self.allowed_peers = frozenset(allowed_peers)
        self.executor = executor
        self.ledger = Ledger(ledger_path)
        self._run_lock = asyncio.Lock()
        self._waiters: dict[tuple[str, str], asyncio.Future[Message]] = {}

    @classmethod
    @asynccontextmanager
    async def connect(cls, url: str, *, name: str, token: str, allowed_peers: set[str],
                      ledger_path: Path, executor: Executor | None = None):
        if not name or not token:
            raise ValueError("identity and credential required")
        parsed = urlsplit(url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("hub URL must not contain credentials/query/fragment")
        if parsed.scheme != "wss" and not (parsed.scheme == "ws" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}):
            raise ValueError("WS credentials require TLS or loopback")
        # 1.1.2 LinkClient declares endpoint_id writable but WsLinkClient
        # implements a read-only property. Native WS is runtime-tested here.
        hub_client = HubClient(cast(LinkFactory, WsLink(url)))
        network = cls(hub_client, name, allowed_peers, executor, ledger_path)
        try:
            await hub_client.open()
            passport = Passport(name=name, owner="hermes-profile",
                                auth=AuthBlock(scheme="api_key", claim={"token": token}))
            # No replay before the custom handler is installed. Automatic
            # pending-turn replay is intentionally deferred, not made up.
            network.client = await hub_client.attach(cast("Agent", ExternalIdentity(name)), name,
                passport=passport, resume=Resume(summary="External Hermes runtime"),
                attach_plugin=False, since_envelope_id=None)
            network.client.on_envelope(network._on_envelope)
            yield network
        finally:
            # close disconnects; AgentClient.close/shutdown would unregister.
            await hub_client.close()
            network.ledger.close()
            for future in network._waiters.values():
                if not future.done():
                    future.cancel()

    async def peers(self) -> list[Peer]:
        # Avoid exposing Passport.auth or arbitrary private runtime metadata.
        return [Peer(p.name, p.agent_id) for p in await self.hub_client.list_agents()
                if p.name in self.allowed_peers and p.agent_id]

    async def open(self, *, peer: str, project_id: str, timeout: float = 10) -> str:
        if peer not in self.allowed_peers:
            raise PermissionError("peer is not enrolled in this identity's allowlist")
        if not project_id:
            raise ValueError("project_id required")
        channel = await self.client.open(type="conversation", target=peer,
                                         labels={"project_id": project_id, "protocol": "hermes-tracer-v1"})
        async with asyncio.timeout(timeout):
            while True:
                metadata = await channel.info()
                if metadata.state == ChannelState.ACTIVE:
                    return channel.channel_id
                if metadata.is_terminal():
                    raise PermissionError("channel invitation rejected or expired")
                await asyncio.sleep(0.01)

    async def _channel(self, channel_id: str) -> tuple[Channel, str]:
        metadata = await self.hub_client.get_channel(channel_id)
        ids = [p.agent_id for p in metadata.participants]
        if self.client.agent_id not in ids or len(ids) != 2:
            raise PermissionError("channel is not this identity's two-party channel")
        peer_id = next(i for i in ids if i != self.client.agent_id)
        peer = await self.hub_client.get_agent(peer_id)
        if (peer.name not in self.allowed_peers
                or metadata.labels.get("protocol") != "hermes-tracer-v1"
                or not isinstance(metadata.labels.get("project_id"), str)
                or not metadata.labels["project_id"].strip()):
            raise PermissionError("channel peer, protocol, or project scope is invalid")
        return Channel(metadata=metadata, client=self.client), peer_id

    async def send(self, channel_id: str, text: str, *, operation_id: str | None = None) -> str:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("nonempty text required")
        channel, peer_id = await self._channel(channel_id)
        operation_id = operation_id or uuid.uuid4().hex
        if not isinstance(operation_id, str) or not operation_id.strip():
            raise ValueError("nonempty operation_id required")
        return await channel.send(text, audience=[peer_id], event_data={
            "kind": "request", "text": text, "operation_id": operation_id,
        }, depth=0)

    async def ask(self, channel_id: str, text: str, *, operation_id: str | None = None,
                  timeout: float = 300) -> Message:
        operation_id = operation_id or uuid.uuid4().hex
        key = (channel_id, operation_id)
        if key in self._waiters:
            raise ValueError("operation already awaited")
        future = asyncio.get_running_loop().create_future()
        self._waiters[key] = future
        try:
            request_id = await self.send(channel_id, text, operation_id=operation_id)
            reply = await asyncio.wait_for(future, timeout)
            if reply.causation_id != request_id:
                raise ValueError("reply does not correlate to the posted request")
            if reply.kind == "status":
                raise ExecutionUncertain(reply.text)
            return reply
        finally:
            self._waiters.pop(key, None)

    async def history(self, channel_id: str) -> list[Message]:
        await self._channel(channel_id)
        return [_message(e) for e in await self.hub_client.read_wal(channel_id)
                if e.event_type == EV_TEXT and e.event_data.get("kind") in {"request", "reply", "status"}]

    async def _on_envelope(self, envelope: Envelope):
        if envelope.event_type == EV_CHANNEL_INVITE:
            metadata = await self.hub_client.get_channel(envelope.channel_id)
            inviter = await self.hub_client.get_agent(metadata.creator_id)
            allowed = (inviter.name in self.allowed_peers
                       and metadata.labels.get("protocol") == "hermes-tracer-v1"
                       and isinstance(metadata.labels.get("project_id"), str)
                       and bool(metadata.labels["project_id"].strip()))
            await self.client.send_envelope(Envelope(channel_id=envelope.channel_id,
                sender_id=self.client.agent_id, audience=[metadata.creator_id],
                event_type=EV_CHANNEL_INVITE_ACK if allowed else EV_CHANNEL_INVITE_REJECT,
                event_data={"channel_id": envelope.channel_id}, causation_id=envelope.envelope_id))
            return
        if envelope.event_type != EV_TEXT:
            return
        channel, peer_id = await self._channel(envelope.channel_id)
        if envelope.sender_id != peer_id:
            return
        data = envelope.event_data
        kind = data.get("kind")
        if kind in {"reply", "status"}:
            waiter = self._waiters.get((envelope.channel_id, data.get("operation_id")))
            if waiter is not None and not waiter.done():
                waiter.set_result(_message(envelope))
            return  # Replies never trigger another runtime turn.
        if kind != "request":
            return
        if not isinstance(data.get("operation_id"), str) or not data["operation_id"].strip():
            return
        if not isinstance(data.get("text"), str) or not data["text"].strip():
            return
        request = ExecutionRequest(self.name, channel.metadata.labels["project_id"],
                                   envelope.channel_id, data["operation_id"], data["text"])
        async with self._run_lock:
            # A failed handler would be NACKed and immediately replayed by
            # native AG2. Catch execution errors after durable admission to
            # ACK safely with a status, never automatically re-execute.
            try:
                result = self.ledger.admit(request)
                if result is None:
                    if self.executor is None:
                        raise ExecutionUncertain("no executor enrolled")
                    result = await self.executor(request)
                    self.ledger.finish(request.operation_id, result)
                reply_data: dict[str, Any] = {"kind": "reply", "text": result.text,
                    "session_id": result.session_id, "run_id": result.run_id}
            except Exception as exc:  # health: allow BLE001 -- external executor boundary: ACK held work instead of native NACK/replay; exception text may contain secrets
                reply_data = {"kind": "status", "text": f"execution unsettled or refused ({type(exc).__name__}); explicit operator reconciliation required"}
            reply_data["operation_id"] = request.operation_id
            await channel.send(reply_data["text"], audience=[peer_id],
                               causation_id=envelope.envelope_id, event_data=reply_data, depth=envelope.depth)
