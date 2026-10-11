"""Values crossing the public agent_network/executor boundary."""
from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass(frozen=True)
class ExecutionRequest:
    profile: str
    project_id: str
    channel_id: str
    operation_id: str
    text: str
    session_origin_id: str = ""
    session_current_id: str = ""


@dataclass(frozen=True)
class ExecutionResult:
    text: str
    session_id: str
    run_id: str


Executor = Callable[[ExecutionRequest], Awaitable[ExecutionResult]]


@dataclass(frozen=True)
class Message:
    envelope_id: str
    sender_id: str
    kind: str
    text: str
    operation_id: str
    causation_id: str | None
    session_id: str = ""
    run_id: str = ""

    @property
    def request_id(self) -> str | None:
        return self.causation_id


@dataclass(frozen=True)
class Peer:
    name: str
    agent_id: str


class ExecutionUncertain(RuntimeError):
    """No automatic retry: the run may already have executed side effects."""
