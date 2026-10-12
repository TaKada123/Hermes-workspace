"""Typed, bounded references shared over the AG2 protocol (never file contents)."""
from dataclasses import dataclass
from enum import StrEnum
import hashlib
from pathlib import Path
import re


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
        if not isinstance(self.kind, ArtifactKind):
            raise ValueError("artifact kind must be an ArtifactKind")
        if not self.uri or len(self.uri) > 2048 or "\n" in self.uri:
            raise ValueError("artifact URI must be nonempty and bounded")
        if not self.media_type or len(self.media_type) > 127 or "/" not in self.media_type:
            raise ValueError("artifact media type is invalid")
        if isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int) or self.size_bytes < 0:
            raise ValueError("artifact size must be a nonnegative integer")
        if not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValueError("artifact sha256 must be lowercase hexadecimal")
        if len(self.label) > 256 or "\n" in self.label:
            raise ValueError("artifact label is invalid")

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
    candidate = Path(path).resolve(strict=True)
    roots = tuple(root.resolve(strict=True) for root in approved_roots)
    if not roots or not any(candidate.is_relative_to(root) for root in roots):
        raise PermissionError("artifact is outside explicitly approved roots")
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 0:
        raise ValueError("max_bytes must be a nonnegative integer")
    metadata = candidate.stat()
    if not candidate.is_file():
        raise ValueError("artifact must be a regular file")
    if metadata.st_size > max_bytes:
        raise ValueError("artifact exceeds the configured size limit")
    digest = hashlib.sha256()
    actual_size = 0
    with candidate.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            actual_size += len(chunk)
            if actual_size > max_bytes:
                raise ValueError("artifact exceeds the configured size limit")
            digest.update(chunk)
    return ArtifactRef(kind, candidate.as_uri(), media_type, actual_size, digest.hexdigest(), label)
