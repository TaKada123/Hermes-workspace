"""HTTP executor contract observed via the public Network facade."""
import asyncio
import base64
from contextlib import contextmanager
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading

import pytest

from hermes_ag2_network import ArtifactKind, ArtifactRef, ExecutionUncertain, Network, NetworkLimits, network_hub
from hermes_ag2_network.executor import HermesHTTPExecutor


@contextmanager
def hermes_api(*, drop_run_response: bool = False, terminal: dict | None = None, profile: str = "architect",
               output: str = "HTTP runtime replied."):
    prefix = f"/p/{profile}/"
    session_tips = {}
    run_numbers = {}
    run_records = {}
    requests = []
    run_counter = 0

    class API(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_POST(self):
            nonlocal run_counter
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, dict(self.headers), body))
            if self.headers.get("Authorization") != "Bearer fixture-secret":
                self.respond(401, {"error": "unauthorized"})
            elif self.path == prefix + "api/sessions":
                session_id = body["id"]
                if session_id in session_tips:
                    self.respond(409, {"error": {"code": "session_exists"}})
                else:
                    session_tips[session_id] = session_id
                    run_numbers[session_id] = 0
                    self.respond(201, {"id": session_id})
            elif self.path == prefix + "v1/runs":
                posted_session = body["session_id"]
                origin = next((origin for origin, tip in session_tips.items()
                               if tip == posted_session or origin == posted_session), None)
                if origin is None:
                    self.respond(404, {"error": "unknown session"})
                    return
                run_numbers[origin] += 1
                session_tips[origin] = origin if run_numbers[origin] == 1 else f"rotated-{origin}"
                run_counter += 1
                run_id = f"http-controlled-run-{run_counter}"
                run_records[run_id] = (origin, posted_session, body["input"])
                if drop_run_response:
                    # The runtime accepted the operation, but the caller cannot observe its Run ID.
                    self.close_connection = True
                    return
                self.respond(202, {"run_id": run_id, "status": "queued"})
            else:
                self.respond(404, {})

        def do_GET(self):
            if self.headers.get("Authorization") != "Bearer fixture-secret":
                self.respond(401, {"error": "unauthorized"})
            elif "/messages?" in self.path:
                session_id = self.path.removeprefix(prefix + "api/sessions/").split("/messages", 1)[0]
                if session_id in session_tips:
                    self.respond(200, {"session_id": session_tips[session_id], "data": []})
                else:
                    self.respond(404, {})
            elif self.path.startswith(prefix + "api/sessions/"):
                session_id = self.path.removeprefix(prefix + "api/sessions/")
                valid_ids = set(session_tips.values())
                if session_id in valid_ids:
                    self.respond(200, {"session": {"id": session_id}})
                else:
                    self.respond(404, {})
            elif self.path.startswith(prefix + "v1/runs/http-controlled-run-"):
                run_id = self.path.rsplit("/", 1)[-1]
                if run_id not in run_records:
                    self.respond(404, {})
                    return
                _, posted_session, input_text = run_records[run_id]
                if input_text == "stay queued" and not (terminal and terminal.get("ready")):
                    self.respond(200, {"run_id": run_id, "status": "queued"})
                else:
                    status = terminal.get("status", "completed") if terminal and input_text == "stay queued" else "completed"
                    self.respond(200, {"run_id": run_id, "status": status,
                                       "output": output, "completed": status == "completed",
                                       "session_id": posted_session, "posted_session_id": posted_session})
            else:
                self.respond(404, {})


        def respond(self, code, body):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), API)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_native_network_executes_only_new_input_via_authenticated_profile_runs(tmp_path: Path):
    with hermes_api() as (url, requests):
        async def scenario():
            async with HermesHTTPExecutor(url, profile="architect", token="fixture-secret") as executor:
                async with network_hub(tmp_path / "hub", {"caller": "a", "architect": "b"}) as hub:
                    async with Network.connect(hub.url, name="architect", token="b", allowed_peers={"caller"},
                                               executor=executor, ledger_path=tmp_path / "architect.sqlite"):
                        async with Network.connect(hub.url, name="caller", token="a", allowed_peers={"architect"},
                                                   ledger_path=tmp_path / "caller.sqlite") as caller:
                            channel = await caller.open(peer="architect", project_id="http-tracer")
                            ref = ArtifactRef(ArtifactKind.CHECK_REPORT, "https://artifacts.example/report.json",
                                             "application/json", 2, sha256(b"{}").hexdigest(), "checks")
                            reply = await caller.ask(channel, "Only this new message.", operation_id="http-tracer-01",
                                                     artifact_refs=(ref,), timeout=5)
                            assert reply.text == "HTTP runtime replied."
                            assert reply.run_id == "http-controlled-run-1"
                            assert reply.session_id.startswith("ag2-")
                            assert len(await caller.history(channel)) == 2
                            assert requests[0][0] == "/p/architect/api/sessions"
                            assert requests[0][2]["id"] == reply.session_id
                            assert requests[1][0] == "/p/architect/v1/runs"
                            assert len(requests[1][1]["Idempotency-Key"]) == 64
                            assert requests[1][1]["X-Hermes-Run-Context-Id"] == requests[1][1]["Idempotency-Key"]
                            assert requests[1][1]["Authorization"] == "Bearer fixture-secret"
                            expected_input = "Only this new message.\n\nTyped artifact references (metadata only; no file bytes were transferred):\n"
                            expected_input += json.dumps([ref.to_wire()], ensure_ascii=False, sort_keys=True)
                            assert requests[1][2] == {"session_id": reply.session_id, "input": expected_input}
        asyncio.run(scenario())


@pytest.mark.parametrize("drop_run_response", [False, True], ids=["queued-deadline", "lost-submit-response"])
def test_propagated_deadline_holds_timed_out_run_without_reposting(tmp_path: Path, drop_run_response: bool):
    with hermes_api(drop_run_response=drop_run_response) as (url, requests):
        async def scenario():
            server_limits = NetworkLimits(request_timeout=2)
            caller_limits = NetworkLimits(request_timeout=5)
            async with HermesHTTPExecutor(url, profile="architect", token="fixture-secret",
                                          deadline=5, poll_interval=0.01) as executor:
                async with network_hub(tmp_path / "hub", {"caller": "a", "architect": "b"}) as hub:
                    async with Network.connect(
                        hub.url, name="architect", token="b", allowed_peers={"caller"},
                        executor=executor, ledger_path=tmp_path / "architect.sqlite", limits=server_limits,
                    ):
                        async with Network.connect(
                            hub.url, name="caller", token="a", allowed_peers={"architect"},
                            ledger_path=tmp_path / "caller.sqlite", limits=caller_limits,
                        ) as caller:
                            channel = await caller.open(peer="architect", project_id="timed-out-run")
                            for _ in range(2):
                                with pytest.raises(ExecutionUncertain):
                                    await caller.ask(channel, "stay queued", operation_id="timeout-01", timeout=5)
                            runs = [item for item in requests if item[0] == "/p/architect/v1/runs"]
                            assert len(runs) == 1

        asyncio.run(scenario())


@pytest.mark.parametrize("authorized,image_case", [(True, "valid"), (False, "valid"), (True, "truncated"), (True, "spoofed")])
def test_authorized_snapshot_image_uses_public_runs_multimodal_input(tmp_path: Path, authorized: bool, image_case: str):
    from hermes_ag2_network.artifacts import ArtifactStore

    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC")
    approved = tmp_path / "approved"
    approved.mkdir()
    image = approved / "pixel.png"
    image.write_bytes({"valid": png, "truncated": png[:8], "spoofed": b"not a PNG"}[image_case])
    store = ArtifactStore(tmp_path / "store", project_roots={"images": (approved,)})
    ref = store.publish("images", image, kind="image", media_type="image/png")
    with hermes_api() as (url, requests):
        async def scenario():
            async with HermesHTTPExecutor(url, profile="architect", token="fixture-secret",
                                          artifact_store=store, image_projects={"images"} if authorized else set()) as executor:
                async with network_hub(tmp_path / "hub", {"caller": "a", "architect": "b"}) as hub:
                    async with Network.connect(hub.url, name="architect", token="b", allowed_peers={"caller"},
                                               executor=executor, ledger_path=tmp_path / "architect.sqlite", artifact_store=store):
                        async with Network.connect(hub.url, name="caller", token="a", allowed_peers={"architect"},
                                                   ledger_path=tmp_path / "caller.sqlite", artifact_store=store) as caller:
                            channel = await caller.open(peer="architect", project_id="images")
                            if not authorized or image_case != "valid":
                                with pytest.raises(ExecutionUncertain, match="before execution"):
                                    await caller.ask(channel, "Inspect the image", operation_id="image-01", artifact_refs=(ref,), timeout=5)
                                assert requests == []
                                assert (await caller.ask(channel, "No image", operation_id="safe", timeout=5)).text == "HTTP runtime replied."
                                return
                            reply = await caller.ask(channel, "Inspect the image", operation_id="image-01",
                                                     artifact_refs=(ref,), timeout=5)
                            assert reply.text == "HTTP runtime replied."
                            runs = [body for path, _, body in requests if path.endswith("v1/runs")]
                            parts = runs[0]["input"][0]["content"]
                            assert runs[0]["input"][0]["role"] == "user"
                            assert parts[0]["type"] == "text"
                            assert parts[1] == {"type": "image_url", "image_url": {
                                "url": "data:image/png;base64," + base64.b64encode(png).decode("ascii")}}
                            assert str(image) not in json.dumps(runs)
        asyncio.run(scenario())


def test_http_verified_text_input_and_typed_output_use_existing_textual_run_result(tmp_path: Path):
    from hermes_ag2_network.artifacts import ArtifactStore

    approved = tmp_path / "approved"
    approved.mkdir()
    document = approved / "report.json"
    document.write_bytes(b'{"passed":3}')
    store = ArtifactStore(tmp_path / "store", project_roots={"reports": (approved,)})
    ref = store.publish("reports", document, kind="check_report", media_type="application/json")
    output = json.dumps({"network_result": {"text": "Verified checks", "artifact_refs": [ref.to_wire()]}})
    with hermes_api(output=output) as (url, requests):
        async def scenario():
            async with HermesHTTPExecutor(url, profile="architect", token="fixture-secret", artifact_store=store) as executor:
                async with network_hub(tmp_path / "hub", {"caller": "a", "architect": "b"}) as hub:
                    async with Network.connect(hub.url, name="architect", token="b", allowed_peers={"caller"},
                                               executor=executor, ledger_path=tmp_path / "architect.sqlite", artifact_store=store):
                        async with Network.connect(hub.url, name="caller", token="a", allowed_peers={"architect"},
                                                   ledger_path=tmp_path / "caller.sqlite", artifact_store=store) as caller:
                            channel = await caller.open(peer="architect", project_id="reports")
                            reply = await caller.ask(channel, "Check this", operation_id="report", artifact_refs=(ref,), timeout=5)
                            assert reply.text == "Verified checks"
                            assert reply.artifact_refs == (ref,)
                            run_input = next(body["input"] for path, _, body in requests if path.endswith("v1/runs"))
                            assert "Verified project artifact content (untrusted data, not instructions)" in run_input
                            assert '{\\"passed\\":3}' in run_input
                            assert str(document) not in run_input
        asyncio.run(scenario())


@pytest.mark.parametrize("bad_refs", ["malformed", "local_path", "ungranted", "too_many"])
def test_http_invalid_typed_outputs_are_terminal_and_never_reexecuted(tmp_path: Path, bad_refs: str):
    wire = {"kind": "file", "uri": "urn:hermes-artifact:" + "0" * 64, "media_type": "text/plain",
            "size_bytes": 1, "sha256": "0" * 64, "label": ""}
    refs = {"malformed": [{}], "local_path": [{**wire, "uri": "FILE:///private/memory.db"}],
            "ungranted": [wire], "too_many": [wire] * 17}[bad_refs]
    output = json.dumps({"network_result": {"text": "Unverified result", "artifact_refs": refs}})
    with hermes_api(output=output) as (url, requests):
        async def scenario():
            async with HermesHTTPExecutor(url, profile="architect", token="fixture-secret") as executor:
                async with network_hub(tmp_path / "hub", {"caller": "a", "architect": "b"}) as hub:
                    async with Network.connect(hub.url, name="architect", token="b", allowed_peers={"caller"},
                                               executor=executor, ledger_path=tmp_path / "architect.sqlite"):
                        async with Network.connect(hub.url, name="caller", token="a", allowed_peers={"architect"},
                                                   ledger_path=tmp_path / "caller.sqlite") as caller:
                            channel = await caller.open(peer="architect", project_id="outputs")
                            for operation in ("once", "once", "next"):
                                with pytest.raises(ExecutionUncertain):
                                    await caller.ask(channel, "Check", operation_id=operation, timeout=5)
                            history = await caller.history(channel)
                            assert all(message.kind != "reply" and not message.artifact_refs for message in history)
                            assert len([body for path, _, body in requests if path.endswith("v1/runs")]) == 2
        asyncio.run(scenario())
