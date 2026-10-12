"""Artifact descriptors are typed, size-bounded references, never implicit file reads."""
import hashlib
from pathlib import Path

import pytest

from hermes_ag2_network.artifacts import ArtifactKind, ArtifactRef, verify_local_file


def test_artifact_wire_round_trip_preserves_typed_digest(tmp_path: Path):
    artifact = tmp_path / "checks.txt"
    artifact.write_bytes(b"3 passed\n")
    ref = verify_local_file(artifact, approved_roots=(tmp_path,), max_bytes=64,
                            kind=ArtifactKind.CHECK_REPORT, media_type="text/plain")
    assert ArtifactRef.from_wire(ref.to_wire()) == ref
    assert ref.sha256 == hashlib.sha256(b"3 passed\n").hexdigest()


def test_large_and_unapproved_files_are_rejected(tmp_path: Path):
    outside = tmp_path / "outside.txt"
    outside.write_text("private")
    approved = tmp_path / "approved"
    approved.mkdir()
    with pytest.raises(PermissionError):
        verify_local_file(outside, approved_roots=(approved,), max_bytes=64)
    with pytest.raises(ValueError, match="size limit"):
        verify_local_file(outside, approved_roots=(tmp_path,), max_bytes=2)


def test_wire_rejects_unknown_fields_and_malformed_digest():
    wire = {"kind": "image", "uri": "file:///approved/image.png", "media_type": "image/png",
            "size_bytes": 1, "sha256": "0" * 64, "label": ""}
    with pytest.raises(ValueError):
        ArtifactRef.from_wire({**wire, "private": True})
    with pytest.raises(ValueError):
        ArtifactRef.from_wire({**wire, "sha256": "not-a-digest"})
