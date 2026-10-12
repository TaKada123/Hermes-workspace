"""Name-only Hermes profile discovery and explicit enrollment CLI workflow."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from hermes_ag2_network.discovery import discover_profiles, enroll_profile, enrolled_profiles, revoke_profile


def test_discovery_lists_profile_directory_names_only(tmp_path: Path):
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "coding").mkdir()
    (profiles / "architect").mkdir()
    (profiles / "not-a-profile.txt").write_text("ignored")
    (profiles / "unsafe.name").mkdir()
    assert discover_profiles(tmp_path) == ["architect", "coding", "default"]
    assert enrolled_profiles(tmp_path) == []


def test_enrollment_is_explicit_and_writes_only_names(tmp_path: Path):
    (tmp_path / "profiles" / "coding").mkdir(parents=True)
    (tmp_path / "profiles" / "architect").mkdir()
    assert enroll_profile("coding", tmp_path) == ["coding"]
    assert enrolled_profiles(tmp_path) == ["coding"]
    enrollment = tmp_path / "agent-network" / "enrolled-profiles.json"
    assert json.loads(enrollment.read_text()) == ["coding"]
    assert enrollment.stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError, match="not available"):
        enroll_profile("missing", tmp_path)


def test_enrollment_refuses_insecure_existing_file(tmp_path: Path):
    (tmp_path / "profiles" / "coding").mkdir(parents=True)
    enrollment = tmp_path / "agent-network" / "enrolled-profiles.json"
    enrollment.parent.mkdir(mode=0o700)
    enrollment.write_text('["coding"]', encoding="utf-8")
    enrollment.chmod(0o644)
    with pytest.raises(PermissionError, match="owner-only"):
        enrolled_profiles(tmp_path)
    with pytest.raises(PermissionError, match="owner-only"):
        enroll_profile("coding", tmp_path)


def test_cli_discovery_does_not_enroll_and_then_explicitly_enrolls(tmp_path: Path):
    (tmp_path / "profiles" / "coding").mkdir(parents=True)
    module = "hermes_ag2_network.cli"
    first = subprocess.run([sys.executable, "-m", module, "profiles", "--home", str(tmp_path)],
                           text=True, capture_output=True, check=True)
    assert json.loads(first.stdout) == {"available": ["coding", "default"], "enrolled": []}
    assert not (tmp_path / "agent-network" / "enrolled-profiles.json").exists()
    second = subprocess.run([sys.executable, "-m", module, "profiles", "--home", str(tmp_path),
                             "--enroll", "coding"], text=True, capture_output=True, check=True)
    assert json.loads(second.stdout) == {"available": ["coding", "default"], "enrolled": ["coding"]}
    third = subprocess.run([sys.executable, "-m", module, "profiles", "--home", str(tmp_path),
                            "--revoke", "coding"], text=True, capture_output=True, check=True)
    assert json.loads(third.stdout)["enrolled"] == []
    assert enrolled_profiles(tmp_path) == []
    denied = subprocess.run([sys.executable, "-m", module, "bridge", "--home", str(tmp_path),
                             "--name", "coding", "--hub-url", "ws://127.0.0.1:1", "--allow-peer", "caller",
                             "--ledger", str(tmp_path / "unused.sqlite"),
                             "--control-db", str(tmp_path / "unused-control.sqlite"),
                             "--api-url", "http://127.0.0.1:1"], text=True, capture_output=True, timeout=10)
    assert denied.returncode == 2 and "not explicitly enrolled" in denied.stderr
    assert not (tmp_path / "unused.sqlite").exists()


def test_profile_home_resolves_root_and_default_can_be_enrolled(tmp_path: Path, monkeypatch):
    profile = tmp_path / "profiles" / "coding"
    profile.mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(profile))
    assert discover_profiles() == ["coding", "default"]
    assert enroll_profile("default") == ["default"]
    assert enrolled_profiles(tmp_path) == ["default"]
    assert not (profile / "agent-network").exists()
    assert revoke_profile("default", profile) == []


def test_concurrent_cli_enrollments_preserve_all_names(tmp_path: Path):
    names = [f"profile{i}" for i in range(8)]
    for name in names:
        (tmp_path / "profiles" / name).mkdir(parents=True)
    children = [subprocess.Popen([sys.executable, "-m", "hermes_ag2_network.cli", "profiles",
                                 "--home", str(tmp_path), "--enroll", name],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for name in names]
    for child in children:
        _, error = child.communicate(timeout=30)
        assert child.returncode == 0, error
    assert enrolled_profiles(tmp_path) == names
    assert revoke_profile(names[0], tmp_path) == names[1:]
    assert revoke_profile(names[0], tmp_path) == names[1:]


def test_enrollment_rejects_symlink_directory_and_file(tmp_path: Path):
    (tmp_path / "profiles" / "coding").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    link = tmp_path / "agent-network"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(PermissionError):
        enroll_profile("coding", tmp_path)
    link.unlink()
    link.mkdir(mode=0o700)
    target = outside / "target.json"
    target.write_text('[]', encoding="utf-8")
    target.chmod(0o600)
    (link / "enrolled-profiles.json").symlink_to(target)
    with pytest.raises(PermissionError):
        enroll_profile("coding", tmp_path)
    assert target.read_text(encoding="utf-8") == '[]'


@pytest.mark.parametrize("linked_component", ["home", "ancestor"])
@pytest.mark.parametrize("action", [enrolled_profiles, enroll_profile, revoke_profile])
def test_enrollment_rejects_symlink_ancestors_without_reading_or_writing_target(
    tmp_path: Path, linked_component: str, action,
):
    real_home = tmp_path / "real" / "home"
    (real_home / "profiles" / "coding").mkdir(parents=True)
    assert enroll_profile("coding", real_home) == ["coding"]
    enrollment = real_home / "agent-network" / "enrolled-profiles.json"
    before = enrollment.read_bytes()
    link = tmp_path / "linked"
    link.symlink_to(real_home if linked_component == "home" else real_home.parent, target_is_directory=True)
    home = link if linked_component == "home" else link / "home"
    with pytest.raises(PermissionError, match="symlink"):
        if action is enrolled_profiles:
            action(home)
        else:
            action("default", home)
    assert enrollment.read_bytes() == before
    # Reject before creating enrollment storage through a linked ancestor too.
    missing_home = link / "new-home"
    with pytest.raises(PermissionError, match="symlink"):
        revoke_profile("default", missing_home)
    assert not missing_home.exists()
