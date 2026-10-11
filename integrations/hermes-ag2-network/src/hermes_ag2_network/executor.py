"""Authenticated HTTP executor: provider/model/tool resolution stays in Hermes."""
import asyncio
import json
import re
from urllib.parse import quote, urlsplit
import uuid

import httpx

from .types import ExecutionRequest, ExecutionResult, ExecutionUncertain


class HermesHTTPExecutor:
    def __init__(self, url: str, *, profile: str, token: str, deadline: float = 300,
                 poll_interval: float = 0.2):
        parsed = urlsplit(url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("API URL must not contain credentials/query/fragment")
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}):
            raise ValueError("HTTP credentials require TLS or loopback")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", profile) or not token:
            raise ValueError("valid enrolled profile and credential required")
        self.profile = profile
        self.deadline = deadline
        self.poll_interval = poll_interval
        self.http = httpx.AsyncClient(base_url=f"{url.rstrip('/')}/p/{quote(profile)}/",
            headers={"Authorization": f"Bearer {token}"}, timeout=15, follow_redirects=False,
            trust_env=False)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.http.aclose()

    async def __call__(self, request: ExecutionRequest) -> ExecutionResult:
        if request.profile != self.profile:
            raise PermissionError("executor cannot execute another profile")
        try:
            async with asyncio.timeout(self.deadline):
                return await self._execute(request)
        except (httpx.HTTPError, TimeoutError) as exc:
            # Do not echo response bodies or secrets in the exception; do not
            # retry POST after a lost response or automatically stop live work.
            raise ExecutionUncertain("Hermes API execution unsettled; no automatic retry") from exc

    async def _execute(self, request: ExecutionRequest) -> ExecutionResult:
        identity = json.dumps([request.profile, request.channel_id, request.operation_id], separators=(",", ":"))
        session_id = "ag2-" + uuid.uuid5(uuid.NAMESPACE_URL, identity).hex
        response = await self.http.post("api/sessions", json={
            "id": session_id, "source": "api_server", "title": "AG2 network tracer",
        })
        if response.status_code != 409:
            response.raise_for_status()
        else:
            error = response.json().get("error", {})
            if not isinstance(error, dict) or error.get("code") != "session_exists":
                response.raise_for_status()
        # Verify the exact new target, also on a deterministic create conflict.
        session = await self.http.get(f"api/sessions/{session_id}")
        session.raise_for_status()
        if session.json().get("session", {}).get("id") != session_id:
            raise ExecutionUncertain("Hermes session identity mismatch")
        run_response = await self.http.post("v1/runs", headers={
            "Idempotency-Key": request.operation_id,
            "X-Hermes-Session-Key": "ag2:" + session_id,
        }, json={"session_id": session_id, "input": request.text})
        run_response.raise_for_status()
        run_id = run_response.json()["run_id"]
        while True:
            response = await self.http.get(f"v1/runs/{quote(run_id, safe='')}")
            response.raise_for_status()
            run = response.json()
            status = run["status"]
            if status == "completed":
                if run.get("completed") is False or run.get("partial") or run.get("interrupted"):
                    raise ExecutionUncertain("Hermes returned an incomplete terminal run")
                output = run.get("output")
                if not isinstance(output, str):
                    raise ExecutionUncertain("Hermes completed without textual output")
                return ExecutionResult(output, run.get("session_id") or session_id, run_id)
            if status in {"failed", "cancelled", "interrupted"}:
                raise ExecutionUncertain("Hermes run ended without completion; no automatic retry")
            await asyncio.sleep(self.poll_interval)
