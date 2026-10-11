#!/usr/bin/env python3
"""List every chat/channel the logged-in Telegram account is a member of.

Used once, after ``login.py`` has created the session, to identify WHICH channel
should be monitored (closed channels are not discoverable any other way - they do
not exist in any index, only in the account's own dialog list).

Run it with the same interpreter the gateway uses:

    /home/vottak/.hermes/tools/python-3.14*/bin/python3 \
        /home/vottak/.hermes/plugins/tguser/scan_dialogs.py [filter]

``filter`` is an optional case-insensitive substring matched against the chat
title and username, so ``scan_dialogs.py универ`` narrows the output.

Output: a table on stdout (type, id, title, username, members) plus a JSON dump
at ``<HERMES_HOME>/tguser/dialogs.json`` for later machine use. It only READS the
dialog list; it never sends anything and never prints the session or api_hash.
"""

import asyncio
import json
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
    home = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
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


def _kind(entity) -> str:
    """Human-readable dialog kind from a telethon entity."""
    if getattr(entity, "broadcast", False):
        return "channel"
    if getattr(entity, "megagroup", False):
        return "supergroup"
    if getattr(entity, "username", None) and getattr(entity, "participants_count", None) is None:
        return "chat"
    return "group"


async def _run(needle: str) -> int:
    from telethon import TelegramClient

    api_id = (os.environ.get("TELETHON_API_ID") or "").strip()
    api_hash = (os.environ.get("TELETHON_API_HASH") or "").strip()
    home = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    session = os.path.expanduser(
        (os.environ.get("TGUSER_SESSION") or os.path.join(home, "tguser", "tguser")).strip()
    )
    if not api_id or not api_hash:
        print("ERROR: TELETHON_API_ID and TELETHON_API_HASH must be set in <HERMES_HOME>/.env.")
        return 2
    if not os.path.isfile(session + ".session"):
        print(f"ERROR: no session at {session}.session - run login.py first.")
        return 2

    rows = []
    client = TelegramClient(session, int(api_id), api_hash)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            print("ERROR: session exists but is not authorized - re-run login.py.")
            return 2
        me = await client.get_me()
        print(f"account: {getattr(me, 'first_name', '') or ''} (id={getattr(me, 'id', None)})")
        print("")
        header = f"{'type':<11} {'id':<16} {'username':<22} title"
        print(header)
        print("-" * len(header))
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            row = {
                "type": _kind(entity),
                "id": dialog.id,
                "title": dialog.title or "",
                "username": getattr(entity, "username", None) or "",
                "is_channel": bool(getattr(entity, "broadcast", False)),
                "protected_content": bool(getattr(entity, "noforwards", False)),
            }
            rows.append(row)
            haystack = f"{row['title']} {row['username']}".lower()
            if needle and needle not in haystack:
                continue
            print(f"{row['type']:<11} {row['id']:<16} {(row['username'] or '-'):<22} {row['title']}")
    finally:
        await client.disconnect()

    out_path = os.path.join(home, "tguser", "dialogs.json")
    os.makedirs(os.path.dirname(out_path), mode=0o700, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)
    print("")
    print(f"total dialogs: {len(rows)}; json written to {out_path}")
    print("note: 'protected_content: true' means Telegram blocks media download there")
    print("      (set in dialogs.json, column noforwards) - text still readable.")
    return 0


def main() -> int:
    _load_profile_env()
    needle = " ".join(sys.argv[1:]).strip().lower()
    return asyncio.run(_run(needle))


if __name__ == "__main__":
    sys.exit(main())
