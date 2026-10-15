"""Behavioral contract for authenticated, profile-scoped Run discovery."""

from unittest.mock import MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from gateway.config import PlatformConfig
from gateway.platforms.api_server import APIServerAdapter, _api_request_profile
from gateway.platforms.api_server_runs import _RunStream
from gateway.platforms.api_server import cors_middleware, security_headers_middleware


def _adapter(api_key: str = "") -> APIServerAdapter:
    extra = {"key": api_key} if api_key else {}
    return APIServerAdapter(PlatformConfig(enabled=True, extra=extra))


def _app(adapter: APIServerAdapter) -> web.Application:
    from gateway.platforms.api_server_runs import _http_routes

    app = web.Application(middlewares=[m for m in (cors_middleware, security_headers_middleware) if m])
    app["api_server_adapter"] = adapter
    run_list = next(handler for method, path, handler in _http_routes(adapter)
                    if method == "GET" and path == "/v1/runs")
    app.router.add_post("/v1/runs", adapter._handle_runs)
    app.router.add_get("/v1/runs", run_list)
    app.router.add_get("/v1/runs/{run_id}", adapter._handle_get_run)
    app.router.add_get("/v1/capabilities", adapter._handle_capabilities)
    return app


def _scope(adapter: APIServerAdapter) -> str:
    request = MagicMock()
    request.headers = {}
    return adapter._run_idempotency_scope(request)


def _add_run(adapter: APIServerAdapter, run_id: str, session_id: str, *, status="queued", scope=None):
    adapter._set_run_status(run_id, status, session_id=session_id, output="private transcript", error="private error")
    getattr(adapter, "_run_owners")[run_id] = scope or _scope(adapter)
    getattr(adapter, "_run_streams")[run_id] = _RunStream()


@pytest.mark.asyncio
async def test_capabilities_advertise_exact_session_run_discovery():
    adapter = _adapter("profile-secret")
    async with TestClient(TestServer(_app(adapter))) as client:
        response = await client.get("/v1/capabilities", headers={"Authorization": "Bearer profile-secret"})
        body = await response.json()

    assert response.status == 200
    assert body["features"]["run_list_by_session"] is True
    assert body["endpoints"]["run_list_by_session"] == {
        "method": "GET", "path": "/v1/runs?session_id={session_id}"}


@pytest.mark.asyncio
async def test_list_runs_returns_only_safe_status_for_exact_owned_session():
    adapter = _adapter()
    session_id = "acceptance-session"
    _add_run(adapter, "run_queued", session_id)
    _add_run(adapter, "run_other_session", "unrelated-session")

    async with TestClient(TestServer(_app(adapter))) as client:
        response = await client.get("/v1/runs", params={"session_id": session_id})
        body = await response.json()

    assert response.status == 200
    assert body["object"] == "list"
    assert body["session_id"] == session_id
    assert [row["run_id"] for row in body["data"]] == ["run_queued"]
    assert body["data"][0]["status"] == "queued"
    assert "output" not in body["data"][0]
    assert "error" not in body["data"][0]


@pytest.mark.asyncio
async def test_list_runs_observes_a_newly_admitted_run_without_its_output():
    adapter = _adapter()
    app = _app(adapter)

    async with TestClient(TestServer(app)) as client:
        agent = MagicMock()
        agent.run_conversation.return_value = {"final_response": "private response"}
        agent.session_prompt_tokens = agent.session_completion_tokens = agent.session_total_tokens = 0
        with patch.object(adapter, "_create_agent", return_value=agent):
            started = await client.post("/v1/runs", json={"input": "private prompt", "session_id": "acceptance-session"})
            run_id = (await started.json())["run_id"]
            response = await client.get("/v1/runs", params={"session_id": "acceptance-session"})
            body = await response.json()

    assert started.status == 202
    assert response.status == 200
    row = next(row for row in body["data"] if row["run_id"] == run_id)
    assert row["status"] in {"queued", "running", "completed"}
    assert "output" not in row
    assert "error" not in row


@pytest.mark.asyncio
async def test_list_runs_requires_exact_session_and_bounded_pagination():
    adapter = _adapter()
    _add_run(adapter, "run_one", "acceptance-session")
    _add_run(adapter, "run_two", "acceptance-session")

    async with TestClient(TestServer(_app(adapter))) as client:
        missing = await client.get("/v1/runs")
        oversized = await client.get("/v1/runs", params={"session_id": "acceptance-session", "limit": 1000})
        first = await client.get("/v1/runs", params={"session_id": "acceptance-session", "limit": 1})
        first_body = await first.json()
        second = await client.get("/v1/runs", params={"session_id": "acceptance-session", "limit": 1, "offset": 1})
        second_body = await second.json()

    assert missing.status == 400
    assert oversized.status == 400
    assert first_body["data"][0]["run_id"] == "run_one"
    assert second_body["data"][0]["run_id"] == "run_two"


@pytest.mark.asyncio
async def test_list_runs_requires_auth_and_hides_other_profile_runs():
    adapter = _adapter("profile-secret")
    _add_run(adapter, "run_coding", "acceptance-session")
    token = _api_request_profile.set("architect")
    try:
        other_scope = _scope(adapter)
    finally:
        _api_request_profile.reset(token)
    _add_run(adapter, "run_architect", "acceptance-session", scope=other_scope)

    async with TestClient(TestServer(_app(adapter))) as client:
        unauthorized = await client.get("/v1/runs", params={"session_id": "acceptance-session"})
        authorized = await client.get("/v1/runs", params={"session_id": "acceptance-session"},
                                      headers={"Authorization": "Bearer profile-secret"})
        body = await authorized.json()

    assert unauthorized.status == 401
    assert authorized.status == 200
    assert [row["run_id"] for row in body["data"]] == ["run_coding"]
