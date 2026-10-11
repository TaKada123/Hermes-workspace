"""Public agent_network facade over native AG2 envelopes and channels."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, TYPE_CHECKING, cast
from urllib.parse import urlsplit
import uuid

from ag2.network import (
    AuthBlock, ChannelState, Envelope, EV_CHANNEL_INVITE, EV_CHANNEL_INVITE_ACK,
    EV_CHANNEL_INVITE_REJECT, EV_TEXT, HubClient, NotFoundError, Passport, Resume, WsLink,
)
from ag2.network.client.agent_client import AgentClient
from ag2.network.client.channel import Channel
from ag2.network.transport.link import LinkFactory

if TYPE_CHECKING:
    from ag2.agent import Agent

from .ledger import Ledger
from .types import ExecutionRequest, ExecutionUncertain, Executor, Message, NetworkCycleError, Peer


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


def _answered_request_ids(envelopes: list[Envelope], sender_id: str) -> set[str]:
    return {envelope.causation_id for envelope in envelopes
            if envelope.sender_id == sender_id and envelope.event_type == EV_TEXT
            and envelope.causation_id and envelope.event_data.get("kind") in {"reply", "status"}}


def _unanswered_requests(envelopes: list[Envelope], recipient_id: str, peer_id: str) -> list[Envelope]:
    answered = _answered_request_ids(envelopes, recipient_id)
    return [envelope for envelope in envelopes if envelope.event_type == EV_TEXT
            and envelope.sender_id == peer_id
            and (envelope.audience is None or recipient_id in envelope.audience)
            and envelope.event_data.get("kind") == "request" and envelope.envelope_id not in answered]


class Network:
    """One enrolled Hermes identity backed by native AG2 channels and WAL.

    Project-scoped channel reuse, durable Hermes session lineage, and restart
    reconciliation sit behind open/send/ask/history/peers.
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
        self._open_lock = asyncio.Lock()
        self._ready = asyncio.Event()
        self._waiters: dict[tuple[str, str], asyncio.Future[Message]] = {}
        # The current external execution's specialist ancestry. Tool API calls made while
        # Hermes is answering an inbound request inherit this chain and cannot recurse back
        # into a profile whose run is already waiting on them.
        self._active_trace: tuple[str, ...] = ()

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
            # Attach without trusting AG2's pre-handler replay; install the
            # external callback, then reconcile persisted requests from native
            # WAL before exposing this Network to callers.
            network.client = await hub_client.attach(cast("Agent", ExternalIdentity(name)), name,
                passport=passport, resume=Resume(summary="External Hermes runtime"),
                attach_plugin=False, since_envelope_id=None)
            network.client.on_envelope(network._on_envelope)
            await network._reconcile_inbound()
            network._ready.set()
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

    async def _channels(self, *, include_terminal: bool = False):
        metadata = await self.hub_client.list_channels(agent_id=self.client.agent_id,
                                                       include_terminal=include_terminal, limit=500)
        if len(metadata) == 500:
            raise RuntimeError("channel recovery limit reached; operator reconciliation required")
        return metadata

    async def _active_channels(self):
        return [item for item in await self._channels() if item.state == ChannelState.ACTIVE]

    async def _find_active_channel(self, peer_name: str, project_id: str) -> str | None:
        matches = []
        for metadata in await self._active_channels():
            if metadata.labels.get("project_id") != project_id:
                continue
            try:
                _, peer_id = await self._channel(metadata.channel_id)
            except (NotFoundError, PermissionError):
                continue
            peer = await self.hub_client.get_agent(peer_id)
            if peer.name == peer_name:
                matches.append(metadata.channel_id)
        if len(matches) > 1:
            raise RuntimeError("multiple active channels match this project and peer; operator reconciliation required")
        return matches[0] if matches else None

    async def _wait_for_channel(self, channel: Channel, timeout: float):
        async with asyncio.timeout(timeout):
            while True:
                metadata = await channel.info()
                if metadata.state == ChannelState.ACTIVE or metadata.is_terminal():
                    return metadata
                await asyncio.sleep(0.01)

    async def _stored_channel(self, peer: str, project_id: str, timeout: float) -> str | None:
        channel_id = self.ledger.channel(self.name, peer, project_id)
        if channel_id is None:
            return None
        try:
            channel, peer_id = await self._channel(channel_id)
        except NotFoundError:
            self.ledger.forget_channel(self.name, peer, project_id)
            return None
        metadata = await channel.info()
        existing_peer = await self.hub_client.get_agent(peer_id)
        if existing_peer.name != peer or metadata.labels.get("project_id") != project_id:
            raise PermissionError("stored project-channel mapping does not match its scope")
        if not metadata.is_terminal() and metadata.state != ChannelState.ACTIVE:
            metadata = await self._wait_for_channel(channel, timeout)
        if metadata.state == ChannelState.ACTIVE:
            return channel_id
        self.ledger.forget_channel(self.name, peer, project_id)
        return None

    async def open(self, *, peer: str, project_id: str, timeout: float = 10) -> str:
        if peer not in self.allowed_peers:
            raise PermissionError("peer is not enrolled in this identity's allowlist")
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("project_id required")
        async with self._open_lock:
            existing_id = await self._stored_channel(peer, project_id, timeout)
            if existing_id is not None:
                return existing_id
            recovered_id = await self._find_active_channel(peer, project_id)
            if recovered_id is not None:
                self.ledger.remember_channel(self.name, peer, project_id, recovered_id)
                return recovered_id
            channel = await self.client.open(type="conversation", target=peer,
                                             labels={"project_id": project_id, "protocol": "hermes-tracer-v1"})
            metadata = await self._wait_for_channel(channel, timeout)
            if metadata.state != ChannelState.ACTIVE:
                raise PermissionError("channel invitation rejected or expired")
            self.ledger.remember_channel(self.name, peer, project_id, channel.channel_id)
            return channel.channel_id

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
        peer = await self.hub_client.get_agent(peer_id)
        trace = self._active_trace or (self.name,)
        if self.name not in trace:
            trace = (*trace, self.name)
        if peer.name in trace:
            raise NetworkCycleError(f"network cycle detected: {peer.name} is already in the request ancestry")
        return await channel.send(text, audience=[peer_id], event_data={
            "kind": "request", "text": text, "operation_id": operation_id, "trace": list(trace),
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

    async def _reconcile_inbound(self) -> None:
        """Recover active work and durably flag requests stranded on terminal channels."""
        metadata = await self._channels(include_terminal=True)
        for channel_metadata in metadata:
            if channel_metadata.state != ChannelState.ACTIVE and not channel_metadata.is_terminal():
                continue
            try:
                channel, peer_id = await self._channel(channel_metadata.channel_id)
            except (NotFoundError, PermissionError):
                continue
            wal = await self.hub_client.read_wal(channel.channel_id)
            requests = _unanswered_requests(wal, self.client.agent_id, peer_id)
            if channel_metadata.is_terminal():
                project_id = channel.metadata.labels["project_id"]
                for envelope in requests:
                    operation_id = envelope.event_data.get("operation_id")
                    if isinstance(operation_id, str) and operation_id.strip():
                        self.ledger.note_terminal_request(self.name, project_id, channel.channel_id,
                                                          envelope.envelope_id, operation_id)
                continue
            for envelope in requests:
                await self._process_request(envelope, channel, peer_id)

    async def _process_request(self, envelope: Envelope, channel: Channel, peer_id: str) -> None:
        data = envelope.event_data
        if not isinstance(data.get("operation_id"), str) or not data["operation_id"].strip():
            return
        if not isinstance(data.get("text"), str) or not data["text"].strip():
            return
        request = ExecutionRequest(self.name, channel.metadata.labels["project_id"],
                                   envelope.channel_id, data["operation_id"], data["text"],
                                   *self.ledger.session(self.name, channel.metadata.labels["project_id"], envelope.channel_id))
        async with self._run_lock:
            # A concurrently delivered original is redundant if startup replay
            # already posted its durable reply.
            wal = await self.hub_client.read_wal(envelope.channel_id)
            if envelope.envelope_id in _answered_request_ids(wal, self.client.agent_id):
                return
            try:
                result = self.ledger.admit(request)
                if result is None:
                    if self.executor is None:
                        raise ExecutionUncertain("no executor enrolled")
                    peer_name = (await self.hub_client.get_agent(peer_id)).name
                    trace = data.get("trace", [])
                    if (not isinstance(trace, list)
                            or any(not isinstance(name, str) or not name.strip() for name in trace)
                            or len(trace) != len(set(trace))):
                        raise ValueError("invalid network request ancestry")
                    if not trace:
                        trace = [peer_name]
                    elif peer_name not in trace:
                        trace = [peer_name, *trace]
                    if self.name in trace:
                        raise ValueError("network cycle detected: recipient is already in the request ancestry")
                    previous_trace = self._active_trace
                    self._active_trace = (*trace, self.name)
                    try:
                        result = await self.executor(request)
                    finally:
                        self._active_trace = previous_trace
                    self.ledger.advance_session(request.profile, request.project_id, request.channel_id, result.session_id)
                    self.ledger.finish(request, result)
                reply_data: dict[str, Any] = {"kind": "reply", "text": result.text,
                    "session_id": result.session_id, "run_id": result.run_id}
            except Exception as exc:  # health: allow BLE001 -- external executor boundary: ACK held work instead of native NACK/replay; exception text may contain secrets
                reply_data = {"kind": "status", "text": f"execution unsettled or refused ({type(exc).__name__}); explicit operator reconciliation required"}
            reply_data["operation_id"] = request.operation_id
            await channel.send(reply_data["text"], audience=[peer_id],
                               causation_id=envelope.envelope_id, event_data=reply_data, depth=envelope.depth)

    async def history(self, channel_id: str) -> list[Message]:
        channel, _ = await self._channel(channel_id)
        project_id = channel.metadata.labels["project_id"]
        envelopes = await self.hub_client.read_wal(channel_id)
        messages = [_message(e) for e in envelopes
                    if e.event_type == EV_TEXT and e.event_data.get("kind") in {"request", "reply", "status"}]
        messages.extend(Message(
            envelope_id=f"local-recovery:{source_channel}:{request_id}", sender_id=self.client.agent_id,
            kind="status", text=f"Unanswered request is stranded in terminal AG2 channel {source_channel}; "
            "it was not replayed automatically. Operator reconciliation is required.",
            operation_id=operation_id, causation_id=request_id,
        ) for source_channel, request_id, operation_id
          in self.ledger.terminal_requests(self.name, project_id))
        return messages

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
        # Hold live deliveries until durable WAL reconciliation completes.
        await self._ready.wait()
        channel, peer_id = await self._channel(envelope.channel_id)
        if envelope.sender_id != peer_id:
            return
        kind = envelope.event_data.get("kind")
        if kind in {"reply", "status"}:
            waiter = self._waiters.get((envelope.channel_id, envelope.event_data.get("operation_id")))
            if waiter is not None and not waiter.done():
                waiter.set_result(_message(envelope))
            return  # Replies never trigger another runtime turn.
        if kind == "request":
            await self._process_request(envelope, channel, peer_id)
