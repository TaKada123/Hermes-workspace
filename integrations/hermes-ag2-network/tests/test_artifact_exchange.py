"""Verified content through real authenticated plugin HTTP and native AG2 seams."""
import asyncio
from pathlib import Path

import httpx
import pytest

from hermes_ag2_network import ExecutionResult, ExecutionUncertain, Network, network_hub
from hermes_ag2_network.artifacts import ArtifactStore, ArtifactKind, ArtifactRef
from hermes_ag2_network.tool_api import ToolAPI


@pytest.mark.parametrize("kind", [ArtifactKind.FILE, ArtifactKind.CHECK_REPORT, ArtifactKind.GIT_REFERENCE,
                                  ArtifactKind.RESULT, ArtifactKind.ERROR, ArtifactKind.STATUS])
def test_project_content_and_typed_output_survive_restart(tmp_path: Path, kind: ArtifactKind):
    async def scenario():
        approved = tmp_path / "approved"
        approved.mkdir()
        document = approved / "checks.txt"
        document.write_bytes(b"3 passed\n")
        store = ArtifactStore(tmp_path / "store", project_roots={"project": (approved,)}, max_bytes=64)
        output_ref = store.publish("project", document, kind=kind.value, media_type="text/plain")

        async def specialist(request):
            assert store.read(request.project_id, request.artifact_refs[0]) == b"3 passed\n"
            return ExecutionResult("Verified", "session", "run", artifact_refs=(output_ref,))

        channel = ""
        for restart in (False, True):
            async with network_hub(tmp_path / "hub", {"caller": "a", "architect": "b"}) as hub:
                async with Network.connect(hub.url, name="architect", token="b", allowed_peers={"caller"},
                                           executor=specialist, ledger_path=tmp_path / "architect.sqlite",
                                           artifact_store=store):
                    async with Network.connect(hub.url, name="caller", token="a", allowed_peers={"architect"},
                                               ledger_path=tmp_path / "caller.sqlite", artifact_store=store) as caller:
                        channel = await caller.open(peer="architect", project_id="project")
                        async with ToolAPI(caller, "tool-secret", port=0) as api:
                            async with httpx.AsyncClient(base_url=api.url, headers={
                                "Authorization": "Bearer tool-secret", "X-Hermes-Profile": "caller",
                            }) as http:
                                published = await http.post("/v1/artifacts/publish", json={
                                    "channel_id": channel, "path": str(document), "kind": kind.value,
                                    "media_type": "text/plain",
                                })
                                assert published.status_code == 200
                                ref = published.json()["result"]
                                assert ref["uri"].startswith("urn:hermes-artifact:")
                                assert str(approved) not in str(ref)
                                reply = await http.post("/v1/ask", json={"channel_id": channel, "text": "Check",
                                    "operation_id": "once", "artifact_refs": [ref], "timeout_seconds": 5})
                                assert reply.status_code == 200
                                assert reply.json()["result"]["artifact_refs"] == [ref]
                                consumed = await http.post("/v1/artifacts/read", json={"channel_id": channel, "artifact_ref": ref})
                                assert consumed.json()["result"]["text"] == "3 passed\n"
                        if restart:
                            history = await caller.history(channel)
                            assert all(message.artifact_refs == (output_ref,) for message in history)
    asyncio.run(scenario())


@pytest.mark.parametrize("unsafe", ["oversize", "outside", "private", "private_grant", "file_link", "directory_link"])
def test_tool_publish_rejects_unapproved_large_private_and_symlink_payloads(tmp_path: Path, unsafe: str):
    async def scenario():
        approved = tmp_path / "approved"
        approved.mkdir()
        safe = approved / "safe.txt"
        safe.write_text("ok")
        large = approved / "large"
        large.write_bytes(b"x" * 65)
        outside = tmp_path / "private.txt"
        outside.write_text("private")
        private = approved / ".hermes" / "memory.db"
        private.parent.mkdir()
        private.write_text("private")
        personal = approved / "personal" / "data"
        personal.parent.mkdir()
        personal.write_text("private")
        file_link = approved / "file-link"
        file_link.symlink_to(safe)
        directory_link = approved / "directory-link"
        directory_link.symlink_to(approved, target_is_directory=True)
        candidate = {"oversize": large, "outside": outside, "private": private,
                     "private_grant": personal,
                     "file_link": file_link, "directory_link": directory_link / "safe.txt"}[unsafe]
        store = ArtifactStore(tmp_path / "store", project_roots={"project": (approved,)}, max_bytes=64,
                              private_roots=(personal.parent,))
        async with network_hub(tmp_path / "hub", {"caller": "a", "architect": "b"}) as hub:
            async with Network.connect(hub.url, name="architect", token="b", allowed_peers={"caller"},
                                       ledger_path=tmp_path / "architect.sqlite"):
                async with Network.connect(hub.url, name="caller", token="a", allowed_peers={"architect"},
                                           ledger_path=tmp_path / "caller.sqlite", artifact_store=store) as caller:
                    channel = await caller.open(peer="architect", project_id="project")
                    async with ToolAPI(caller, "tool-secret", port=0) as api:
                        async with httpx.AsyncClient(base_url=api.url, headers={
                            "Authorization": "Bearer tool-secret", "X-Hermes-Profile": "caller",
                        }) as http:
                            response = await http.post("/v1/artifacts/publish", json={"channel_id": channel, "path": str(candidate)})
                            assert response.status_code in {400, 403}
                            assert str(candidate) not in response.text
                            assert await caller.history(channel) == []
    asyncio.run(scenario())


@pytest.mark.parametrize("tamper", ["hash", "oversize", "symlink"])
def test_receiver_verifies_again_before_execution_and_private_project_cannot_consume(tmp_path: Path, tamper: str):
    async def scenario():
        approved = tmp_path / "approved"
        approved.mkdir()
        document = approved / "checks.txt"
        document.write_bytes(b"verified")
        sender_store = ArtifactStore(tmp_path / "sender-store", project_roots={"project": (approved,)}, max_bytes=64)
        receiver_store = ArtifactStore(tmp_path / "receiver-store", project_roots={"project": (approved,)}, max_bytes=64)
        ref = sender_store.publish("project", document, media_type="text/plain")
        receiver_store.publish("project", document, media_type="text/plain")
        consumed = []

        async def specialist(request):
            consumed.append(receiver_store.read(request.project_id, request.artifact_refs[0]))
            return ExecutionResult("Read", "session", "run")

        # Corrupt only the recipient snapshot: sender verification still succeeds.
        snapshot = next((tmp_path / "receiver-store").glob("*/*"))
        if tamper == "symlink":
            snapshot.unlink()
            snapshot.symlink_to(document)
        else:
            snapshot.write_bytes({"hash": b"tampered", "oversize": b"x" * 65}[tamper])
        async with network_hub(tmp_path / "hub", {"caller": "a", "architect": "b"}) as hub:
            async with Network.connect(hub.url, name="architect", token="b", allowed_peers={"caller"},
                                       executor=specialist, ledger_path=tmp_path / "architect.sqlite", artifact_store=receiver_store):
                async with Network.connect(hub.url, name="caller", token="a", allowed_peers={"architect"},
                                           ledger_path=tmp_path / "caller.sqlite", artifact_store=sender_store) as caller:
                    channel = await caller.open(peer="architect", project_id="project")
                    with pytest.raises(ExecutionUncertain, match="before execution"):
                        await caller.ask(channel, "Check", operation_id="corrupt", artifact_refs=(ref,), timeout=5)
                    assert consumed == []
                    snapshot.unlink()
                    snapshot.write_bytes(b"verified")
                    assert (await caller.ask(channel, "Check", operation_id="valid", artifact_refs=(ref,), timeout=5)).text == "Read"
                    other = await caller.open(peer="architect", project_id="ungranted")
                    with pytest.raises(PermissionError):
                        await caller.read_artifact(other, ref)
                    remote = ArtifactRef(ArtifactKind.FILE, "https://127.0.0.1/private", "text/plain", 8, ref.sha256)
                    with pytest.raises(ValueError, match="local store"):
                        await caller.read_artifact(channel, remote)
                    document.write_bytes(b"new value")
                    # Source changes do not silently change the already-published snapshot.
                    assert await caller.read_artifact(channel, ref) == b"verified"
                    changed = sender_store.publish("project", document, media_type="text/plain")
                    with pytest.raises(ExecutionUncertain):
                        await caller.ask(channel, "Check", operation_id="valid", artifact_refs=(changed,), timeout=5)
    asyncio.run(scenario())


def test_cached_output_is_reverified_after_restart_not_trusted_from_ledger(tmp_path: Path):
    async def scenario():
        approved = tmp_path / "approved"
        approved.mkdir()
        report = approved / "report"
        report.write_bytes(b"verified")
        store = ArtifactStore(tmp_path / "store", project_roots={"project": (approved,)})
        ref = store.publish("project", report, kind="result", media_type="text/plain")
        executions = []

        async def specialist(request):
            executions.append(request.operation_id)
            return ExecutionResult("Result", "session", "run", artifact_refs=(ref,))

        for corrupt in (False, True):
            if corrupt:
                next((tmp_path / "store").glob("*/*")).write_bytes(b"tampered")
            async with network_hub(tmp_path / "hub", {"caller": "a", "architect": "b"}) as hub:
                async with Network.connect(hub.url, name="architect", token="b", allowed_peers={"caller"},
                                           executor=specialist, ledger_path=tmp_path / "architect.sqlite", artifact_store=store):
                    async with Network.connect(hub.url, name="caller", token="a", allowed_peers={"architect"},
                                               ledger_path=tmp_path / "caller.sqlite", artifact_store=store) as caller:
                        channel = await caller.open(peer="architect", project_id="project")
                        if corrupt:
                            with pytest.raises(ExecutionUncertain):
                                await caller.ask(channel, "Check", operation_id="once", timeout=5)
                            assert (await caller.history(channel))[-1].kind == "status"
                        else:
                            assert (await caller.ask(channel, "Check", operation_id="once", timeout=5)).artifact_refs == (ref,)
        assert executions == ["once"]
    asyncio.run(scenario())


def test_held_artifact_request_reconciles_after_restart_without_reexecution(tmp_path: Path):
    from hermes_ag2_network.types import network_execution_context_id

    async def scenario():
        approved = tmp_path / "approved"
        approved.mkdir()
        document = approved / "data.txt"
        document.write_bytes(b"verified")
        store = ArtifactStore(tmp_path / "store", project_roots={"project": (approved,)})
        ref = store.publish("project", document, media_type="text/plain")
        executions = []

        class HeldExecutor:
            async def __call__(self, request):
                executions.append(request.operation_id)
                raise ExecutionUncertain("controlled lost acknowledgement")

            async def reconcile(self, request):
                assert request.artifact_refs == (ref,)
                assert store.read(request.project_id, request.artifact_refs[0]) == b"verified"
                return ExecutionResult("Reconciled", "session", "run", artifact_refs=(ref,))

        channel = ""
        for restart in (False, True):
            async with network_hub(tmp_path / "hub", {"caller": "a", "architect": "b"}) as hub:
                async with Network.connect(hub.url, name="architect", token="b", allowed_peers={"caller"},
                                           executor=HeldExecutor(), ledger_path=tmp_path / "architect.sqlite", artifact_store=store) as architect:
                    async with Network.connect(hub.url, name="caller", token="a", allowed_peers={"architect"},
                                               ledger_path=tmp_path / "caller.sqlite", artifact_store=store) as caller:
                        channel = await caller.open(peer="architect", project_id="project")
                        if restart:
                            context = network_execution_context_id("architect", "project", channel, "once")
                            result = await architect.reconcile(context)
                            assert result.artifact_refs == (ref,)
                            reply = await caller.ask(channel, "Check", operation_id="once", artifact_refs=(ref,), timeout=5)
                            assert reply.text == "Reconciled"
                            assert reply.artifact_refs == (ref,)
                        else:
                            with pytest.raises(ExecutionUncertain):
                                await caller.ask(channel, "Check", operation_id="once", artifact_refs=(ref,), timeout=5)
        assert executions == ["once"]
    asyncio.run(scenario())
