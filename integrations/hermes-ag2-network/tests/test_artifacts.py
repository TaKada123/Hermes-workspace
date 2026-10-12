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


def test_artifact_uri_schemes_are_restricted_and_file_scheme_is_case_insensitive():
    wire = {"kind": "file", "uri": "FILE:///private/secret.txt", "media_type": "text/plain",
            "size_bytes": 1, "sha256": "0" * 64, "label": ""}
    ref = ArtifactRef.from_wire(wire)
    assert ref.is_local_file
    with pytest.raises(ValueError, match="scheme"):
        ArtifactRef.from_wire({**wire, "uri": "javascript:alert(1)"})


def test_wire_rejects_local_file_uri_with_invalid_shape():
    wire = {"kind": "image", "uri": "file://", "media_type": "image/png",
            "size_bytes": 1, "sha256": "0" * 64, "label": ""}
    with pytest.raises(ValueError):
        ArtifactRef.from_wire(wire)
