"""Public agent_network facade over native AG2 envelopes and channels."""
import asyncio
from collections.abc import Mapping
from contextlib import asynccontextmanager
from dataclasses import replace
import json
import math
from hashlib import sha256
from pathlib import Path
from typing import Any, TYPE_CHECKING, cast
from urllib.parse import urlsplit
import time
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


from .admission import Admission
from .artifacts import ArtifactRef, ArtifactStore
from .ledger import Ledger
from .types import (
    ExecutionBudget, ExecutionRequest, ExecutionResult, ExecutionTaskContext, ExecutionTerminated, ExecutionUncertain,
    Executor, Message, NetworkBudgetExceeded, NetworkCycleError, NetworkLimits, Peer, RequestNotAdmitted,
    network_execution_context_id,
)



class ExternalIdentity:
    """Pinned AG2 1.1.2 duck-typed identity; deliberately not ag2.Agent.

    HubClient requires an Agent in its annotations but only .name here with
    attach_plugin=False. Any accidental default model handler fails closed.
    """
    def __init__(self, name: str):
        self.name = name

    async def ask(self, *args, **kwargs):
        raise RuntimeError("AG2 model execution disabled: external Hermes identity")


def _artifact_refs(data: dict[str, Any]) -> tuple[ArtifactRef, ...]:
    raw = data.get("artifact_refs", [])
    if not isinstance(raw, list) or len(raw) > 16:
        raise ValueError("invalid artifact reference list")
    if len(json.dumps(raw).encode("utf-8")) > 16 * 1024:
        raise ValueError("artifact reference metadata exceeds the size limit")
    refs = tuple(ArtifactRef.from_wire(item) for item in raw)
    if any(ref.is_local_file for ref in refs):
        raise ValueError("local file references cannot cross profiles")
    return refs


def _message(envelope: Envelope) -> Message:
    data = envelope.event_data
    admission = data.get("admission")
    code = NetworkBudgetExceeded(code=admission.get("code", "budget") if isinstance(admission, dict) else "budget").code
    return Message(envelope.envelope_id, envelope.sender_id, data["kind"], data.get("text", ""),
                   data["operation_id"], envelope.causation_id,
                   data.get("session_id", ""), data.get("run_id", ""),
                   code, _artifact_refs(data))


def _answered_request_ids(envelopes: list[Envelope], sender_id: str) -> set[str]:
    return {envelope.causation_id for envelope in envelopes
            if envelope.sender_id == sender_id and envelope.event_type == EV_TEXT
            and envelope.causation_id and envelope.event_data.get("kind") in {"reply", "status", "rejected"}}


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
                 executor: Executor | None, ledger_path: Path,
                 project_peers: Mapping[str, set[str]] | None = None,
                 limits: NetworkLimits | None = None, control_path: Path | None = None,
                 artifact_store: ArtifactStore | None = None):
        self.hub_client = hub_client
        self.name = name
        self.allowed_peers = frozenset(allowed_peers)
        self.project_peers = {
            project_id: frozenset(peers) for project_id, peers in (project_peers or {}).items()
        }
        if any(not isinstance(project_id, str) or not project_id.strip()
               for project_id in self.project_peers):
            raise ValueError("project peer grants require nonempty project IDs")
        if any(not isinstance(peer, str) or not peer.strip()
               for peers in (*self.project_peers.values(), self.allowed_peers) for peer in peers):
            raise ValueError("peer grants require nonempty peer names")
        self.executor = executor
        self.artifact_store = artifact_store
        self.limits = limits or NetworkLimits()
        self.ledger = Ledger(ledger_path)
        self.admission = Admission(control_path or Path(ledger_path).parent / "network-admission.sqlite",
                                   self.limits.max_active, self.limits.max_pending)
        self._run_lock = asyncio.Lock()
        self._open_lock = asyncio.Lock()
        self._ready = asyncio.Event()
        self._pending_inbound = 0
        self._waiters: dict[tuple[str, str], asyncio.Queue[Message | None]] = {}
        # The current external execution's specialist ancestry. Tool API calls made while
        # Hermes is answering an inbound request inherit this chain and cannot recurse back
        # into a profile whose run is already waiting on them.
        self._held_request = self.ledger.held(self.name)
        self._active_context = self._held_request._task_context if self._held_request else None
        if self._active_context is not None:
            self.admission.restore(self.name, self._active_context.network_context_id)

    @classmethod
    @asynccontextmanager
    async def connect(cls, url: str, *, name: str, token: str, allowed_peers: set[str],
                      ledger_path: Path, executor: Executor | None = None,
                      project_peers: Mapping[str, set[str]] | None = None,
                      limits: NetworkLimits | None = None, control_path: Path | None = None,
                      artifact_store: ArtifactStore | None = None):
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
        network = cls(hub_client, name, allowed_peers, executor, ledger_path, project_peers, limits, control_path, artifact_store)
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
            network.admission.close()
            for replies in network._waiters.values():
                replies.put_nowait(None)

    def _peers_for_project(self, project_id: str) -> frozenset[str]:
        return self.project_peers.get(project_id, self.allowed_peers)

    def _is_peer_allowed(self, peer: str, project_id: str) -> bool:
        return peer in self._peers_for_project(project_id)

    async def peers(self, *, project_id: str | None = None) -> list[Peer]:
        # Avoid exposing Passport.auth or arbitrary private runtime metadata.
        if project_id is not None and (not isinstance(project_id, str) or not project_id.strip()):
            raise ValueError("project_id must be a nonempty string")
        allowed = (self._peers_for_project(project_id) if project_id is not None
                   else self.allowed_peers.union(*self.project_peers.values()))
        return [Peer(p.name, p.agent_id) for p in await self.hub_client.list_agents()
                if p.name in allowed and p.agent_id]

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
        deadline_at = self._deadline_for(timeout, self.limits.request_timeout)
        timeout = deadline_at - time.time()
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("project_id required")
        if not self._is_peer_allowed(peer, project_id):
            raise PermissionError("peer is not enrolled for this project")
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
        project_id = metadata.labels.get("project_id")
        if (not isinstance(project_id, str) or not project_id.strip()
                or peer.name not in self._peers_for_project(project_id)
                or metadata.labels.get("protocol") != "hermes-tracer-v1"):
            raise PermissionError("channel peer, protocol, or project scope is invalid")
        return Channel(metadata=metadata, client=self.client), peer_id

    def _execution_context(self, network_context_id: str | None,
                           inherit_active: bool) -> ExecutionTaskContext | None:
        context = self._active_context
        if network_context_id is not None:
            if context is None or network_context_id != context.network_context_id:
                raise NetworkBudgetExceeded(code="stale_context")
            return context
        if context is not None and not inherit_active:
            raise NetworkBudgetExceeded(code="profile_held")
        return context

    def _outbound_budget(self, deadline_at: float | None,
                         context: ExecutionTaskContext | None) -> ExecutionBudget:
        now = time.time()
        parent = context.budget if context is not None else None
        requested_deadline = parent.deadline_at if parent is not None else now + self.limits.request_timeout
        if deadline_at is not None:
            if (isinstance(deadline_at, bool) or not isinstance(deadline_at, (int, float))
                    or not math.isfinite(deadline_at)):
                raise NetworkBudgetExceeded(code="deadline")
            requested_deadline = min(requested_deadline, float(deadline_at))
        requested_deadline = min(requested_deadline, now + self.limits.request_timeout)
        if requested_deadline <= now:
            raise NetworkBudgetExceeded(code="deadline")
        if parent is not None:
            if parent.turns_remaining < 1 or parent.hops_remaining < 1:
                raise NetworkBudgetExceeded(code="nested_budget")
            remaining = self.admission.remaining(parent.interaction_id)
            budget = ExecutionBudget(requested_deadline, min(parent.turns_remaining, remaining),
                                     parent.hops_remaining - 1, parent.interaction_id)
        else:
            identity = uuid.uuid4().hex
            budget = ExecutionBudget(requested_deadline, self.limits.max_turns,
                                     self.limits.max_hops - 1, identity)
        return budget

    def _inbound_budget(self, data: dict[str, Any]) -> ExecutionBudget:
        now = time.time()
        raw = data.get("budget")
        if raw is None:  # Accept pre-budget requests already persisted in native WAL.
            deadline = now + self.limits.request_timeout
            identity = self.admission.interaction(self.limits.max_turns, deadline)
            return ExecutionBudget(deadline, self.limits.max_turns, self.limits.max_hops - 1, identity)
        if not isinstance(raw, dict):
            raise NetworkBudgetExceeded(code="invalid_budget")
        deadline = raw.get("deadline_at")
        turns = raw.get("turns_remaining")
        hops = raw.get("hops_remaining")
        if (isinstance(deadline, bool) or not isinstance(deadline, (int, float))
                or not math.isfinite(deadline)
                or isinstance(turns, bool) or not isinstance(turns, int) or turns < 0
                or isinstance(hops, bool) or not isinstance(hops, int) or hops < 0):
            raise NetworkBudgetExceeded(code="invalid_budget")
        budget = ExecutionBudget(
            min(float(deadline), now + self.limits.request_timeout),
            min(turns, self.limits.max_turns),
            min(hops, self.limits.max_hops - 1),
            raw.get("interaction_id", ""),
        )
        if budget.deadline_at <= now or budget.turns_remaining < 1:
            raise NetworkBudgetExceeded(code="interaction_budget")
        return budget

    @staticmethod
    def _deadline_for(timeout: float, maximum: float) -> float:
        if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                or not math.isfinite(timeout) or timeout <= 0):
            raise ValueError("timeout must be a finite positive number")
        return time.time() + min(float(timeout), maximum)

    def _verify_artifacts(self, project_id: str, refs: tuple[ArtifactRef, ...]):
        if self.artifact_store is not None:
            self.artifact_store.verify(project_id, refs)
        elif any(ArtifactStore.is_stored(ref) for ref in refs):
            raise PermissionError("project artifact store is not enrolled")

    async def publish_artifact(self, channel_id: str, path: Path, *, kind: str = "file",
                               media_type: str = "application/octet-stream", label: str = "") -> ArtifactRef:
        channel, _ = await self._channel(channel_id)
        if self.artifact_store is None:
            raise PermissionError("project artifact store is not enrolled")
        return self.artifact_store.publish(channel.metadata.labels["project_id"], path,
                                           kind=kind, media_type=media_type, label=label)

    async def read_artifact(self, channel_id: str, ref: ArtifactRef) -> bytes:
        channel, _ = await self._channel(channel_id)
        if self.artifact_store is None:
            raise PermissionError("project artifact store is not enrolled")
        return self.artifact_store.read(channel.metadata.labels["project_id"], ref)

    async def send(self, channel_id: str, text: str, *, operation_id: str,
                   artifact_refs: tuple[ArtifactRef, ...] = (),
                   _deadline_at: float | None = None, _network_context_id: str | None = None,
                   _inherit_context: bool = True) -> str:
        context = self._execution_context(_network_context_id, _inherit_context)
        budget = self._outbound_budget(_deadline_at, context)
        async with asyncio.timeout(budget.deadline_at - time.time()):
            if not isinstance(text, str) or not text.strip():
                raise ValueError("nonempty text required")
            if not isinstance(artifact_refs, (list, tuple)) or len(artifact_refs) > 16:
                raise ValueError("at most 16 typed artifact references are allowed")
            if any(not isinstance(ref, ArtifactRef) or ref.is_local_file
                   for ref in artifact_refs):
                raise ValueError("artifact references must be typed and must not expose local file paths")
            wire_refs = [ref.to_wire() for ref in artifact_refs]
            refs_json = json.dumps(wire_refs, sort_keys=True, separators=(",", ":"))
            if len(refs_json.encode("utf-8")) > 16 * 1024:
                raise ValueError("artifact reference metadata exceeds the size limit")
            channel, peer_id = await self._channel(channel_id)
            if not isinstance(operation_id, str) or not operation_id.strip():
                raise ValueError("nonempty operation_id required")
            self._verify_artifacts(channel.metadata.labels["project_id"], tuple(artifact_refs))
            peer = await self.hub_client.get_agent(peer_id)
            outbound_trace = context.trace if context is not None else ()
            if not outbound_trace:
                outbound_trace = (self.name,)
            elif self.name not in outbound_trace:
                outbound_trace = (*outbound_trace, self.name)
            if peer.name in outbound_trace:
                raise NetworkCycleError(f"network cycle detected: {peer.name} is already in the request ancestry")
            transport_id = uuid.uuid4().hex
            envelope = Envelope(channel_id=channel_id, sender_id=self.client.agent_id,
                                audience=[peer_id], event_type=EV_TEXT, event_data={
                "kind": "request", "text": text, "artifact_refs": wire_refs,
                "operation_id": operation_id, "trace": list(outbound_trace),
                "transport_id": transport_id,
                "budget": {
                    "deadline_at": budget.deadline_at,
                    "turns_remaining": budget.turns_remaining,
                    "hops_remaining": budget.hops_remaining,
                    "interaction_id": budget.interaction_id,
                },
            }, depth=0)
            context_id = network_execution_context_id(peer.name, channel.metadata.labels["project_id"],
                                                      channel_id, operation_id)
            interaction = (budget.interaction_id, budget.turns_remaining, budget.deadline_at) if context is None else None
            request_fingerprint = sha256(json.dumps(
                {"text": text, "artifact_refs": wire_refs}, sort_keys=True, separators=(",", ":"),
            ).encode()).hexdigest()
            self.admission.reserve_transport(context_id, transport_id, request_fingerprint, interaction)
            try:
                # Native ACK only proves acceptance by AG2, not terminal execution.
                return await self.client.send_envelope(envelope)
            except asyncio.CancelledError:
                if time.time() >= budget.deadline_at:
                    raise ExecutionUncertain("transport submission deadline expired; explicit operator reconciliation required") from None
                raise  # Caller cancellation also retains the reservation.
            except Exception as exc:  # health: allow BLE001 -- submission may have persisted before ACK failed; never resend or expose transport details
                raise ExecutionUncertain("transport submission uncertain; inspect history or reconcile before retrying") from exc

    async def ask(self, channel_id: str, text: str, *, operation_id: str,
                  artifact_refs: tuple[ArtifactRef, ...] = (), timeout: float = 300,
                  _network_context_id: str | None = None,
                  _inherit_context: bool = True) -> Message:
        context = self._execution_context(_network_context_id, _inherit_context)
        deadline_at = self._deadline_for(timeout, self.limits.request_timeout)
        if context is not None:
            deadline_at = min(deadline_at, context.budget.deadline_at)
        if len(self._waiters) >= self.limits.max_pending:
            raise NetworkBudgetExceeded(code="pending_capacity")
        if not isinstance(operation_id, str) or not operation_id.strip():
            raise ValueError("nonempty operation_id required")
        key = (channel_id, operation_id)
        if key in self._waiters:
            raise ValueError("operation already awaited")
        replies: asyncio.Queue[Message | None] = asyncio.Queue()
        self._waiters[key] = replies
        try:
            request_id = await self.send(channel_id, text, operation_id=operation_id,
                                         artifact_refs=artifact_refs,
                                         _deadline_at=deadline_at,
                                         _network_context_id=_network_context_id,
                                         _inherit_context=_inherit_context)
            try:
                async with asyncio.timeout(max(0.0, deadline_at - time.time())):
                    while True:
                        reply = await replies.get()
                        if reply is None:
                            raise ExecutionUncertain("network disconnected after submission; no automatic retry")
                        if reply.causation_id == request_id:
                            break
            except TimeoutError as exc:
                # Submission succeeded; a missing reply cannot prove absence of side effects.
                raise ExecutionUncertain(
                    "network reply deadline expired after submission; no automatic retry",
                ) from exc

            if reply.kind == "status":
                raise ExecutionUncertain(reply.text)
            if reply.kind == "rejected":
                raise NetworkBudgetExceeded(code=reply.admission_code)
            channel, _ = await self._channel(channel_id)
            self._verify_artifacts(channel.metadata.labels["project_id"], reply.artifact_refs)
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
            for envelope in wal:
                # A durable terminal receipt can clean up a crash after reply persistence
                # but before reservation release, even when its caller was offline.
                self._settle_transport_receipt(envelope)
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

    def _request_trace(self, data: dict[str, Any], peer_name: str) -> tuple[str, ...]:
        trace = data.get("trace", [])
        if (not isinstance(trace, list)
                or any(not isinstance(name, str) or not name.strip() for name in trace)
                or len(trace) != len(set(trace))):
            raise RequestNotAdmitted("invalid network request ancestry")
        if not trace:
            trace = [peer_name]
        elif peer_name not in trace:
            trace = [peer_name, *trace]
        if self.name in trace:
            raise RequestNotAdmitted("network cycle detected: recipient is already in the request ancestry")
        return (*trace, self.name)

    async def _execute_once(self, request: ExecutionRequest, budget: ExecutionBudget,
                            trace: tuple[str, ...]) -> ExecutionResult:
        result = self.ledger.cached(request)
        if result is not None:
            return result
        if self.executor is None:
            raise NetworkBudgetExceeded(code="executor_unavailable")
        validate_input = getattr(self.executor, "validate_input", None)
        if validate_input is not None:
            try:
                validate_input(request)
            except (ValueError, OSError) as exc:
                raise RequestNotAdmitted("artifact input refused before execution") from exc
        context = ExecutionTaskContext(
            network_context_id=network_execution_context_id(
                request.profile, request.project_id, request.channel_id, request.operation_id,
            ),
            trace=trace,
            budget=ExecutionBudget(
                budget.deadline_at, budget.turns_remaining - 1, budget.hops_remaining, budget.interaction_id,
            ),
        )
        self.admission.acquire(self.name, context.network_context_id, budget.interaction_id)
        try:
            self.ledger.admit(request)
            self._held_request = replace(request, _task_context=context)
            self.ledger.hold(self._held_request)
        except BaseException:
            # Executor has not been invoked; this execution lease is safe to release.
            self.admission.release(self.name, context.network_context_id)
            self._held_request = self.ledger.held(self.name)
            self._active_context = self._held_request._task_context if self._held_request else None
            raise
        self._active_context = context
        try:
            async with asyncio.timeout(budget.deadline_at - time.time()):
                result = await self.executor(self._held_request)
        except ExecutionTerminated:
            self.ledger.terminate(context.network_context_id)
            self._release_execution(self._held_request)
            raise
        except NetworkBudgetExceeded as exc:
            self.ledger.hold(self._held_request)
            raise ExecutionUncertain("nested budget exhausted after operation admission") from exc
        except BaseException:
            # Cancellation/deadline is not proof that the external HTTP Run stopped.
            self.ledger.hold(self._held_request)
            raise
        try:
            self._finish_execution(self._held_request, result)
        except (ValueError, OSError) as exc:
            self.ledger.terminate(context.network_context_id)
            self._release_execution(self._held_request)
            raise ExecutionTerminated("completed execution returned invalid artifact output") from exc
        return result

    def _finish_execution(self, request: ExecutionRequest, result: ExecutionResult):
        refs = _artifact_refs({"artifact_refs": [ref.to_wire() for ref in result.artifact_refs]})
        self._verify_artifacts(request.project_id, refs)
        self.ledger.advance_session(request.profile, request.project_id, request.channel_id, result.session_id)
        self.ledger.finish(request, result)
        self._release_execution(request)

    def _release_execution(self, request: ExecutionRequest):
        self.ledger.release(self.name)
        if request._task_context is not None:
            self.admission.release(self.name, request._task_context.network_context_id)
        self._held_request = None
        self._active_context = None

    async def reconcile(self, network_context_id: str) -> ExecutionResult:
        """Operator-only readback: never POST or resend an uncertain operation."""
        async with self._run_lock:
            context = self._execution_context(network_context_id, False)
            request = self._held_request
            if context is None or request is None:
                raise ExecutionUncertain("no held operation to reconcile")
            reconcile = getattr(self.executor, "reconcile", None)
            if reconcile is None:
                raise ExecutionUncertain("executor has no terminal readback seam")
            try:
                result = await reconcile(request)
            except ExecutionTerminated:
                # Keep the operation ledger unsettled: terminal failure is not a result,
                # and must never turn a retry into a fresh external Run.
                self.ledger.terminate(context.network_context_id)
                self._release_execution(request)
                self.admission.reconcile_transport(context.network_context_id)
                raise
            self._finish_execution(request, result)
            self.admission.reconcile_transport(context.network_context_id)
            return result

    async def _process_request(self, envelope: Envelope, channel: Channel, peer_id: str) -> None:
        data = envelope.event_data
        operation_id = data.get("operation_id")
        text = data.get("text")
        if not isinstance(operation_id, str) or not operation_id.strip():
            return
        if not isinstance(text, str) or not text.strip():
            return
        if self._pending_inbound >= self.limits.max_pending:
            cause = NetworkBudgetExceeded(code="pending_capacity")
            await channel.send("network request capacity reached", audience=[peer_id],
                causation_id=envelope.envelope_id, event_data={
                    "kind": "rejected", "operation_id": operation_id,
                    "text": f"{cause.summary}; {cause.remediation}", "admission": cause.public_details(),
                    "transport_id": data.get("transport_id", ""),
                }, depth=envelope.depth)
            self.admission.release_transport(data.get("transport_id", ""))
            return
        self._pending_inbound += 1
        try:
            async with self._run_lock:
                try:
                    project_id = channel.metadata.labels["project_id"]
                    try:
                        artifact_refs = _artifact_refs(data)
                        self._verify_artifacts(project_id, artifact_refs)
                    except (ValueError, OSError) as exc:
                        raise RequestNotAdmitted("invalid artifact references") from exc
                    session_origin_id, session_current_id = self.ledger.session(
                        self.name, project_id, envelope.channel_id,
                    )
                    request = ExecutionRequest(
                        self.name, project_id, envelope.channel_id, operation_id, text,
                        session_origin_id, session_current_id, artifact_refs=artifact_refs,
                    )
                    wal = await self.hub_client.read_wal(envelope.channel_id)
                    if envelope.envelope_id in _answered_request_ids(wal, self.client.agent_id):
                        return
                    peer_name = (await self.hub_client.get_agent(peer_id)).name
                    trace = self._request_trace(data, peer_name)
                    result = self.ledger.cached(request)
                    if result is None:
                        if self._held_request is not None:
                            raise NetworkBudgetExceeded(code="profile_held")
                        budget = self._inbound_budget(data)
                        request = ExecutionRequest(
                            self.name, project_id, envelope.channel_id, operation_id, text,
                            session_origin_id, session_current_id, budget.deadline_at,
                            budget.turns_remaining, artifact_refs=artifact_refs,
                        )
                        result = await self._execute_once(request, budget, trace)
                    try:
                        refs = _artifact_refs({"artifact_refs": [ref.to_wire() for ref in result.artifact_refs]})
                        self._verify_artifacts(project_id, refs)
                    except (ValueError, OSError) as exc:
                        raise ExecutionTerminated("cached artifact output failed verification") from exc
                    reply_data: dict[str, Any] = {
                        "kind": "reply", "text": result.text,
                        "session_id": result.session_id, "run_id": result.run_id,
                        "artifact_refs": [ref.to_wire() for ref in result.artifact_refs],
                    }
                except NetworkBudgetExceeded as exc:
                    reply_data = {
                        "kind": "rejected",
                        "text": f"{exc.summary}; {exc.remediation}",
                        "admission": exc.public_details(),
                    }
                except ExecutionTerminated:
                    reply_data = {"kind": "status", "text": "terminal execution or artifact verification failed; no automatic re-execution", "terminal": True}
                except RequestNotAdmitted:
                    reply_data = {"kind": "status", "text": "request refused before execution; correct the input under a new operation ID", "terminal": True}
                except Exception as exc:  # health: allow BLE001 -- external executor boundary: ACK held work instead of native NACK/replay; exception text may contain secrets
                    reply_data = {"kind": "status", "text": f"execution unsettled or refused ({type(exc).__name__}); explicit operator reconciliation required"}
                context_id = network_execution_context_id(self.name, project_id, envelope.channel_id, operation_id)
                terminal = (reply_data["kind"] in {"reply", "rejected"}
                            or reply_data.get("terminal") is True or self.ledger.is_terminated(context_id))
                reply_data["terminal"] = terminal
                reply_data["transport_id"] = data.get("transport_id", "")
                reply_data["operation_id"] = operation_id
                await channel.send(reply_data["text"], audience=[peer_id],
                    causation_id=envelope.envelope_id, event_data=reply_data, depth=envelope.depth)
                if terminal:
                    self.admission.release_transport(data.get("transport_id", ""))
        finally:
            self._pending_inbound -= 1

    async def history(self, channel_id: str) -> list[Message]:
        channel, _ = await self._channel(channel_id)
        project_id = channel.metadata.labels["project_id"]
        envelopes = await self.hub_client.read_wal(channel_id)
        messages = [_message(e) for e in envelopes
                    if e.event_type == EV_TEXT and e.event_data.get("kind") in {"request", "reply", "status", "rejected"}]
        messages.extend(Message(
            envelope_id=f"local-recovery:{source_channel}:{request_id}", sender_id=self.client.agent_id,
            kind="status", text=f"Unanswered request is stranded in terminal AG2 channel {source_channel}; "
            "it was not replayed automatically. Operator reconciliation is required.",
            operation_id=operation_id, causation_id=request_id,
        ) for source_channel, request_id, operation_id
          in self.ledger.terminal_requests(self.name, project_id))
        return messages

    def _settle_transport_receipt(self, envelope: Envelope):
        data = envelope.event_data
        if (envelope.event_type == EV_TEXT and envelope.causation_id
                and (data.get("kind") in {"reply", "rejected"}
                     or (data.get("kind") == "status" and data.get("terminal") is True))):
            transport_id = data.get("transport_id")
            if isinstance(transport_id, str):
                self.admission.release_transport(transport_id)

    async def _on_envelope(self, envelope: Envelope):
        if envelope.event_type == EV_CHANNEL_INVITE:
            metadata = await self.hub_client.get_channel(envelope.channel_id)
            inviter = await self.hub_client.get_agent(metadata.creator_id)
            project_id = metadata.labels.get("project_id")
            allowed = (isinstance(project_id, str) and bool(project_id.strip())
                       and inviter.name in self._peers_for_project(project_id)
                       and metadata.labels.get("protocol") == "hermes-tracer-v1")
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
        if kind in {"reply", "status", "rejected"}:
            self._settle_transport_receipt(envelope)
            replies = self._waiters.get((envelope.channel_id, envelope.event_data.get("operation_id")))
            if replies is not None:
                replies.put_nowait(_message(envelope))
            return  # Replies never trigger another runtime turn.
        if kind == "request":
            await self._process_request(envelope, channel, peer_id)
