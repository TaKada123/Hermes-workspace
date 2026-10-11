"""HTTP executor contract observed via the public Network facade."""
import asyncio
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading

from hermes_ag2_network import Network, network_hub
from hermes_ag2_network.executor import HermesHTTPExecutor


@contextmanager
def hermes_api():
    requests = []

    class API(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, dict(self.headers), body))
            if self.headers.get("Authorization") != "Bearer fixture-secret":
                self.respond(401, {"error": "unauthorized"})
            elif self.path == "/p/architect/api/sessions":
                self.respond(201, {"id": body["id"]})
            elif self.path == "/p/architect/v1/runs":
                self.respond(202, {"run_id": "http-controlled-run", "status": "queued"})
            else:
                self.respond(404, {})

        def do_GET(self):
            if self.headers.get("Authorization") != "Bearer fixture-secret":
                self.respond(401, {"error": "unauthorized"})
            elif self.path.startswith("/p/architect/api/sessions/"):
                self.respond(200, {"session": {"id": requests[0][2]["id"]}})
            elif self.path == "/p/architect/v1/runs/http-controlled-run":
                self.respond(200, {"run_id": "http-controlled-run", "status": "completed",
                                   "output": "HTTP runtime replied.", "completed": True,
                                   "session_id": requests[1][2]["session_id"]})
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
                            reply = await caller.ask(channel, "Only this new message.", operation_id="http-tracer-01", timeout=5)
                            assert reply.text == "HTTP runtime replied."
                            assert reply.run_id == "http-controlled-run"
                            assert reply.session_id.startswith("ag2-")
                            assert len(await caller.history(channel)) == 2
                            assert requests[0][0] == "/p/architect/api/sessions"
                            assert requests[0][2]["id"] == reply.session_id
                            assert requests[1][0] == "/p/architect/v1/runs"
                            assert requests[1][1]["Idempotency-Key"] == "http-tracer-01"
                            assert requests[1][1]["Authorization"] == "Bearer fixture-secret"
                            assert requests[1][2] == {"session_id": reply.session_id, "input": "Only this new message."}
        asyncio.run(scenario())
