"""Shard receipts preserve Unicode and bound process-tree cleanup."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from types import SimpleNamespace

import psutil
import pytest

from scripts.ci import suite_shards


def test_slice_reads_bom_receipts(tmp_path, monkeypatch, capsys):
    def verify(output, shards):
        (output / "slice-01.txt").write_bytes(b"\xef\xbb\xbf" + "tests/память.py\n".encode("utf-8"))
        return {"head_sha": "test-head"}

    monkeypatch.setattr(suite_shards, "verify", verify)
    popen = subprocess.Popen

    def launch(command, **kwargs):
        return popen([sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'\\xef\\xbb\\xbfok\\n')"], **kwargs)

    monkeypatch.setattr(suite_shards, "subprocess", SimpleNamespace(
        Popen=launch, STDOUT=subprocess.STDOUT, TimeoutExpired=subprocess.TimeoutExpired))
    assert suite_shards.run_slice(1, 2, tmp_path, 10) == 0
    result = json.loads((tmp_path / "result.json").read_text(encoding="utf-8-sig"))
    assert result["files"] == ["tests/память.py"]
    assert result["status"] == "passed"
    assert capsys.readouterr().out == "ok\n\n"


def test_timeout_terminates_descendants_and_records_receipt(tmp_path, monkeypatch):
    def verify(output, shards):
        (output / "slice-01.txt").write_text("tests/example.py\n", encoding="utf-8")
        return {"head_sha": "test-head"}

    monkeypatch.setattr(suite_shards, "verify", verify)
    popen = subprocess.Popen
    processes = []
    child_pid_file = tmp_path / "child.pid"
    from agent.deadline import kill_process_tree

    def launch(command, **kwargs):
        script = (
            "import pathlib, subprocess, sys, time; "
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], "
            "start_new_session=True); "
            f"pathlib.Path({str(child_pid_file)!r}).write_text(str(child.pid), encoding='utf-8'); "
            "time.sleep(60)"
        )
        process = popen([sys.executable, "-c", script], **kwargs)
        processes.append(process)
        deadline = time.monotonic() + 10
        while not child_pid_file.exists():
            assert process.poll() is None
            assert time.monotonic() < deadline
            time.sleep(0.01)
        return process

    monkeypatch.setattr(suite_shards, "subprocess", SimpleNamespace(
        Popen=launch, STDOUT=subprocess.STDOUT, TimeoutExpired=subprocess.TimeoutExpired))
    try:
        assert suite_shards.run_slice(1, 2, tmp_path, 0.05) == 124
        assert processes[0].poll() is not None
        child_pid = int(child_pid_file.read_text(encoding="utf-8-sig"))
        if psutil.pid_exists(child_pid):
            child = psutil.Process(child_pid)
            try:
                child.wait(timeout=10)
            except psutil.TimeoutExpired:
                assert child.status() == psutil.STATUS_ZOMBIE
        result = json.loads((tmp_path / "result.json").read_text(encoding="utf-8-sig"))
        assert result["status"] == "timed_out"
        assert result["exit_code"] == 124
    finally:
        for process in processes:
            if process.poll() is None:
                kill_process_tree(process.pid)
            process.wait(timeout=10)


@pytest.mark.platforms("posix")
@pytest.mark.live_system_guard_bypass  # Must signal our child after it is reparented to init.
def test_timeout_kills_detached_resistant_child_after_parent_exits(tmp_path, monkeypatch):
    def verify(output, shards):
        (output / "slice-01.txt").write_text("tests/example.py\n", encoding="utf-8")
        return {"head_sha": "test-head"}

    monkeypatch.setattr(suite_shards, "verify", verify)
    popen = subprocess.Popen
    parents = []
    children = []
    ready = tmp_path / "resistant-child.pid"
    child_script = (
        "import os, pathlib, signal, time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        f"pathlib.Path({str(ready)!r}).write_text(str(os.getpid()), encoding='utf-8'); "
        "time.sleep(60)"
    )

    def launch(command, **kwargs):
        parent_script = (
            "import subprocess, sys, time; "
            f"subprocess.Popen([sys.executable, '-c', {child_script!r}], start_new_session=True); "
            "time.sleep(60)"
        )
        parent = popen([sys.executable, "-c", parent_script], **kwargs)
        parents.append(parent)
        deadline = time.monotonic() + 10
        while not ready.exists() or not ready.read_text(encoding="utf-8"):
            assert parent.poll() is None
            assert time.monotonic() < deadline, "Detached child never became ready"
            time.sleep(0.01)
        child = psutil.Process(int(ready.read_text(encoding="utf-8")))
        children.append(child)
        assert child.ppid() == parent.pid
        return parent

    monkeypatch.setattr(suite_shards, "subprocess", SimpleNamespace(
        Popen=launch, STDOUT=subprocess.STDOUT, TimeoutExpired=subprocess.TimeoutExpired))
    try:
        assert suite_shards.run_slice(1, 2, tmp_path, 0.05) == 124
        assert parents[0].returncode == -15  # Parent exited on SIGTERM, not escalation.
        child = children[0]
        try:
            child.wait(timeout=3)
        except psutil.TimeoutExpired:
            assert child.status() == psutil.STATUS_ZOMBIE, "Detached SIGTERM-resistant child survived"
        result = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
        assert result["status"] == "timed_out"
        assert result["exit_code"] == 124
    finally:
        # The red run must not leak the deliberately resistant, reparented child.
        for child in children:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        for parent in parents:
            if parent.poll() is None:
                from agent.deadline import kill_process_tree
                kill_process_tree(parent.pid)
            parent.wait(timeout=10)
