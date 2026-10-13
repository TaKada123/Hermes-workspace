"""Read-only live-runtime prerequisite gate. Never substitute controlled CI for live acceptance.

This command intentionally stops before Sessions/Runs mutations when the owner runtime
is unavailable. It is a prerequisite probe, NOT a ten-step scenario executor.
No credential, transcript or private memory is emitted.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .cli import protected_file


class RuntimeProbe:
    """Authenticated public HTTP seam, with allowlisted diagnostic receipts."""

    def __init__(self, api_url: str, credentials: dict[str, str]):
        parsed = urlsplit(api_url)
        if (parsed.scheme not in {"http", "https"} or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
            raise ValueError("API requires a credential-free base URL")
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
                        body = response.json()
                        # The public Sessions list is a dict with a sessions array. A login
                        # page or arbitrary successful proxy response isn't runtime readiness.
                        result["authenticated"] = isinstance(body, dict) and isinstance(body.get("sessions"), list)
                    if not result["authenticated"]:
                        receipt["blockers"].append(f"{profile}: authenticated Sessions API unavailable")
                except (httpx.HTTPError, ValueError) as exc:
                    result["error_class"] = type(exc).__name__
                    receipt["blockers"].append(f"{profile}: authenticated Sessions API unreachable or invalid")
                receipt["profiles"][profile] = result
        receipt["ready"] = not receipt["blockers"]
        return receipt


def save_receipt(path: Path, receipt: dict) -> None:
    """A new evidence target only; never overwrite prior acceptance evidence."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(receipt, output, ensure_ascii=False, indent=2)
        output.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--coding-api-key-file", required=True)
    parser.add_argument("--architect-api-key-file", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    probe = RuntimeProbe(args.api_url, {
        "coding": protected_file(args.coding_api_key_file),
        "architect": protected_file(args.architect_api_key_file),
    })
    receipt = asyncio.run(probe.readiness())
    save_receipt(args.receipt, receipt)
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if receipt["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
