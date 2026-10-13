"""Acceptance readiness is fail-closed; fixtures are NOT live Hermes receipts."""
import asyncio

from aiohttp import web

import pytest
from hermes_ag2_network.live_acceptance import RuntimeProbe


@pytest.mark.parametrize("architect_response", [
    {"sessions": []}, {"error": "private diagnostic"},
])
def test_both_profiles_must_authenticate_and_private_session_fields_are_not_evidence(architect_response):
    async def scenario():
        async def sessions(request):
            profile = request.match_info["profile"]
            assert request.headers["Authorization"] == f"Bearer {profile}-credential"
            assert request.query["limit"] == "1"
            body = {"sessions": [{"id": "existing-user-session", "title": "private-title"}]} if profile == "coding" else architect_response
            return web.json_response(body)

        app = web.Application()
        app.router.add_get("/p/{profile}/api/sessions", sessions)
        manager = web.AppRunner(app)
        await manager.setup()
        site = web.TCPSite(manager, "127.0.0.1", 0)
        await site.start()
        try:
            port = manager.addresses[0][1]
            receipt = await RuntimeProbe(f"http://127.0.0.1:{port}", {
                "coding": "coding-credential", "architect": "architect-credential",
            }).readiness()
            assert receipt["ready"] is ("sessions" in architect_response)
            assert receipt["live_scenario_completed"] is False
            assert receipt["mutations"] == []
            for private in ("private-title", "existing-user-session", "private diagnostic", "coding-credential"):
                assert private not in str(receipt)
        finally:
            await manager.cleanup()
    asyncio.run(scenario())


def test_unreachable_runtime_cannot_be_reported_as_live_acceptance():
    async def scenario():
        probe = RuntimeProbe("http://127.0.0.1:1", {"coding": "fixture-secret", "architect": "other-secret"})
        receipt = await probe.readiness()
        assert receipt["ready"] is False
        assert receipt["live_scenario_completed"] is False
        assert receipt["blockers"]
        assert "fixture-secret" not in str(receipt)
        assert "other-secret" not in str(receipt)
    asyncio.run(scenario())
