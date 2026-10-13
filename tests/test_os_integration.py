"""Exercise real patch assembly, pinned bytes, and component source boundaries."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location("os_integration", Path(__file__).resolve().parents[1]
                                            / "scripts/prepare-os-integration.py")
integration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(integration)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / "cache"
        self.base = self.cache / "frameworks/base/config.txt"
        self.base.parent.mkdir(parents=True)
        self.base.write_text("upstream\n")
        (self.root / "component").mkdir()
        (self.root / "component/Gesture.java").write_text("class Gesture {}\n")
        (self.root / "hook.patch").write_text(
            "diff --git a/config.txt b/config.txt\n"
            "--- a/config.txt\n+++ b/config.txt\n@@ -1 +1 @@\n-upstream\n+configured\n")
        self.project = {
            "project": "frameworks/base", "repository": "GrapheneOS/platform_frameworks_base",
            "commit": "a" * 40, "base_files": [{"path": "config.txt",
                "sha256": hashlib.sha256(b"upstream\n").hexdigest()}],
            "hooks": ["hook.patch"],
            "source_trees": [{"source": "component", "destination": "services/core/java"}],
        }
        self.patch_root = mock.patch.object(integration, "ROOT", self.root)
        self.patch_root.start()
        self.addCleanup(self.patch_root.stop)

    def assemble(self):
        return integration.assemble(self.project, self.cache, False, self.root / "unused")

    def test_patch_is_deterministic_and_applies_with_all_source_bytes(self):
        patch = self.assemble()
        self.assertEqual(patch, self.assemble())
        checkout = self.root / "checkout"
        checkout.mkdir()
        integration.git(checkout, "init", "-q")
        (checkout / "config.txt").write_text("upstream\n")
        integration.git(checkout, "add", "--", ".")
        patch_file = self.root / "result.patch"
        patch_file.write_bytes(patch)
        integration.git(checkout, "apply", "--check", "--index", str(patch_file))
        integration.git(checkout, "apply", "--index", str(patch_file))
        self.assertEqual((checkout / "config.txt").read_text(), "configured\n")
        self.assertEqual((checkout / "services/core/java/Gesture.java").read_text(), "class Gesture {}\n")

    def test_changed_upstream_is_rejected_without_fetching(self):
        self.base.write_text("tampered\n")
        with mock.patch.object(integration.urllib.request, "urlopen") as network:
            with self.assertRaisesRegex(ValueError, "differs from pin"):
                self.assemble()
            network.assert_not_called()

    def test_missing_base_requires_explicit_fetch(self):
        self.base.unlink()
        with self.assertRaisesRegex(ValueError, "missing base file"):
            self.assemble()

    def test_source_edit_changes_patch_and_is_not_hidden_by_cached_base(self):
        first = self.assemble()
        (self.root / "component/Gesture.java").write_text("class ChangedGesture {}\n")
        self.assertNotEqual(first, self.assemble())

    def test_caller_git_selectors_cannot_mutate_an_external_index_or_worktree(self):
        outside = self.root / "caller-checkout"
        outside.mkdir()
        integration.git(outside, "init", "-q")
        (outside / "keep.txt").write_text("caller data\n")
        integration.git(outside, "add", "--", ".")
        index = outside / ".git/index"
        before = index.read_bytes()
        with mock.patch.dict(os.environ, {
                "GIT_DIR": str(outside / ".git"), "GIT_WORK_TREE": str(outside),
                "GIT_INDEX_FILE": str(index), "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "core.autocrlf", "GIT_CONFIG_VALUE_0": "true"}):
            self.assertIn(b"class Gesture", self.assemble())
        self.assertEqual(before, index.read_bytes())
        self.assertEqual((outside / "keep.txt").read_text(), "caller data\n")
        self.assertEqual({p.name for p in outside.iterdir()}, {".git", "keep.txt"})

    def test_component_cannot_override_another_component(self):
        self.project["source_trees"].append(self.project["source_trees"][0].copy())
        with self.assertRaisesRegex(ValueError, "replace another source"):
            self.assemble()

    def test_development_pin_rejects_changed_patches_and_upstream(self):
        contract = {"upstream_tag": "2026100600", "manifest_commit": "a" * 40}
        series = b'{"patches": []}\n'
        lock = {"status": "development-pinned", "tag": contract["upstream_tag"],
                "manifest_commit": contract["manifest_commit"],
                "patch_series_sha256": hashlib.sha256(series).hexdigest()}
        (self.root / "os").mkdir()
        path = self.root / "os/development-lock.json"
        path.write_text(json.dumps(lock))
        integration.check_development_pin(contract, series)
        with self.assertRaisesRegex(ValueError, "pin is stale"):
            integration.check_development_pin(contract, series + b" ")
        with self.assertRaisesRegex(ValueError, "another upstream"):
            integration.check_development_pin(dict(contract, manifest_commit="b" * 40), series)
        lock["status"] = "verified"
        path.write_text(json.dumps(lock))
        with self.assertRaisesRegex(ValueError, "not pinned"):
            integration.check_development_pin(contract, series)

    def test_component_symlink_is_rejected(self):
        (self.root / "component/extra.java").symlink_to(self.base)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.assemble()

    def test_unreadable_source_directory_cannot_be_silently_omitted(self):
        def denied_walk(source, onerror, followlinks):
            onerror(PermissionError("unreadable component directory"))
            return iter(())
        with mock.patch.object(integration.os, "walk", side_effect=denied_walk):
            with self.assertRaisesRegex(PermissionError, "unreadable component"):
                integration.add_tree(self.root / "component", self.root / "output")

    def test_unsafe_destinations_are_rejected(self):
        for name in (".", "../escape", "/absolute", "a/../escape", "a//b", "a/.git/b", "a/.repo/b", "a?url=evil"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                integration.relative(name)

    def test_symlinked_parent_cannot_escape(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.root / "component/link").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "escapes root"):
            integration.within(self.root / "component", "link/target")

    def test_symlinked_parent_cannot_alias_another_canonical_source(self):
        (self.root / "alias").symlink_to(self.root / "component", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink path component"):
            integration.within(self.root, "alias/Gesture.java")


if __name__ == "__main__":
    unittest.main()
