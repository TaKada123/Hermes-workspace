"""Public persistent delegation: briefing is provider-only, never replay history."""
import json
import os
from pathlib import Path

import pytest

from tests.fakes.fake_llm_provider import FakeLLMServer, Text, write_hermes_home


@pytest.mark.integration
@pytest.mark.parametrize("goal", [
    "quartz PERSIST-GOAL",
    "quartz PERSIST-GOAL\nsecond line",
    "quartz PERSIST-GOAL\r\nsecond line\r\n",
    "quartz PERSIST-GOAL\nsecond line\n",
    "quartz PERSIST-GOAL\u2028вторая строка\u2028",
    "quartz PERSIST-GOAL\u2029вторая строка\u2029",
    "quartz PERSIST-GOAL\x85вторая строка\x85",
], ids=["single", "lf", "crlf-trailing", "lf-trailing", "unicode-line",
        "unicode-paragraph", "unicode-next-line"])
@pytest.mark.parametrize("mode", ["text", "image", "image-worktree", "image-url"])
def test_persistent_delegation_keeps_briefing_out_of_durable_history(goal, mode, monkeypatch, tmp_path):
    from hermes_state import SessionDB
    from run_agent import AIAgent
    from tools.delegate_tool import delegate_task

    monkeypatch.setenv("HERMES_DUMP_REQUESTS", "1")
    monkeypatch.chdir(tmp_path)
    images = None if mode == "text" else ["data:image/png;base64,aGVsbG8="]
    if mode == "image-url":
        images = ["https://example.invalid/goal.png"]
    worktree_note = ""
    if mode == "image-worktree":
        # Exercise the real seed_workspace annotation without creating/pruning
        # another git repository: only the filesystem boundary is replaced.
        from tools.subagent_worktree import build_worktree_context_note
        info = {"path": str(tmp_path), "branch": "test-child", "base_commit": "test-base"}
        worktree_note = build_worktree_context_note(info)
        monkeypatch.setattr("tools.delegate_tool_child_run._create_isolated_worktree",
                            lambda *args: info)
        monkeypatch.setattr("tools.subagent_worktree.finalize_subagent_worktree",
                            lambda info: {**info, "pruned": False})
    entry = "quartz SECRET-RECALLED-ENTRY requires TLS"
    with FakeLLMServer([Text("child done")]) as srv:
        home = Path(os.environ["HERMES_HOME"])
        write_hermes_home(home, srv.base_url, extra_config=(
            "memory:\n  backend: sqlite_v2\n  nudge_interval: 0\n"
            "delegation:\n  memory_briefing: true\n"
            "providers:\n  custom:\n    models:\n      fake-model:\n        supports_vision: true\n"
            "updates:\n  check: false\nmodels_dev:\n  url: http://127.0.0.1:9/api.json\n"
        ))
        db = SessionDB(db_path=home / "state.db")
        parent = AIAgent(provider="custom", base_url=srv.base_url, api_key="sk-fake-e2e",
                         model="fake-model", quiet_mode=True, session_db=db,
                         enabled_toolsets=["memory", "terminal"], skip_context_files=True,
                         skip_background_review=True)
        children = []
        original_build = __import__("tools.delegate_tool", fromlist=["_build_child_agent"])._build_child_agent
        from unittest.mock import patch
        def record_child(*args, **kwargs):
            child = original_build(*args, **kwargs)
            child.save_trajectories = True
            children.append(child)
            child.test_original_sanitize = child._sanitize_api_messages
            child.test_original_dump = child._dump_api_request_debug
            run = child.run_conversation
            def record_run(*args, **kwargs):
                result = run(*args, **kwargs)
                child.test_returned_messages = result["messages"]
                clean = kwargs["user_message"]
                original_text = clean if isinstance(clean, str) else clean[0]["text"]
                probe = [
                    {"role": "user", "content": clean},
                    {"role": "assistant", "content": original_text},
                    {"role": "user", "content": "History quotes: " + original_text},
                    {"role": "assistant", "content": "continuation"},
                    {"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": original_text}},
                        {"type": "text", "text": "unrelated steering"},
                    ]},
                ]
                from copy import deepcopy
                child.test_probe_input = deepcopy(probe)
                child.test_probe_outbound = child._sanitize_api_messages(probe)
                child.test_probe_after = probe
                child.test_no_goal_outbound = child._sanitize_api_messages([
                    {"role": "system", "content": original_text}, *deepcopy(probe[1:])
                ])
                return result
            child.run_conversation = record_run
            return child
        try:
            parent._ensure_db_session()
            assert parent._memory_store.add("memory", entry)["success"]
            with patch("tools.delegate_tool._build_child_agent", record_child):
                result = json.loads(delegate_task(goal=goal, context="PERSIST-CONTEXT: keep this contract",
                                                   images=images, parent_agent=parent, background=False))
            assert result["results"][0]["status"] == "completed", result
            child = children[0]
            assert child._sanitize_api_messages == child.test_original_sanitize
            assert child._dump_api_request_debug == child.test_original_dump
            requests = srv.main_requests()
            assert requests
            content = requests[0]["messages"][-1]["content"]
            text_values = ([content] if isinstance(content, str) else
                           [p["text"] for p in content if p.get("type") == "text"])
            assert sum(t.count("Memory briefing") for t in text_values) == 1
            assert sum(t.count(entry) for t in text_values) == 1
            assert (goal + worktree_note) in text_values[0]
            if images:
                image_hint = "\n\n[Image attached: " + images[0] + "]" if mode == "image-url" else ""
                assert text_values[0] == goal + worktree_note + image_hint
            assert len(requests) == 1
            # The installed send hook must not mistake quoted history, assistant
            # content, or an image URL for the original goal's text identity.
            probe_out = child.test_probe_outbound
            assert "Memory briefing" in json.dumps(probe_out[0])
            assert "Memory briefing" not in json.dumps(probe_out[1:])
            assert child.test_probe_input == child.test_probe_after
            assert "Memory briefing" not in json.dumps(child.test_no_goal_outbound)
            dumps = list(home.rglob(f"request_dump_{child.session_id}_*.json"))
            assert dumps, "debug snapshot path must be exercised"
            assert all(entry not in dump.read_text() and "Memory briefing" not in dump.read_text()
                       for dump in dumps)
            rows = db.get_messages(child.session_id)
            users = [r for r in rows if r["role"] == "user"]
            assert len(users) == 1
            durable_content = users[0]["content"]
            assert goal in durable_content
            assert "PERSIST-CONTEXT: keep this contract" in str(requests[0]["messages"])
            assert "Memory briefing" not in json.dumps(rows, ensure_ascii=False)
            assert entry not in json.dumps(rows, ensure_ascii=False)
            trajectory = tmp_path / "trajectory_samples.jsonl"
            assert trajectory.exists()
            trajectory_rows = [json.loads(line) for line in trajectory.read_text().split("\n") if line]
            def strings(value):
                if isinstance(value, str):
                    yield value
                elif isinstance(value, list):
                    for item in value:
                        yield from strings(item)
                elif isinstance(value, dict):
                    for item in value.values():
                        yield from strings(item)
            # Existing trajectory/resume display normalization trims outer
            # whitespace; the provider and durable user row above stay verbatim.
            assert any(goal.rstrip() in text for text in strings(trajectory_rows))
            assert entry not in trajectory.read_text() and "Memory briefing" not in trajectory.read_text()
            assert result.get("live_transcripts"), "real durable child transcript must be exercised"
            for transcript in result["live_transcripts"]:
                assert entry not in Path(transcript).read_text()
                assert "Memory briefing" not in Path(transcript).read_text()
            resumed = db.get_messages_as_conversation(child.session_id)
            assert entry not in str(resumed) and "Memory briefing" not in str(resumed)
            assert any((goal + worktree_note).rstrip() in text for text in strings(resumed))
            assert entry not in str(child.test_returned_messages)
            assert "Memory briefing" not in str(child.test_returned_messages)
            assert entry not in json.dumps(result) and "Memory briefing" not in json.dumps(result)
            if images:
                assert isinstance(content, list)
                assert any(p.get("image_url", {}).get("url") == images[0] for p in content)
                assert any(p.get("type") == "image_url" for m in child.test_returned_messages
                           if isinstance(m.get("content"), list) for p in m["content"])
        finally:
            parent.close()
            db.close()
