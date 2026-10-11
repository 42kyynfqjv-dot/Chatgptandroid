"""Meaningful failure tests for source pinning and the release evidence boundary."""
import importlib.util
import json
import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts/os-pipeline.py"
SPEC = importlib.util.spec_from_file_location("os_pipeline", SCRIPT)
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.lock = {
            "schema_version": 1, "status": "verified", "foundation": "GrapheneOS", "device": "tegu",
            "manifest_url": "https://github.com/GrapheneOS/platform_manifest.git", "tag": "2026100600",
            "manifest_commit": "a" * 40, "allowed_signers_sha256": "a" * 64,
            "patch_series_sha256": "a" * 64, "platform_security_patch": "2026-10-05",
            "review_reference": "synthetic test review", "update_url": "https://updates.test-distribution.org/",
            "vendor": {"build_id": "SYNTHETIC", "factory_sha256": "a" * 64, "source_url": "https://vendor.test-distribution.org/"},
            "kernel": {"source_commit": "a" * 40, "prebuilts_sha256": "a" * 64},
            "keys": {key: "a" * 64 for key in ("ota_cert_sha256", "avb_public_key_sha256", "platform_cert_sha256")},
        }
        self.lock_path = self.root / "lock.json"
        self.lock_path.write_text(json.dumps(self.lock))
        self.evidence = {
            "schema_version": 1, "device": "tegu", "release_id": "test-only", "mode": "normal",
            "source_lock_sha256": pipeline.digest(self.lock_path), "build_number": 2, "previous_build_number": 1,
            "security_patch": self.lock["platform_security_patch"], "update_url": self.lock["update_url"],
            "keys": self.lock["keys"], "release_review_reference": "synthetic test review", "artifacts": {}, "checks": {},
        }
        for name in ("ota", "factory", "signed_target_files", "manifest", "sbom"):
            path = self.root / name
            path.write_text("synthetic test artifact: " + name)
            self.evidence["artifacts"][name] = {"path": name, "sha256": pipeline.digest(path)}
        for name in pipeline.CHECKS:
            path = self.root / (name + ".json")
            path.write_text(json.dumps({"release_id": "test-only", "ota_sha256": self.evidence["artifacts"]["ota"]["sha256"], "check": name, "passed": True, "reviewer": "unit test", "details": "synthetic unit test data"}))
            self.evidence["checks"][name] = {"path": path.name, "sha256": pipeline.digest(path)}

    def check(self):
        pipeline.validate_release(self.lock, self.evidence, self.root, self.lock_path)

    def test_complete_synthetic_evidence(self):
        self.check()

    def test_emergency_still_requires_every_security_check(self):
        self.evidence["mode"] = "emergency"
        del self.evidence["checks"]["physical_tegu"]
        with self.assertRaisesRegex(ValueError, "required validation"):
            self.check()

    def test_checked_in_lock_refuses_release(self):
        with self.assertRaisesRegex(ValueError, "not cryptographically pinned"):
            pipeline.validate_lock(pipeline.read_json(SCRIPT.parents[1] / "os/upstream-lock.json"))

    def test_foreign_ota_report_rejected(self):
        record = self.evidence["checks"]["physical_tegu"]
        path = self.root / record["path"]
        data = json.loads(path.read_text())
        data["ota_sha256"] = "b" * 64
        path.write_text(json.dumps(data))
        record["sha256"] = pipeline.digest(path)
        with self.assertRaisesRegex(ValueError, "another release"):
            self.check()

    def test_artifact_tampering_rejected(self):
        (self.root / "ota").write_text("tampered")
        with self.assertRaisesRegex(ValueError, "artifact hash mismatch"):
            self.check()

    def test_no_downgrade(self):
        self.evidence["build_number"] = 1
        with self.assertRaisesRegex(ValueError, "must increase"):
            self.check()

    def test_no_unreviewed_patch_level(self):
        self.evidence["security_patch"] = "2026-11-05"
        with self.assertRaisesRegex(ValueError, "patch level differs"):
            self.check()

    def test_no_upstream_endpoint(self):
        for url in ("https://releases.grapheneos.org/", "http://updates.test-distribution.org/", "https://updates.example.com.invalid/", "https://user:secret@updates.test-distribution.org/"):
            with self.subTest(url=url):
                self.assertFalse(pipeline.own_endpoint(url))

    def test_traversal_and_symlinks_rejected(self):
        (self.root / "escape").symlink_to(self.root.parent)
        for path in ("../outside", "/tmp/outside", "escape/outside"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                pipeline.contained(self.root, path)


class ManifestTests(unittest.TestCase):
    def test_floating_revision_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            (root / "default.xml").write_text('<manifest><project name="platform/foo" revision="17" /></manifest>')
            with self.assertRaisesRegex(ValueError, "pin a commit"):
                pipeline.manifest_projects(root)

    def test_immutable_manifest_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            (root / "default.xml").write_text('<manifest><include name="pinned.xml" /></manifest>')
            (root / "pinned.xml").write_text('<manifest><project name="platform/foo" path="foo" revision="' + "a" * 40 + '" /></manifest>')
            self.assertEqual(pipeline.manifest_projects(root), {"foo": "a" * 40})

    def test_unhandled_submanifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            (root / "default.xml").write_text('<manifest><submanifest name="surprise" /></manifest>')
            with self.assertRaisesRegex(ValueError, "unsupported manifest"):
                pipeline.manifest_projects(root)


class PatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.project = self.root / "source/foo"
        self.manifests = self.root / "source/.repo/manifests"
        for path in (self.project, self.manifests):
            path.mkdir(parents=True)
            pipeline.run("git", "init", "-q", cwd=path)
        (self.project / "value").write_text("before\n")
        self.commit(self.project)
        commit = pipeline.run("git", "rev-parse", "HEAD", cwd=self.project)
        (self.manifests / "default.xml").write_text('<manifest><project name="foo" revision="' + commit + '" /></manifest>')
        self.commit(self.manifests)
        patches = self.root / "os/patches"
        patches.mkdir(parents=True)
        (self.project / "value").write_text("after\n")
        patch_file = patches / "change.patch"
        patch_file.write_text(pipeline.run("git", "diff", cwd=self.project) + "\n")
        (self.project / "value").write_text("before\n")
        series = self.root / "series.json"
        series.write_text(json.dumps({"schema_version": 1, "patches": [{"project": "foo", "file": "os/patches/change.patch", "sha256": pipeline.digest(patch_file), "kind": "customization"}]}))
        # Pin-validation tests above cover the full production lock; here isolate
        # actual git patch behavior with a verified synthetic manifest/series.
        lock = self.root / "lock.json"
        lock.write_text(json.dumps({"manifest_commit": pipeline.run("git", "rev-parse", "HEAD", cwd=self.manifests), "patch_series_sha256": pipeline.digest(series)}))
        self.args = SimpleNamespace(lock=lock, series=series, source=self.root / "source", emergency=False, apply=True)
        self.addCleanup(patch.stopall)
        patch.object(pipeline, "REPO", self.root).start()
        patch.object(pipeline, "validate_lock").start()

    @staticmethod
    def commit(path):
        pipeline.run("git", "add", ".", cwd=path)
        pipeline.run("git", "-c", "user.name=Pipeline Test", "-c", "user.email=pipeline@example.invalid", "commit", "-qm", "synthetic test", cwd=path)

    def test_actual_patch_applies_to_pinned_clean_project(self):
        pipeline.patch_sources(self.args)
        self.assertEqual((self.project / "value").read_text(), "after\n")

    def test_dirty_source_rejected_without_overwrite(self):
        (self.project / "value").write_text("local change\n")
        with self.assertRaisesRegex(ValueError, "dirty source"):
            pipeline.patch_sources(self.args)
        self.assertEqual((self.project / "value").read_text(), "local change\n")

    def test_emergency_omits_customization_patch(self):
        self.args.emergency = True
        pipeline.patch_sources(self.args)
        self.assertEqual((self.project / "value").read_text(), "before\n")

    def test_patch_target_must_be_in_signed_manifest(self):
        unlisted = self.root / "source/unlisted"
        unlisted.mkdir()
        pipeline.run("git", "init", "-q", cwd=unlisted)
        (unlisted / "value").write_text("before\n")
        self.commit(unlisted)
        series = json.loads(self.args.series.read_text())
        series["patches"][0]["project"] = "unlisted"
        self.args.series.write_text(json.dumps(series))
        lock = json.loads(self.args.lock.read_text())
        lock["patch_series_sha256"] = pipeline.digest(self.args.series)
        self.args.lock.write_text(json.dumps(lock))
        with self.assertRaisesRegex(ValueError, "not in signed manifest"):
            pipeline.patch_sources(self.args)
        self.assertEqual((unlisted / "value").read_text(), "before\n")

    def test_verify_exact_patched_tree(self):
        pipeline.patch_sources(self.args)
        pipeline.verify_tree(self.args)

    def test_verify_rejects_unstaged_mutation_even_assume_unchanged(self):
        pipeline.patch_sources(self.args)
        pipeline.run("git", "update-index", "--assume-unchanged", "value", cwd=self.project)
        (self.project / "value").write_text("unreviewed code\n")
        with self.assertRaisesRegex(ValueError, "working tree content differs"):
            pipeline.verify_tree(self.args)

    def test_verify_rejects_staged_additional_change(self):
        pipeline.patch_sources(self.args)
        (self.project / "value").write_text("unreviewed code\n")
        pipeline.run("git", "add", "value", cwd=self.project)
        with self.assertRaisesRegex(ValueError, "index differs"):
            pipeline.verify_tree(self.args)

    def test_verify_rejects_ignored_file(self):
        pipeline.patch_sources(self.args)
        (self.project / ".git/info/exclude").write_text("evil-script\n")
        (self.project / "evil-script").write_text("unreviewed code\n")
        with self.assertRaisesRegex(ValueError, "unexpected file"):
            pipeline.verify_tree(self.args)

    def test_verify_rejects_root_script_outside_projects(self):
        pipeline.patch_sources(self.args)
        (self.root / "source/bootstrap.sh").write_text("unreviewed code\n")
        with self.assertRaisesRegex(ValueError, "unexpected file"):
            pipeline.verify_tree(self.args)

    def test_verify_rejects_wrong_mode_selection(self):
        pipeline.patch_sources(self.args)
        self.args.emergency = True
        with self.assertRaisesRegex(ValueError, "index differs"):
            pipeline.verify_tree(self.args)

    def test_verify_accepts_critical_only_tree(self):
        self.args.emergency = True
        pipeline.verify_tree(self.args)

    def add_manifest_outputs(self):
        manifest = self.manifests / "default.xml"
        manifest.write_text(manifest.read_text().replace(" /></manifest>", '><linkfile src="value" dest="entrypoint"/><copyfile src="value" dest="copied"/></project></manifest>'))
        self.commit(self.manifests)
        lock = json.loads(self.args.lock.read_text())
        lock["manifest_commit"] = pipeline.run("git", "rev-parse", "HEAD", cwd=self.manifests)
        self.args.lock.write_text(json.dumps(lock))
        pipeline.patch_sources(self.args)
        (self.root / "source/entrypoint").symlink_to("foo/value")
        (self.root / "source/copied").write_text("after\n")

    def test_verify_accepts_correct_linkfile_and_copyfile(self):
        self.add_manifest_outputs()
        pipeline.verify_tree(self.args)

    def test_verify_rejects_replaced_entrypoint_linkfile(self):
        self.add_manifest_outputs()
        entrypoint = self.root / "source/entrypoint"
        entrypoint.unlink()
        entrypoint.write_text("after\n")
        with self.assertRaisesRegex(ValueError, "expected symlink"):
            pipeline.verify_tree(self.args)

    def test_verify_rejects_modified_copyfile(self):
        self.add_manifest_outputs()
        (self.root / "source/copied").write_text("unreviewed code\n")
        with self.assertRaisesRegex(ValueError, "working tree content differs"):
            pipeline.verify_tree(self.args)

    def test_verify_rejects_dirty_manifest_despite_git_stat_flag(self):
        pipeline.patch_sources(self.args)
        pipeline.run("git", "update-index", "--assume-unchanged", "default.xml", cwd=self.manifests)
        (self.manifests / "default.xml").write_text("<manifest/>")
        with self.assertRaisesRegex(ValueError, "working tree content differs"):
            pipeline.verify_tree(self.args)

    def test_patch_rejects_dirty_manifest_despite_git_stat_flag(self):
        pipeline.run("git", "update-index", "--assume-unchanged", "default.xml", cwd=self.manifests)
        (self.manifests / "default.xml").write_text("<manifest/>")
        with self.assertRaisesRegex(ValueError, "working tree content differs"):
            pipeline.patch_sources(self.args)


if __name__ == "__main__":
    unittest.main()
