"""Values crossing the public agent_network/executor boundary."""
from dataclasses import dataclass, field
from hashlib import sha256
import json
from math import isfinite
from typing import Awaitable, Callable

from .artifacts import ArtifactRef


def network_execution_context_id(profile: str, project_id: str, channel_id: str, operation_id: str) -> str:
    """Stable opaque ID binding one admitted network operation to its Hermes API run."""
    identity = json.dumps([profile, project_id, channel_id, operation_id], separators=(",", ":"))
    return sha256(identity.encode()).hexdigest()


@dataclass(frozen=True)
class NetworkLimits:
    """Bound nested work, queued requests, and per-operation wall-clock time."""

    max_hops: int = 8
    max_turns: int = 16
    max_pending: int = 16
    request_timeout: float = 300.0
    max_active: int = 16

    def __post_init__(self):
        maximums = {"max_hops": 16, "max_turns": 32, "max_pending": 64, "max_active": 64}
        for name, maximum in maximums.items():
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= maximum:
                raise ValueError(f"{name} must be between 1 and {maximum}")
        if (isinstance(self.request_timeout, bool) or not isinstance(self.request_timeout, (int, float))
                or not isfinite(self.request_timeout) or not 0 < self.request_timeout <= 300):
            raise ValueError("request_timeout must be greater than zero and at most 300 seconds")


@dataclass
class ExecutionBudget:
    deadline_at: float
    turns_remaining: int
    hops_remaining: int
    interaction_id: str = ""


@dataclass
class ExecutionTaskContext:
    """Opaque network operation identity and shared nested-call budget; never serialized to AG2."""

    network_context_id: str
    trace: tuple[str, ...]
    budget: ExecutionBudget
    run_id: str = ""


@dataclass(frozen=True)
class ExecutionRequest:
    profile: str
    project_id: str
    channel_id: str
    operation_id: str
    text: str
    session_origin_id: str = ""
    session_current_id: str = ""
    deadline_at: float = 0.0
    turns_remaining: int = 0
    artifact_refs: tuple[ArtifactRef, ...] = ()
    _task_context: ExecutionTaskContext | None = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class ExecutionResult:
    text: str
    session_id: str
    run_id: str
    artifact_refs: tuple[ArtifactRef, ...] = ()


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
    admission_code: str = "budget"
    artifact_refs: tuple[ArtifactRef, ...] = ()

    @property
    def request_id(self) -> str | None:
        return self.causation_id


@dataclass(frozen=True)
class Peer:
    name: str
    agent_id: str


class NetworkBudgetExceeded(RuntimeError):
    """Safe allowlisted causes: never publish arbitrary executor exception text."""

    CAUSES = {
        "budget": ("Network request budget exceeded", "Inspect configured limits before retrying."),
        "global_capacity": ("Global controlled network capacity is full", "Wait for terminal completion or reconcile held work; retry the same operation ID."),
        "pending_capacity": ("Shared pending transport capacity is full", "Wait for a terminal receipt or reconcile held work; retry the same operation ID."),
        "profile_held": ("Profile has active or uncertain work", "Wait for completion or explicitly reconcile the owning profile's held Run."),
        "interaction_budget": ("Shared interaction budget is unknown, expired or exhausted", "Start a new bounded interaction only after settling prior work."),
        "nested_budget": ("Nested hop or turn budget is exhausted", "Finish the current interaction; do not retry this descendant."),
        "deadline": ("Network request deadline is invalid or expired", "Supply a valid deadline within the current interaction budget."),
        "invalid_budget": ("Network request budget is invalid", "Correct the budget metadata before submitting."),
        "stale_context": ("Network execution context is unknown or stale", "Use the current owning Run context; never reuse a settled context."),
        "executor_unavailable": ("No executor is enrolled for this participant", "Enroll the owning Hermes executor before retrying the same operation ID."),
    }

    def __init__(self, message: str = "", *, code: str = "budget"):
        self.code = code if isinstance(code, str) and code in self.CAUSES else "budget"
        self.summary, self.remediation = self.CAUSES[self.code]
        super().__init__(message or f"{self.summary}; {self.remediation}")

    def public_details(self) -> dict[str, str]:
        return {"code": self.code, "cause": self.summary, "remediation": self.remediation}


class NetworkCycleError(ValueError):
    """A request would re-enter a specialist already waiting in its ancestry."""


class ExecutionUncertain(RuntimeError):
    """No automatic retry: the run may already have executed side effects."""


class RequestNotAdmitted(ValueError):
    """Bridge validation proved this delivery did not invoke an executor."""


class ExecutionTerminated(ExecutionUncertain):
    """Authenticated readback proved terminal, but no successful result is available."""
