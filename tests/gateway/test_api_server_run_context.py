"""Per-run run context is validated and bound independently from session task IDs."""
import asyncio
from unittest.mock import MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from gateway.config import PlatformConfig
from gateway.platforms.api_server import APIServerAdapter
from gateway.platforms.api_server_run_idempotency import RunIdempotencyStore


def _app(adapter: APIServerAdapter) -> web.Application:
    app = web.Application()
    app.router.add_post("/v1/runs", adapter._handle_runs)
    app.router.add_get("/v1/runs/{run_id}", adapter._handle_get_run)
    return app


@pytest.mark.asyncio
async def test_run_context_id_is_bound_to_one_run_and_restored(tmp_path):
    adapter = APIServerAdapter(PlatformConfig(enabled=True, extra={}))
    adapter._run_idempotency_store.close()
    adapter._run_idempotency_store = RunIdempotencyStore(str(tmp_path / "run-context.sqlite"))
    context_id = "a" * 64
    observed_contexts = []

    async with TestClient(TestServer(_app(adapter))) as client:
        mismatch = await client.post(
            "/v1/runs", json={"input": "invalid"},
            headers={"Idempotency-Key": context_id, "X-Hermes-Run-Context-Id": "b" * 64},
        )
        assert mismatch.status == 400
        with patch.object(adapter, "_create_agent") as create:
            agent = MagicMock()
            agent._active_run_context_id = "previous-context"

            def run(**_kwargs):
                observed_contexts.append(agent._active_run_context_id)
                return {"final_response": "done"}

            agent.run_conversation.side_effect = run
            agent.session_prompt_tokens = agent.session_completion_tokens = agent.session_total_tokens = 0
            create.return_value = agent
            accepted = await client.post(
                "/v1/runs", json={"input": "network request"},
                headers={"Idempotency-Key": context_id, "X-Hermes-Run-Context-Id": context_id},
            )
            assert accepted.status == 202
            run_id = (await accepted.json())["run_id"]
            for _ in range(40):
                status_response = await client.get(f"/v1/runs/{run_id}")
                if (await status_response.json())["status"] == "completed":
                    break
                await asyncio.sleep(0.05)

    assert observed_contexts == [context_id]
    assert agent._active_run_context_id == "previous-context"
