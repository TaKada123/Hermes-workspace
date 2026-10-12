"""Name-only discovery and explicit, locked enrollment for Hermes profiles (POSIX)."""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import re
import stat
import tempfile

_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


def profile_root(hermes_home: Path | None = None) -> Path:
    """Resolve default/custom roots, including a named profile's HERMES_HOME."""
    value = str(hermes_home) if hermes_home is not None else os.environ.get("HERMES_HOME", "").strip()
    # health: allow HX001 -- explicit standalone default-root path; no owning core import.
    home = Path(os.path.expandvars(value)).expanduser() if value else Path.home() / ".hermes"
    return home.parent.parent if home.parent.name == "profiles" else home


def discover_profiles(hermes_home: Path | None = None) -> list[str]:
    """List directory names only; default lives at the root, not profiles/default."""
    home = profile_root(hermes_home)
    names = {"default"} if home.is_dir() else set()
    profiles_dir = home / "profiles"
    if profiles_dir.is_dir():
        names.update(entry.name for entry in profiles_dir.iterdir()
                     if entry.is_dir() and not entry.is_symlink() and _NAME.fullmatch(entry.name))
    return sorted(names)


def _owner_only(path: Path, *, directory: bool = False) -> None:
    metadata = path.lstat()
    valid_type = stat.S_ISDIR(metadata.st_mode) if directory else stat.S_ISREG(metadata.st_mode)
    if not valid_type or metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise PermissionError("enrollment path must be owner-only, owned by this user, and not a symlink")


def enrolled_profiles(hermes_home: Path | None = None) -> list[str]:
    """Return explicitly authorized names; never read profile configuration."""
    path = profile_root(hermes_home) / "agent-network" / "enrolled-profiles.json"
    if not path.parent.exists() and not path.parent.is_symlink():
        return []
    _owner_only(path.parent, directory=True)
    if not path.exists() and not path.is_symlink():
        return []
    _owner_only(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or any(not isinstance(n, str) or not _NAME.fullmatch(n) for n in data):
        raise ValueError("enrollment file must be a JSON array of valid profile names")
    return sorted(set(data))


def _update_enrollment(name: str, hermes_home: Path | None, *, revoke: bool) -> list[str]:
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise ValueError("invalid profile name")
    home = profile_root(hermes_home)
    if not revoke and name not in discover_profiles(home):
        raise ValueError("profile is not available in Hermes home")
    path = home / "agent-network" / "enrolled-profiles.json"
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _owner_only(path.parent, directory=True)
    lock_path = path.parent / ".enrollment.lock"
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "r+") as lock:
        _owner_only(lock_path)
        fcntl.flock(lock, fcntl.LOCK_EX)
        names = set(enrolled_profiles(home))
        names.discard(name) if revoke else names.add(name)
        result = sorted(names)
        descriptor, temporary_name = tempfile.mkstemp(prefix=".enrollment-", suffix=".tmp", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as target:
                target.write(json.dumps(result, indent=2) + "\n")
                target.flush()
                os.fsync(target.fileno())
            temporary.replace(path)
            directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            temporary.unlink(missing_ok=True)
    return result


def enroll_profile(name: str, hermes_home: Path | None = None) -> list[str]:
    """Atomically add one discovered identity, preserving concurrent enrollment updates."""
    return _update_enrollment(name, hermes_home, revoke=False)


def revoke_profile(name: str, hermes_home: Path | None = None) -> list[str]:
    """Remove a startup authorization, even if the profile no longer exists."""
    return _update_enrollment(name, hermes_home, revoke=True)
