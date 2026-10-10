"""Public persistent delegation: briefing is provider-only, never replay history."""
import json
import os
from pathlib import Path

import pytest

from tests.fakes.fake_llm_provider import FakeLLMServer, Text, write_hermes_home


@pytest.mark.integration
@pytest.mark.parametrize("images", [None, ["data:image/png;base64,aGVsbG8="]])
def test_persistent_delegation_keeps_briefing_out_of_durable_history(images, monkeypatch, tmp_path):
    from hermes_state import SessionDB
    from run_agent import AIAgent
    from tools.delegate_tool import delegate_task

    monkeypatch.setenv("HERMES_DUMP_REQUESTS", "1")
    monkeypatch.chdir(tmp_path)
    goal = "quartz PERSIST-GOAL"
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
            run = child.run_conversation
            def record_run(*args, **kwargs):
                result = run(*args, **kwargs)
                child.test_returned_messages = result["messages"]
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
            requests = srv.main_requests()
            assert requests
            content = requests[0]["messages"][-1]["content"]
            assert "Memory briefing" in str(content) and entry in str(content)
            dumps = list(home.rglob(f"request_dump_{child.session_id}_*.json"))
            assert dumps, "debug snapshot path must be exercised"
            assert all(entry not in dump.read_text() and "Memory briefing" not in dump.read_text()
                       for dump in dumps)
            rows = db.get_messages(child.session_id)
            users = [r for r in rows if r["role"] == "user"]
            assert len(users) == 1
            assert goal in users[0]["content"]
            assert "PERSIST-CONTEXT: keep this contract" in str(requests[0]["messages"])
            assert "Memory briefing" not in json.dumps(rows, ensure_ascii=False)
            assert entry not in json.dumps(rows, ensure_ascii=False)
            trajectory = tmp_path / "trajectory_samples.jsonl"
            assert trajectory.exists()
            assert goal in trajectory.read_text()
            assert entry not in trajectory.read_text() and "Memory briefing" not in trajectory.read_text()
            for transcript in result.get("live_transcripts", []):
                assert entry not in Path(transcript).read_text()
                assert "Memory briefing" not in Path(transcript).read_text()
            resumed = db.get_messages_as_conversation(child.session_id)
            assert entry not in str(resumed) and "Memory briefing" not in str(resumed)
            assert entry not in str(child.test_returned_messages)
            assert "Memory briefing" not in str(child.test_returned_messages)
            if images:
                assert isinstance(content, list)
                assert any(p.get("image_url", {}).get("url") == images[0] for p in content)
                assert any(p.get("type") == "image_url" for m in child.test_returned_messages
                           if isinstance(m.get("content"), list) for p in m["content"])
        finally:
            parent.close()
            db.close()
