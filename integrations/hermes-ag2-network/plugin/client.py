"""Authenticated JSON client for the Hermes Network plugin's local bridge API."""
from __future__ import annotations

import json
import re
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import ProxyHandler, Request, build_opener

SECRET_NAME = "AGENT_NETWORK_TOOLS_KEY"
_ERROR_BY_STATUS = {
    400: "invalid network request",
    401: "bridge authentication failed",
    403: "peer or channel access denied",
    404: "network channel not found",
    409: "execution is uncertain; operator reconciliation required",
    429: "network request budget exceeded",
    504: "network request timed out",
}


def _base_url(ctx) -> str | None:
    value = ctx.get_config("bridge_url", "http://127.0.0.1:8766")
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
    except ValueError:
        return None
    if (parsed.scheme != "http" or hostname != "127.0.0.1"
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        return None
    if parsed.path not in {"", "/"}:
        return None
    return f"http://{parsed.netloc}"


def _token() -> str:
    # This is called during a profile-scoped tool check/handler, never at import.
    from agent.secret_scope import get_secret
    return get_secret(SECRET_NAME, "") or ""


def available(ctx) -> bool:
    """Expose tools only when this profile has loopback config and its own secret."""
    return bool(_base_url(ctx) and _token())


def request(ctx, method: str, path: str, *, payload: dict | None = None, query: dict | None = None,
           run_context_id: str | None = None) -> dict:
    base_url = _base_url(ctx)
    token = _token()
    if not base_url or not token:
        return {"ok": False, "error": "agent network plugin is not configured for this profile"}
    url = base_url + path
    if query:
        url += "?" + urlencode(query)
    if run_context_id is not None and not re.fullmatch(r"[0-9a-f]{64}", run_context_id):
        return {"ok": False, "error": "invalid Hermes run context"}
    network_context_header = ({"X-Hermes-Run-Context-Id": run_context_id}
                              if run_context_id else {})
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    http_request = Request(url, data=body, method=method, headers={
        "Authorization": f"Bearer {token}",
        "X-Hermes-Profile": ctx.profile_name,
        "Accept": "application/json",
        **network_context_header,
        **({"Content-Type": "application/json"} if body is not None else {}),
    })
    timeout = ctx.get_config("timeout_seconds", 310)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        timeout = 310
    timeout = min(320.0, max(2.0, float(timeout)))
    opener = build_opener(ProxyHandler({}))  # bearer credentials stay on loopback, never an ambient proxy
    try:
        with opener.open(http_request, timeout=timeout) as response:
            result = json.loads(response.read(1024 * 1024))
    except HTTPError as exc:
        try:
            server_error = json.loads(exc.read(64 * 1024)).get("error")
        except (ValueError, AttributeError, UnicodeDecodeError):
            server_error = None
        if server_error == "network cycle detected; request rejected before delivery":
            return {"ok": False, "error": server_error}
        return {"ok": False, "error": _ERROR_BY_STATUS.get(exc.code, "network bridge request failed")}
    except (URLError, TimeoutError, socket.timeout, OSError):
        return {"ok": False, "error": "network bridge unavailable or timed out"}
    except (ValueError, UnicodeDecodeError):
        return {"ok": False, "error": "network bridge returned an invalid response"}
    if not isinstance(result, dict) or result.get("profile") != ctx.profile_name:
        return {"ok": False, "error": "network bridge profile binding mismatch"}
    if result.get("ok") is not True:
        return {"ok": False, "error": "network bridge request failed"}
    return {"ok": True, "result": result.get("result")}
