"""Offline safety regression tests; no live config, credentials or Telegram access.

Run directly with the Hermes runtime Python (stdlib unittest; no pytest required).
"""
import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "runtime-config/profiles/university/plugins/tguser"


class BaseAdapter:
    def __init__(self, **kwargs):
        self._running = True

    def truncate_message(self, content, limit):
        return [content]

    def _mark_connected(self):
        self._running = True

    def _mark_disconnected(self):
        self._running = False

    def _wire_plugin_handlers(self, _):
        pass


class Dedup:
    def __init__(self, **kwargs):
        self.seen = set()

    def is_duplicate(self, key):
        duplicate = key in self.seen
        self.seen.add(key)
        return duplicate

    def clear(self):
        self.seen.clear()


class Client:
    def __init__(self, *args):
        self.calls = []

    async def get_entity(self, target):
        self.calls.append(("resolve", target))
        return types.SimpleNamespace(id=101)

    async def send_message(self, entity, content):
        self.calls.append(("send", entity.id, content))
        return types.SimpleNamespace(id=55)

    async def connect(self):
        pass

    async def disconnect(self):
        pass

    async def is_user_authorized(self):
        return True

    async def get_me(self):
        self.calls.append(("get_me",))
        return types.SimpleNamespace(id=101)

    def add_event_handler(self, *args):
        pass


class SafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def mod(name, **attrs):
            module = types.ModuleType(name)
            module.__dict__.update(attrs)
            return module

        def extra_or_secret(extra, key, env, default=None):
            return extra.get(key, default)

        cls.env = patch.dict("os.environ", {}, clear=True)
        cls.env.start()
        cls.stubs = patch.dict(sys.modules, {
            "telethon": mod("telethon", TelegramClient=Client,
                            events=types.SimpleNamespace(NewMessage=lambda: None)),
            "telethon.utils": mod("telethon.utils", get_peer_id=lambda e: e.id),
            "gateway": mod("gateway"),
            "gateway.config": mod("gateway.config", Platform=str, PlatformConfig=types.SimpleNamespace),
            "gateway.platforms": mod("gateway.platforms"),
            "gateway.platforms.base": mod("gateway.platforms.base", BasePlatformAdapter=BaseAdapter,
                SendResult=types.SimpleNamespace, validate_inbound_media_size=lambda *a, **k: None),
            "gateway.platforms.event": mod("gateway.platforms.event", MessageEvent=types.SimpleNamespace,
                MessageType=types.SimpleNamespace(TEXT="text", PHOTO="photo", DOCUMENT="document")),
            "gateway.platforms._shared": mod("gateway.platforms._shared",
                get_scoped_secret=lambda *args: "", extra_or_secret=extra_or_secret,
                seed_extra_from_env=lambda *a, **k: None),
            "gateway.platforms.helpers": mod("gateway.platforms.helpers", MessageDeduplicator=Dedup),
            "hermes_constants": mod("hermes_constants", get_hermes_home=lambda: Path("/synthetic/university")),
        })
        cls.stubs.start()
        spec = importlib.util.spec_from_file_location("exported_tguser", PLUGIN / "adapter.py")
        assert spec is not None and spec.loader is not None
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    @classmethod
    def tearDownClass(cls):
        cls.stubs.stop()
        cls.env.stop()

    def make_adapter(self, **extra):
        cfg = types.SimpleNamespace(extra=extra, home_channel=None)
        adapter = self.module.TguserAdapter(cfg)
        adapter._client = Client()
        adapter._self_id = 101
        return adapter

    def test_foreign_home_never_authorizes_a_send(self):
        for home in ["@foreign", "-100202", "202", {"chat_id": "202"}]:
            with self.subTest(home=home):
                adapter = self.make_adapter(home_channel=home)
                target = home["chat_id"] if isinstance(home, dict) else home
                result = asyncio.run(adapter.send(target, "test"))
                self.assertFalse(result.success)
                self.assertEqual(adapter._client.calls, [])

    def test_unknown_outbound_fails_closed(self):
        for mode in ["typo", "all", "", False]:
            with self.subTest(mode=mode):
                adapter = self.make_adapter(outbound=mode)
                self.assertEqual(adapter._outbound_mode, "none")
                self.assertFalse(asyncio.run(adapter.send("me", "test")).success)
                self.assertEqual(adapter._client.calls, [])

    def test_none_blocks_every_target(self):
        for target in ["me", "self", "101", "202", "@foreign"]:
            adapter = self.make_adapter(outbound="none")
            self.assertFalse(asyncio.run(adapter.send(target, "test")).success)
            self.assertEqual(adapter._client.calls, [])

    def test_self_targets_resolve_only_me_metadata_cannot_redirect(self):
        for target in ["me", "self", "101"]:
            adapter = self.make_adapter(home_channel="@foreign")
            result = asyncio.run(adapter.send(target, "test", metadata={"chat_id": "202", "home_channel": "@foreign"}))
            self.assertTrue(result.success)
            self.assertEqual(adapter._client.calls, [("resolve", "me"), ("send", 101, "test")])

    def test_metadata_cannot_authorize_foreign_target(self):
        adapter = self.make_adapter()
        self.assertFalse(asyncio.run(adapter.send("202", "test", metadata={"chat_id": "me"})).success)
        self.assertEqual(adapter._client.calls, [])

    def ingest(self, adapter, chat_id, sender=101, mid=1, text="command", out=False):
        records, dispatches, fetched = [], [], []
        async def fetch(*args):
            fetched.append(args)
            return [], []
        async def dispatch(*args):
            dispatches.append(args)
        async def ack(*args):
            pass
        adapter._fetch_media = fetch
        adapter._append_inbox = lambda *args: records.append(args)
        adapter._dispatch = dispatch
        adapter._ack_read = ack
        event = types.SimpleNamespace(chat_id=chat_id, sender_id=sender, out=out,
            message=types.SimpleNamespace(id=mid, message=text))
        asyncio.run(adapter._on_new_message(event))
        return records, dispatches, fetched

    def test_owner_outside_saved_messages_ignored_even_if_allowlisted(self):
        for allow_all in [False, True]:
            adapter = self.make_adapter(allowed_users="101", allow_all_users=allow_all)
            self.assertEqual(self.ingest(adapter, 202), ([], [], []))

    def test_watched_group_is_only_data_even_from_owner(self):
        adapter = self.make_adapter(allowed_users="101", allow_all_users=True)
        adapter._watched_ids = {-202}
        records, dispatches, _ = self.ingest(adapter, -202)
        self.assertEqual(len(records), 1)
        self.assertEqual(dispatches, [])

    def test_watched_self_chat_is_data_never_instruction(self):
        adapter = self.make_adapter(allowed_users="101")
        adapter._watched_ids = {101}
        records, dispatches, _ = self.ingest(adapter, 101)
        self.assertEqual(len(records), 1)
        self.assertEqual(dispatches, [])

    def test_owner_saved_messages_can_dispatch(self):
        adapter = self.make_adapter(allowed_users="101")
        _, dispatches, _ = self.ingest(adapter, 101)
        self.assertEqual(len(dispatches), 1)

    def test_foreign_sender_in_self_chat_never_dispatches(self):
        adapter = self.make_adapter(allowed_users="202", allow_all_users=True)
        self.assertEqual(self.ingest(adapter, 101, sender=202), ([], [], []))

    def test_unknown_identity_cannot_dispatch(self):
        adapter = self.make_adapter(allowed_users="101", allow_all_users=True)
        adapter._self_id = None
        self.assertEqual(self.ingest(adapter, 101), ([], [], []))

    def test_reply_echo_not_dispatched(self):
        adapter = self.make_adapter(allowed_users="101")
        asyncio.run(adapter.send("me", "reply"))
        self.assertEqual(self.ingest(adapter, 101, mid=55, text="reply", out=True), ([], [], []))

    def test_sent_message_id_collision_in_watched_group_is_recorded(self):
        adapter = self.make_adapter(allowed_users="101")
        adapter._watched_ids = {-202}
        asyncio.run(adapter.send("me", "reply"))
        records, dispatches, _ = self.ingest(adapter, -202, mid=55, text="other")
        self.assertEqual(len(records), 1)
        self.assertEqual(dispatches, [])

    def test_connect_obtains_self_id_from_account(self):
        adapter = self.make_adapter(api_id="1", api_hash="synthetic")
        adapter._client = None
        async def resolve(client):
            return {}, set()
        adapter._resolve_watch_chats = resolve
        with patch.object(self.module.os.path, "exists", return_value=True):
            self.assertTrue(asyncio.run(adapter.connect()))
        self.assertEqual(adapter._self_id, 101)
        self.assertIn(("get_me",), adapter._client.calls)
        asyncio.run(adapter.disconnect())
        self.assertIsNone(adapter._self_id)

    def test_profile_home_uses_routed_context(self):
        with patch.dict("os.environ", {"HERMES_HOME": "/synthetic/wrong-main"}):
            self.assertEqual(self.module._hermes_home(), "/synthetic/university")

    def test_env_seed_includes_outbound(self):
        with patch.object(self.module, "get_scoped_secret", return_value="1"), \
             patch.object(self.module, "seed_extra_from_env", return_value={}) as seed:
            self.module._env_enablement()
        self.assertIn(("TGUSER_OUTBOUND", "outbound", None), seed.call_args.args[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
