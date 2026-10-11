"""A durable native AG2 hub; no model agent, provider or Hermes imports."""
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
import fcntl

from ag2.knowledge import DiskKnowledgeStore
from ag2.network import ApiKeyAuth, AuthRegistry, Hub, serve_ws


@dataclass(frozen=True)
class HubAddress:
    url: str


@asynccontextmanager
async def network_hub(root: Path, keys: dict[str, str], *, port: int = 0):
    """Authenticated loopback WS server with one owner of the disk store.

    This POSIX lock excludes a second cooperating hub process. Native AG2
    JSONL persistence is durable across clean restart, not crash-atomic.
    """
    if not keys or any(not name or not token for name, token in keys.items()):
        raise ValueError("explicit nonempty identity credentials required")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    with (root / ".owner.lock").open("a") as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        hub = await Hub.open(DiskKnowledgeStore(root), auth=AuthRegistry([ApiKeyAuth(keys)]),
                             allow_remote_agent_registration=False)
        try:
            async with serve_ws(hub, "127.0.0.1", port) as server:
                yield HubAddress(f"ws://127.0.0.1:{next(iter(server.sockets)).getsockname()[1]}")
        finally:
            await hub.close()
