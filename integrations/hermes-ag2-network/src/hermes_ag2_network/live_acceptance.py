"""Read-only readiness gate, or explicit --execute live Coding/Architect acceptance.

Never substitutes controlled CI for live acceptance. No credential/transcript/private memory
is emitted. Only --execute authorizes fresh Sessions/Runs and temporary Hub/Bridge processes.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
from urllib.parse import urlsplit

import httpx

from .cli import protected_file
from .discovery import profile_root


class RuntimeProbe:
    """Authenticated public HTTP seam, with allowlisted diagnostic receipts."""

    def __init__(self, api_url: str, credentials: dict[str, str]):
        parsed = urlsplit(api_url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
            raise ValueError("API requires a credential-free base URL")
        if parsed.port is not None and parsed.port == 0:
            raise ValueError("API requires a valid listener port")
        if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("HTTP API credentials require loopback")
        if set(credentials) != {"coding", "architect"} or any(not value for value in credentials.values()):
            raise ValueError("both existing specialist credentials are required")
        self.api_url = api_url.rstrip("/")
        self._credentials = credentials

    async def readiness(self) -> dict:
        receipt = {"phase": "readiness", "ready": False, "live_scenario_completed": False,
                   "profiles": {}, "blockers": [], "mutations": []}
        async with httpx.AsyncClient(base_url=self.api_url, timeout=5, trust_env=False,
                                     follow_redirects=False) as client:
            for profile, credential in self._credentials.items():
                result: dict = {"authenticated": False}
                try:
                    response = await client.get(f"/p/{profile}/api/sessions", params={"limit": 1},
                                                headers={"Authorization": f"Bearer {credential}"})
                    result["http_status"] = response.status_code
                    if response.status_code == 200:
                        result["content_type"] = response.headers.get("content-type", "").split(";", 1)[0]
                        result["response_kind"] = (
                            "html" if response.text.lstrip().lower().startswith(("<!doctype html", "<html"))
                            else "json")
                        if result["response_kind"] == "html":
                            receipt["blockers"].append(f"{profile}: HTML fallback; use the authenticated Gateway API listener, not a dashboard")
                            raise ValueError("HTML fallback")
                        body = response.json()
                        schema = ("list.data" if isinstance(body, dict) and body.get("object") == "list"
                                  and isinstance(body.get("data"), list) else
                                  "legacy.sessions" if isinstance(body, dict) and isinstance(body.get("sessions"), list)
                                  else None)
                        result["sessions_schema"] = schema
                        result["authenticated"] = schema is not None
                        if not result["authenticated"]:
                            raise ValueError("invalid Sessions shape")
                    else:
                        action = {
                            401: "authentication rejected; check the profile credential file and configured API key",
                            403: "access denied; check profile API permission and credential scope",
                        }.get(response.status_code, "Sessions request rejected; check Gateway health and API routing")
                        receipt["blockers"].append(f"{profile}: HTTP {response.status_code}: {action}")
                except httpx.HTTPError as exc:
                    result["error_class"] = type(exc).__name__
                    receipt["blockers"].append(f"{profile}: HTTP transport failed ({type(exc).__name__}); check Gateway listener, API URL and TLS connectivity")
                except ValueError:
                    result["error_class"] = "ValueError"
                    receipt["blockers"].append(f"{profile}: invalid Sessions JSON; check API routing and Sessions response schema")
                receipt["profiles"][profile] = result
        receipt["ready"] = not receipt["blockers"]
        return receipt


@contextmanager
def receipt_output(path: Path):
    """Reserve a new evidence target BEFORE live mutations; retain its owning descriptor."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    except FileExistsError:
        raise NotADirectoryError("receipt parent is not a directory") from None
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        yield output


def write_receipt(output, receipt: dict):
    output.seek(0)
    json.dump(receipt, output, ensure_ascii=False, indent=2)
    output.write("\n")
    output.truncate()
    output.flush()
    os.fsync(output.fileno())


async def execute_live(scenario):
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    assert task is not None
    loop.add_signal_handler(signal.SIGTERM, task.cancel)
    try:
        return await scenario.run()
    finally:
        loop.remove_signal_handler(signal.SIGTERM)


def read_credential(parser: argparse.ArgumentParser, profile: str, path: str) -> str:
    option = f"--{profile}-api-key-file"
    try:
        value = protected_file(path)
    except FileNotFoundError:
        parser.exit(2, f"{profile}: credential file missing; provide an existing {option}\n")
    except PermissionError:
        parser.exit(2, f"{profile}: credential file unreadable; check owner and read permission for {option}\n")
    except OSError:
        parser.exit(2, f"{profile}: credential file cannot be read; provide a readable regular file for {option}\n")
    except UnicodeError:
        parser.exit(2, f"{profile}: credential encoding invalid; use a UTF-8 token file for {option}\n")
    except ValueError:
        parser.exit(2, f"{profile}: credential file not owner-only or not regular; set owner and chmod 0600 for {option}\n")
    if not value or any(not 33 <= ord(char) <= 126 for char in value):
        parser.exit(2, f"{profile}: credential must be one nonempty ASCII token; correct {option}\n")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--coding-api-key-file", required=True)
    parser.add_argument("--architect-api-key-file", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="opt in to fresh-session real Hermes scenario")
    parser.add_argument("--home", type=Path, help="owning Hermes root or named profile home")
    parser.add_argument("--state-dir", type=Path, help="new owner-only state directory; never reuse/delete uncertain ledgers")
    parser.add_argument("--idle-seconds", type=float, default=10)
    args = parser.parse_args()
    if args.execute and args.state_dir is None:
        parser.error("--execute requires a new --state-dir")
    if args.execute and not 2 <= args.idle_seconds <= 300:
        parser.error("--idle-seconds must be between 2 and 300")
    if args.receipt.exists():
        parser.exit(2, "receipt target already exists; choose a new --receipt path (previous evidence preserved)\n")
    credentials = {
        "coding": read_credential(parser, "coding", args.coding_api_key_file),
        "architect": read_credential(parser, "architect", args.architect_api_key_file),
    }
    try:
        probe = RuntimeProbe(args.api_url, credentials)
        receipt = asyncio.run(probe.readiness())
    except (ValueError, httpx.InvalidURL):
        parser.exit(2, "invalid --api-url; use a credential-free HTTP loopback or HTTPS base URL with a valid host/port, without path, query or fragment\n")
    try:
        with receipt_output(args.receipt) as output:
            write_receipt(output, receipt)
            if args.execute and receipt["ready"]:
                from .live_scenario import LiveScenario
                from .live_runtime import source_identity
                readiness = receipt
                build = source_identity()
                write_receipt(output, {**readiness, 'live_attempt_started': True,
                                      'state_dir': str(args.state_dir), 'execution_build': build})
                scenario = LiveScenario(args.api_url, credentials, home=profile_root(args.home),
                                        state_dir=args.state_dir, idle_seconds=args.idle_seconds)
                receipt = asyncio.run(execute_live(scenario))
                receipt["readiness"] = readiness
                receipt["execution_build"] = build
                write_receipt(output, receipt)
    except FileExistsError:
        parser.exit(2, "receipt target already exists; choose a new --receipt path (previous evidence preserved)\n")
    except PermissionError:
        parser.exit(2, "receipt write denied; check owner and write permission for --receipt and its parent directory\n")
    except OSError:
        parser.exit(2, "receipt could not be saved; check --receipt parent directory, available space and filesystem access\n")
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if (receipt["live_scenario_completed"] if args.execute else receipt["ready"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
