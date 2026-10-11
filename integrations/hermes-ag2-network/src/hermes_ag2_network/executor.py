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

    async def _resolve_session_tip(self, origin_id: str) -> str:
        response = await self.http.get(f"api/sessions/{origin_id}/messages", params={"limit": 0})
        response.raise_for_status()
        tip_id = response.json().get("session_id")
        if not isinstance(tip_id, str) or not tip_id:
            raise ExecutionUncertain("Hermes did not resolve a canonical session tip")
        return tip_id

    async def _execute(self, request: ExecutionRequest) -> ExecutionResult:
        origin_id = request.session_origin_id or request.session_current_id
        if not origin_id:
            raise ValueError("durable Hermes session lineage required")
        response = await self.http.post("api/sessions", json={
            "id": origin_id, "source": "api_server",
            "title": f"AG2 {request.channel_id[:12]}",
        })
        if response.status_code != 409:
            response.raise_for_status()
        else:
            error = response.json().get("error", {})
            if not isinstance(error, dict) or error.get("code") != "session_exists":
                response.raise_for_status()
        # The stored current ID may be stale if Hermes rotated while the
        # bridge was down. Resolve from the stable origin first, then verify
        # the canonical current target before sending a new turn.
        resolved_session_id = await self._resolve_session_tip(origin_id)
        session = await self.http.get(f"api/sessions/{resolved_session_id}")
        session.raise_for_status()
        if session.json().get("session", {}).get("id") != resolved_session_id:
            raise ExecutionUncertain("Hermes session identity mismatch")
        run_response = await self.http.post("v1/runs", headers={
            "Idempotency-Key": request.operation_id,
            "X-Hermes-Session-Key": "ag2:" + origin_id,
        }, json={"session_id": resolved_session_id, "input": request.text})
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
                tip_id = await self._resolve_session_tip(origin_id)
                return ExecutionResult(output, tip_id, run_id)
            if status in {"failed", "cancelled", "interrupted"}:
                raise ExecutionUncertain("Hermes run ended without completion; no automatic retry")
            await asyncio.sleep(self.poll_interval)
