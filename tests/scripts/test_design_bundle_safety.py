"""Offline regression checks for design bundle copy and manifest safety.

Run directly with the runtime Python; no live profile or generation is used.
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def load_script(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, REPO / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INSTALLER = load_script("design_installer", "scripts/install_design_profile.py")
VERIFIER = load_script("design_verifier", "scripts/verify_design_profile.py")


class DesignCopySafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "home"
        self.root.mkdir()
        self.src = self.base / "source"
        self.src.mkdir()
        (self.src / "keep.md").write_text("new", encoding="utf-8")
        self.dst = self.root / "skills" / "bundle"
        self.backup = self.root / "backups" / "snapshot"
        self.external = self.base / "external"
        self.external.mkdir()
        (self.external / "keep.md").write_text("external keep", encoding="utf-8")
        (self.external / "stale.md").write_text("external stale", encoding="utf-8")

    def assert_external_untouched(self):
        self.assertEqual((self.external / "keep.md").read_text(), "external keep")
        self.assertEqual((self.external / "stale.md").read_text(), "external stale")
        self.assertEqual({p.name for p in self.external.iterdir()}, {"keep.md", "stale.md"})

    def test_prune_rejects_symlinked_destination_root_before_mutation(self):
        self.dst.parent.mkdir(parents=True)
        self.dst.symlink_to(self.external, target_is_directory=True)
        with self.assertRaisesRegex((ValueError, RuntimeError), "symlink"):
            INSTALLER._copy_tree(self.src, self.dst, self.backup, self.root, prune=True)
        self.assert_external_untouched()
        self.assertFalse(self.backup.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
