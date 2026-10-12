"""Typed descriptors and explicitly granted same-host verified content snapshots."""
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
from pathlib import Path
import os
import re
import stat
import struct
import zlib
import uuid
from collections.abc import Mapping
from urllib.parse import urlsplit


class ArtifactKind(StrEnum):
    FILE = "file"
    IMAGE = "image"
    CHECK_REPORT = "check_report"
    GIT_REFERENCE = "git_reference"
    RESULT = "result"
    ERROR = "error"
    STATUS = "status"


@dataclass(frozen=True)
class ArtifactRef:
    """A verified descriptor, not an authorization to read the referenced object."""

    kind: ArtifactKind
    uri: str
    media_type: str
    size_bytes: int
    sha256: str
    label: str = ""

    def __post_init__(self):
        if any(not isinstance(value, str) for value in (self.uri, self.media_type, self.sha256, self.label)):
            raise ValueError("artifact string fields must be strings")
        if not isinstance(self.kind, ArtifactKind):
            raise ValueError("artifact kind must be an ArtifactKind")
        if not self.uri or len(self.uri) > 2048 or "\n" in self.uri:
            raise ValueError("artifact URI must be nonempty and bounded")
        parsed = urlsplit(self.uri)
        scheme = parsed.scheme.casefold()
        if scheme not in {"https", "git+https", "urn", "file"}:
            raise ValueError("artifact URI scheme is not allowed")
        if scheme == "file" and (not parsed.path.startswith("/") or parsed.netloc):
            raise ValueError("artifact URI is invalid")
        if scheme in {"https", "git+https"} and (not parsed.hostname or parsed.username or parsed.password):
            raise ValueError("artifact URI must be an authenticated-free HTTPS reference")
        if scheme == "urn" and not parsed.path:
            raise ValueError("artifact URN must contain a name")
        if not self.media_type or len(self.media_type) > 127 or "/" not in self.media_type:
            raise ValueError("artifact media type is invalid")
        if isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int) or self.size_bytes < 0:
            raise ValueError("artifact size must be a nonnegative integer")
        if not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValueError("artifact sha256 must be lowercase hexadecimal")
        if len(self.label) > 256 or "\n" in self.label:
            raise ValueError("artifact label is invalid")

    @property
    def is_local_file(self) -> bool:
        return urlsplit(self.uri).scheme.casefold() == "file"

    def to_wire(self) -> dict[str, str | int]:
        return {"kind": self.kind.value, "uri": self.uri, "media_type": self.media_type,
                "size_bytes": self.size_bytes, "sha256": self.sha256, "label": self.label}

    @classmethod
    def from_wire(cls, value: object) -> "ArtifactRef":
        if not isinstance(value, dict) or set(value) != {
            "kind", "uri", "media_type", "size_bytes", "sha256", "label",
        }:
            raise ValueError("artifact reference has an invalid shape")
        try:
            return cls(ArtifactKind(value["kind"]), value["uri"], value["media_type"],
                       value["size_bytes"], value["sha256"], value["label"])
        except (TypeError, KeyError) as exc:
            raise ValueError("artifact reference has invalid fields") from exc


def verify_local_file(path: Path, *, approved_roots: tuple[Path, ...], max_bytes: int,
                      kind: ArtifactKind = ArtifactKind.FILE, media_type: str = "application/octet-stream",
                      label: str = "") -> ArtifactRef:
    """Hash only a regular, bounded file explicitly contained in an approved root."""
    candidate = _absolute(path)
    roots = tuple(_absolute(root) for root in approved_roots)
    if not roots or not any(candidate.is_relative_to(root) for root in roots):
        raise PermissionError("artifact is outside explicitly approved roots")
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 0:
        raise ValueError("max_bytes must be a nonnegative integer")
    content = _read_regular(candidate, max_bytes)
    return ArtifactRef(kind, candidate.as_uri(), media_type, len(content), hashlib.sha256(content).hexdigest(), label)


def _absolute(path: Path) -> Path:
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise PermissionError("artifact paths must be absolute without traversal")
    return path


def _open_directory(path: Path) -> int:
    """Walk with dirfd/no-follow: reject links in every component, including roots."""
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY") or os.open not in os.supports_dir_fd:
        raise NotImplementedError("verified artifact content requires POSIX no-follow/dirfd support; use metadata-only mode")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in _absolute(path).parts[1:]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except OSError as exc:
        os.close(fd)
        raise PermissionError("artifact directory unavailable or symlinked") from exc


def _read_regular(path: Path, max_bytes: int) -> bytes:
    parent = _open_directory(path.parent)
    try:
        try:
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        except OSError as exc:
            raise PermissionError("artifact unavailable or symlinked") from exc
        with os.fdopen(fd, "rb") as source:
            metadata = os.fstat(source.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("artifact must be a regular file")
            if metadata.st_size > max_bytes:
                raise ValueError("artifact exceeds the configured size limit")
            content = source.read(max_bytes + 1)
            if len(content) > max_bytes:
                raise ValueError("artifact exceeds the configured size limit")
            return content
    finally:
        os.close(parent)


def validate_image_content(content: bytes, media_type: str):
    """Check bounded container integrity, not a replacement for the provider's decoder."""
    signatures = {"image/png": b"\x89PNG\r\n\x1a\n", "image/jpeg": b"\xff\xd8\xff",
                  "image/gif": b"GIF8", "image/webp": b"RIFF"}
    if media_type not in signatures or not content.startswith(signatures[media_type]):
        raise ValueError("image type or signature is unsupported")
    complete = {
        "image/png": content.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82"),
        "image/jpeg": len(content) > 4 and content.endswith(b"\xff\xd9"),
        "image/gif": len(content) > 13 and content.endswith(b";"),
        "image/webp": len(content) >= 20 and content[8:12] == b"WEBP"
                      and int.from_bytes(content[4:8], "little") + 8 == len(content),
    }
    if not complete[media_type]:
        raise ValueError("image container is incomplete")
    if media_type == "image/png":
        offset = 8
        chunk_types = []
        while offset < len(content):
            if offset + 12 > len(content):
                raise ValueError("image container is incomplete")
            size = struct.unpack(">I", content[offset:offset + 4])[0]
            end = offset + size + 12
            if end > len(content):
                raise ValueError("image container is incomplete")
            chunk = content[offset + 4:end - 4]
            if zlib.crc32(chunk) != int.from_bytes(content[end - 4:end], "big"):
                raise ValueError("image chunk integrity mismatch")
            chunk_types.append(chunk[:4])
            offset = end
        if chunk_types[0] != b"IHDR" or b"IDAT" not in chunk_types or chunk_types[-1] != b"IEND":
            raise ValueError("image container is invalid")


class ArtifactStore:
    """Same-host snapshots. Grants are explicit per project; URNs reveal no paths.

    HTTPS/git/other URNs remain metadata only. This store never performs remote I/O.
    Configure the same store directory and project grants on both enrolled peers.
    """

    PREFIX = "urn:hermes-artifact:"

    def __init__(self, root: Path, *, project_roots: Mapping[str, tuple[Path, ...]],
                 max_bytes: int = 1024 * 1024, private_roots: tuple[Path, ...] = ()):
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or not 1 <= max_bytes <= 4 * 1024 * 1024:
            raise ValueError("artifact size limit must be between 1 byte and 4 MiB")
        self.root = _absolute(root)
        self.max_bytes = max_bytes
        self.project_roots = {project: tuple(_absolute(path) for path in paths)
                              for project, paths in project_roots.items()}
        self.private_roots = tuple(_absolute(path) for path in private_roots)
        for project, paths in self.project_roots.items():
            if not isinstance(project, str) or not project.strip() or not paths:
                raise ValueError("explicit project artifact roots required")
            for path in paths:
                self._not_private(path)
                if Path.home().is_relative_to(path):
                    raise PermissionError("private home or broad ancestor cannot be an approved root")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = _open_directory(self.root)
        os.close(fd)

    def _not_private(self, path: Path):
        if (any(part.casefold() in {".hermes", "memories", "memory", ".ssh", ".gnupg"} for part in path.parts)
                or any(path.is_relative_to(root) for root in self.private_roots)):
            raise PermissionError("private runtime or memory roots cannot be shared")

    def _project_directory(self, project: str) -> Path:
        if project not in self.project_roots:
            raise PermissionError("project has no artifact grant")
        return self.root / hashlib.sha256(project.encode()).hexdigest()

    @classmethod
    def is_stored(cls, ref: ArtifactRef) -> bool:
        return ref.uri.startswith(cls.PREFIX)

    def publish(self, project: str, path: Path, *, kind: str = "file",
                media_type: str = "application/octet-stream", label: str = "") -> ArtifactRef:
        directory = self._project_directory(project)
        candidate = _absolute(path)
        self._not_private(candidate)
        if not any(candidate.is_relative_to(root) for root in self.project_roots[project]):
            raise PermissionError("artifact is outside explicitly approved roots")
        content = _read_regular(candidate, self.max_bytes)
        digest = hashlib.sha256(content).hexdigest()
        ref = ArtifactRef(ArtifactKind(kind), self.PREFIX + digest, media_type, len(content), digest, label)
        directory.mkdir(mode=0o700, exist_ok=True)
        parent = _open_directory(directory)
        # Write a complete temporary snapshot then atomically publish it; never
        # follow/overwrite an existing content address supplied by another writer.
        temporary = "." + uuid.uuid4().hex
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            with os.fdopen(fd, "wb") as target:
                target.write(content)
                target.flush()
                os.fsync(target.fileno())
            try:
                os.link(temporary, digest, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
                os.fsync(parent)
            except FileExistsError:
                pass
        finally:
            try:
                os.unlink(temporary, dir_fd=parent)
            except FileNotFoundError:
                pass
            finally:
                os.close(parent)
        self.read(project, ref)
        return ref

    def read(self, project: str, ref: ArtifactRef) -> bytes:
        directory = self._project_directory(project)
        if not self.is_stored(ref) or ref.uri != self.PREFIX + ref.sha256:
            raise ValueError("only content-addressed local store references can be consumed")
        if ref.size_bytes > self.max_bytes:
            raise ValueError("artifact exceeds the configured size limit")
        content = _read_regular(directory / ref.sha256, self.max_bytes)
        if len(content) != ref.size_bytes or hashlib.sha256(content).hexdigest() != ref.sha256:
            raise ValueError("artifact hash or size mismatch")
        return content

    def verify(self, project: str, refs: tuple[ArtifactRef, ...]):
        if len(refs) > 16 or len(json.dumps([ref.to_wire() for ref in refs]).encode()) > 16 * 1024:
            raise ValueError("artifact reference metadata exceeds the size limit")
        for ref in refs:
            if ref.is_local_file:
                raise PermissionError("local file paths cannot cross profiles")
            if self.is_stored(ref):
                self.read(project, ref)
