#!/usr/bin/env python3
"""One-time interactive login helper for the ``tguser`` gateway platform plugin.

Run it with the SAME interpreter the gateway uses (the Hermes runtime python):

    <runtime python> /home/vottak/.hermes/plugins/tguser/login.py

It reads ``TELETHON_API_ID`` / ``TELETHON_API_HASH`` and ``TGUSER_SESSION`` from the profile
env file (``<HERMES_HOME>/.env``, default ``~/.hermes/.env``) or the process environment, builds
a telethon ``TelegramClient`` at the resolved session path, and calls the interactive
``start()`` so that YOU type the phone number, the login code and (if enabled) the two-factor
password in your own terminal. On success it prints the resolved account name and id and then
disconnects.

It never prints or logs the api_hash, the session string, or the login code. Nothing here is
imported by the gateway adapter; the gateway itself never starts an interactive login.
"""

import os
import sys


def _hermes_home() -> str:
    try:
        from hermes_constants import get_hermes_home
    except ImportError:
        return os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return str(get_hermes_home())


def _load_profile_env() -> None:
    """Populate ``os.environ`` from the profile ``.env`` without overriding existing values."""
    home = _hermes_home()
    env_path = os.path.join(home, ".env")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


def main() -> int:
    os.umask(0o077)  # newly created sessions and private outputs are owner-only
    _load_profile_env()
    api_id = (os.environ.get("TELETHON_API_ID") or "").strip()
    api_hash = (os.environ.get("TELETHON_API_HASH") or "").strip()
    home = _hermes_home()
    session = (os.environ.get("TGUSER_SESSION")
               or os.path.join(home, "tguser", "tguser.session")).strip()

    if not api_id or not api_hash:
        print("ERROR: TELETHON_API_ID and TELETHON_API_HASH must be set "
              "(in <HERMES_HOME>/.env or the environment).")
        return 2
    try:
        from telethon import TelegramClient
    except ImportError:
        print("ERROR: telethon is not importable for this interpreter. "
              "Run this script with the Hermes runtime python.")
        return 2

    session = os.path.expanduser(session)
    session_dir = os.path.dirname(session) or "."
    os.makedirs(session_dir, mode=0o700, exist_ok=True)

    print("Starting interactive Telegram login.")
    print("Enter your phone number, the code Telegram sends you, and your two-factor")
    print("password (if any) when prompted. This tool never echoes secrets.")
    client = TelegramClient(session, int(api_id), api_hash)
    try:
        client.start()
    except Exception as exc:  # noqa: BLE001 - report the type only, never the payload
        print(f"ERROR: login failed: {type(exc).__name__}")
        try:
            client.disconnect()
        except Exception:
            pass
        return 1

    try:
        me = client.get_me()
        name = " ".join(
            part for part in (getattr(me, "first_name", None), getattr(me, "last_name", None)) if part
        ) or getattr(me, "username", None) or "unknown"
        print(f"OK: authorized as {name} (id={getattr(me, 'id', None)})")
        print(f"Session written to: {session}")
    finally:
        try:
            client.disconnect()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
