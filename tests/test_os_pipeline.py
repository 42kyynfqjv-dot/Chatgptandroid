"""Meaningful failure tests for source pinning and the release evidence boundary."""
import importlib.util
import contextlib
import io
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

    def test_generated_approval_requires_both_pin_and_review_reference(self):
        for approval in ({}, {"inventory_sha256": "a" * 64, "review_reference": " "},
                         {"inventory_sha256": "0" * 64, "review_reference": "synthetic review"}):
            with self.subTest(approval=approval), self.assertRaises(ValueError):
                pipeline.validate_lock({**self.lock, "generated_inputs": approval})


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


class GeneratedInputTests(unittest.TestCase):
    """Real Git tree + synthetic archive bytes, never production approvals."""
    def setUp(self):
        self.fixture = PatchTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root, self.args = self.fixture.root, self.fixture.args
        pipeline.patch_sources(self.args)
        self.artifacts = self.root / "inputs"
        self.artifacts.mkdir()
        factory, dependency = self.artifacts / "factory.zip", self.artifacts / "dependency.tar"
        factory.write_bytes(b"synthetic factory archive")
        dependency.write_bytes(b"synthetic dependency archive")
        lock = pipeline.read_json(self.args.lock)
        lock["vendor"] = {"build_id": "SYNTHETIC", "factory_sha256": pipeline.digest(factory), "source_url": "https://vendor.example.invalid/factory.zip"}
        self.args.lock.write_text(json.dumps(lock))
        self.generated = self.fixture.project / "generated"
        self.generated.mkdir(mode=0o755)
        self.payload = self.generated / "payload.bin"
        self.payload.write_bytes(b"synthetic extracted bytes")
        self.payload.chmod(0o644)
        (self.generated / "current").symlink_to("payload.bin")
        (self.generated / "source-value").symlink_to("../value")
        self.plan = {
            "generators": [{"id": "extractor", "project": "foo", "commit": pipeline.run("git", "rev-parse", "HEAD", cwd=self.fixture.project)}],
            "artifacts": [{"id": "factory", "kind": "factory", "path": "factory.zip", "sha256": pipeline.digest(factory), "source_url": lock["vendor"]["source_url"]},
                          {"id": "dependency", "kind": "dependency", "path": "dependency.tar", "sha256": pipeline.digest(dependency), "source_url": "https://deps.example.invalid/dependency.tar"}],
            "roots": [{"path": "foo/generated", "generator": "extractor", "inputs": ["factory", "dependency"]}],
        }
        self.args.plan = self.root / "plan.json"
        self.args.output = self.root / "candidate.json"
        self.args.artifacts = self.artifacts
        self.args.generated_inventory = self.args.output
        self.save_plan()

    def save_plan(self):
        self.args.plan.write_text(json.dumps(self.plan))

    def capture(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            pipeline.capture_generated(self.args)
        return json.loads(output.getvalue())

    def approve(self):
        # Deliberately separate test-only human review from candidate capture.
        lock = pipeline.read_json(self.args.lock)
        lock["generated_inputs"] = {"inventory_sha256": pipeline.digest(self.args.output), "review_reference": "synthetic independent review"}
        self.args.lock.write_text(json.dumps(lock))

    def captured_and_approved(self):
        self.capture()
        self.approve()

    def test_capture_never_approves_and_pinned_inventory_admits_exact_generated_files(self):
        original = self.args.lock.read_bytes()
        result = self.capture()
        self.assertEqual(result["status"], "candidate-needs-independent-review")
        self.assertEqual(self.args.lock.read_bytes(), original)
        with self.assertRaisesRegex(ValueError, "not independently pinned"):
            pipeline.verify_tree(self.args)
        self.approve()
        pipeline.verify_tree(self.args)

    def test_byte_mode_type_and_missing_file_mutations_fail(self):
        self.captured_and_approved()
        original = self.payload.read_bytes()
        for mutation in ("bytes", "mode", "symlink", "missing"):
            with self.subTest(mutation=mutation):
                if mutation == "bytes": self.payload.write_bytes(b"changed")
                if mutation == "mode": self.payload.chmod(0o755)
                if mutation in {"symlink", "missing"}: self.payload.unlink()
                if mutation == "symlink": self.payload.symlink_to("../value")
                with self.assertRaises((ValueError, OSError)):
                    pipeline.verify_tree(self.args)
                if self.payload.is_symlink(): self.payload.unlink()
                self.payload.write_bytes(original)
                self.payload.chmod(0o644)

    def test_unrecorded_ignored_file_and_empty_directory_fail(self):
        self.captured_and_approved()
        (self.fixture.project / ".git/info/exclude").write_text("generated/*\n")
        extra = self.generated / "unreviewed"
        extra.write_text("hidden by Git")
        with self.assertRaisesRegex(ValueError, "unexpected file"):
            pipeline.verify_tree(self.args)
        extra.unlink()
        extra.mkdir()
        with self.assertRaisesRegex(ValueError, "unexpected directory"):
            pipeline.verify_tree(self.args)

    def test_inventory_bytes_and_source_binding_cannot_be_reused(self):
        self.captured_and_approved()
        original = self.args.output.read_bytes()
        self.args.output.write_bytes(original + b" ")
        with self.assertRaisesRegex(ValueError, "not independently pinned"):
            pipeline.verify_tree(self.args)
        self.args.output.write_bytes(original)
        lock = pipeline.read_json(self.args.lock)
        lock["vendor"]["build_id"] = "DIFFERENT"
        self.args.lock.write_text(json.dumps(lock))
        with self.assertRaisesRegex(ValueError, "different source inputs"):
            pipeline.verify_tree(self.args)

    def test_mode_and_generator_commit_are_bound(self):
        self.plan["generators"][0]["commit"] = "b" * 40
        self.save_plan()
        with self.assertRaisesRegex(ValueError, "generator is not pinned"):
            self.capture()
        self.plan["generators"][0]["commit"] = pipeline.run("git", "rev-parse", "HEAD", cwd=self.fixture.project)
        self.save_plan()
        self.captured_and_approved()
        inventory = pipeline.read_json(self.args.output)
        inventory["binding"]["mode"] = "emergency"
        self.args.output.write_text(json.dumps(inventory))
        self.approve()
        with self.assertRaisesRegex(ValueError, "different source inputs"):
            pipeline.verify_tree(self.args)

    def test_input_archives_are_rehashed_and_factory_must_match_lock(self):
        self.captured_and_approved()
        (self.artifacts / "dependency.tar").write_bytes(b"tampered dependency")
        with self.assertRaisesRegex(ValueError, "input artifact hash mismatch"):
            pipeline.verify_tree(self.args)
        self.plan["artifacts"][0]["sha256"] = pipeline.digest(self.artifacts / "dependency.tar")
        self.plan["artifacts"][0]["path"] = "dependency.tar"
        self.save_plan()
        self.args.output = self.root / "second.json"
        with self.assertRaisesRegex(ValueError, "factory input differs"):
            self.capture()

    def test_artifact_inside_checkout_is_not_external_input(self):
        self.args.artifacts = self.root
        for artifact in self.plan["artifacts"]:
            artifact["path"] = "inputs/" + artifact["path"]
        self.plan["artifacts"][1]["path"] = "source/foo/generated/payload.bin"
        self.plan["artifacts"][1]["sha256"] = pipeline.digest(self.payload)
        self.save_plan()
        with self.assertRaisesRegex(ValueError, "input artifact is inside source"):
            self.capture()

    def test_tracked_root_and_parent_symlink_alias_rejected(self):
        self.plan["roots"][0]["path"] = "foo/value"
        self.save_plan()
        with self.assertRaisesRegex(ValueError, "overlaps tracked source"):
            self.capture()
        self.plan["roots"][0]["path"] = "foo/generated"
        self.save_plan()
        project = self.fixture.project
        actual = project.with_name("actual")
        project.rename(actual)
        project.symlink_to(actual.name)
        with self.assertRaisesRegex(ValueError, "symlinked inventory parent"):
            self.capture()

    def test_nested_git_outputs_and_noncanonical_paths_rejected(self):
        for path in ("foo/generated/.git", "out", "dist", "foo//generated", "foo/../generated", "./foo/generated", "foo/generated/", "foo\\generated"):
            with self.subTest(path=path):
                self.plan["roots"][0]["path"] = path
                self.save_plan()
                with self.assertRaises(ValueError): self.capture()
        self.plan["roots"][0]["path"] = "foo/generated"
        self.save_plan()
        (self.generated / ".git").mkdir()
        with self.assertRaisesRegex(ValueError, "metadata or build output"):
            self.capture()

    def test_dependency_dist_subdirectory_is_explicitly_inventoried(self):
        # Package distributions are legitimate immutable inputs, distinct from
        # checkout-root out/ and dist/ produced by the OS build itself.
        package = self.generated / "dist"
        package.mkdir(mode=0o755)
        (package / "index.js").write_text("synthetic dependency distribution")
        (package / "index.js").chmod(0o644)
        self.captured_and_approved()
        pipeline.verify_tree(self.args)
        (package / "index.js").write_text("unreviewed dependency change")
        with self.assertRaisesRegex(ValueError, "generated content or mode differs"):
            pipeline.verify_tree(self.args)

    def test_reviewed_inventory_cannot_be_silently_omitted(self):
        self.captured_and_approved()
        self.args.generated_inventory = self.args.artifacts = None
        with self.assertRaisesRegex(ValueError, "reviewed generated inventory must be supplied"):
            pipeline.verify_tree(self.args)

    def test_symlink_escape_metadata_checkout_root_and_changed_target_rejected(self):
        link = self.generated / "current"
        for target in ("../../../outside", "../.git/config", "../../", "../"):
            with self.subTest(target=target):
                link.unlink()
                link.symlink_to(target)
                with self.assertRaises((ValueError, OSError)):
                    self.capture()
        link.unlink()
        link.symlink_to("payload.bin")
        self.captured_and_approved()
        link.unlink()
        link.symlink_to("../value")
        with self.assertRaisesRegex(ValueError, "generated content or mode differs"):
            pipeline.verify_tree(self.args)

    def test_duplicate_case_alias_missing_directory_and_override_entries_fail(self):
        self.captured_and_approved()
        original = pipeline.read_json(self.args.output)
        for mutation in ("duplicate", "case", "directory", "override"):
            with self.subTest(mutation=mutation):
                inventory = json.loads(json.dumps(original))
                entry = next(e for e in inventory["entries"] if e["path"].endswith("payload.bin"))
                if mutation in {"duplicate", "case"}:
                    extra = dict(entry)
                    if mutation == "case": extra["path"] = extra["path"].replace("payload.bin", "PAYLOAD.bin")
                    inventory["entries"].append(extra)
                if mutation == "directory": inventory["entries"] = [e for e in inventory["entries"] if e["kind"] != "directory"]
                if mutation == "override": entry["path"] = "foo/value"
                self.args.output.write_text(json.dumps(inventory))
                self.approve()
                with self.assertRaises(ValueError): pipeline.verify_tree(self.args)

    def test_capture_preserves_tracked_mutation_rejection_and_never_overwrites_output(self):
        (self.fixture.project / "value").write_text("not the pinned patch")
        with self.assertRaisesRegex(ValueError, "working tree content differs"):
            self.capture()
        (self.fixture.project / "value").write_text("after\n")
        self.capture()
        with self.assertRaisesRegex(ValueError, "new file outside source"):
            self.capture()
        self.args.output = self.generated / "candidate.json"
        with self.assertRaisesRegex(ValueError, "new file outside source"):
            self.capture()

    def test_hardlinks_and_duplicate_json_keys_fail_closed(self):
        (self.generated / "alias").hardlink_to(self.payload)
        with self.assertRaisesRegex(ValueError, "hardlinked"):
            self.capture()
        self.args.plan.write_text('{"generators":[],"generators":[]}')
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            self.capture()

    def test_nested_bare_repository_is_not_a_generated_dependency(self):
        pipeline.run("git", "init", "--bare", "-q", str(self.generated / "nested.git"))
        with self.assertRaisesRegex(ValueError, "nested bare Git"):
            self.capture()

    def test_directory_enumeration_failure_does_not_silently_capture_empty_tree(self):
        actual_walk = pipeline.os.walk
        def broken_walk(root, *args, **kwargs):
            if pathlib.Path(root) == self.generated:
                kwargs["onerror"](PermissionError("synthetic scandir failure"))
            return actual_walk(root, *args, **kwargs)
        with patch.object(pipeline.os, "walk", side_effect=broken_walk):
            with self.assertRaises(PermissionError): self.capture()

    def test_directory_enumeration_failure_also_blocks_verification(self):
        self.captured_and_approved()
        actual_walk = pipeline.os.walk
        def broken_walk(root, *args, **kwargs):
            kwargs["onerror"](PermissionError("synthetic verification scandir failure"))
            return actual_walk(root, *args, **kwargs)
        with patch.object(pipeline.os, "walk", side_effect=broken_walk):
            with self.assertRaises(PermissionError): pipeline.verify_tree(self.args)


class DevelopmentProfileTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ReleaseGateTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.lock = {k: v for k, v in self.fixture.lock.items()
                     if k not in {"kernel", "keys", "update_url", "platform_security_patch"}}
        self.lock["status"] = "development-pinned"
        self.lock_path = self.root / "development-lock.json"
        self.lock_path.write_text(json.dumps(self.lock))

    def test_development_source_does_not_need_release_keys_endpoint_or_kernel_claim(self):
        pipeline.validate_development_lock(self.lock)
        self.assertNotIn("kernel", self.lock)
        self.assertNotIn("keys", self.lock)
        with self.assertRaisesRegex(ValueError, "not cryptographically pinned"):
            pipeline.validate_lock(self.lock)
        with self.assertRaisesRegex(ValueError, "not cryptographically pinned"):
            pipeline.validate_release(self.lock, {}, self.root, self.lock_path)

    def test_source_profiles_require_explicit_matching_status(self):
        with self.assertRaisesRegex(ValueError, "not explicitly pinned"):
            pipeline.validate_development_lock(self.fixture.lock)
        upgraded = {**self.lock, "status": "verified"}
        with self.assertRaises((ValueError, KeyError)):
            pipeline.validate_lock(upgraded)
        with self.assertRaisesRegex(ValueError, "not cryptographically pinned"):
            pipeline.validate_profile(self.lock, SimpleNamespace())

    def test_development_rejects_missing_review_and_mutable_or_incomplete_source_identity(self):
        mutations = [{"tag": "main"}, {"manifest_commit": "latest"}, {"allowed_signers_sha256": "0" * 64},
                     {"patch_series_sha256": None}, {"review_reference": " "}, {"status": "blocked-unverified"},
                     {"foundation": "other"}, {"device": "other"},
                     {"vendor": {**self.lock["vendor"], "factory_sha256": None}},
                     {"vendor": {**self.lock["vendor"], "source_url": "http://vendor.invalid/factory.zip"}}]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                pipeline.validate_development_lock({**self.lock, **mutation})

    def test_cli_development_is_source_only_and_cannot_authorize_release(self):
        argv = [str(SCRIPT), "--lock", str(self.lock_path)]
        for flags, expected in [(["--development", "validate-lock"], 0), (["validate-lock"], 1),
                                (["--development", "release-gate", str(self.root / "absent.json")], 1)]:
            with self.subTest(flags=flags), patch("sys.argv", argv + flags), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as error:
                self.assertEqual(pipeline.main(), expected)
                if "release-gate" in flags:
                    self.assertIn("development profile cannot authorize a release", error.getvalue())

    def test_development_import_still_rejects_bad_signed_tag_before_sync(self):
        signers = self.root / "synthetic-signers"
        signers.write_text("synthetic test public signer; not a real trust root")
        self.lock["allowed_signers_sha256"] = pipeline.digest(signers)
        self.lock_path.write_text(json.dumps(self.lock))
        args = SimpleNamespace(lock=self.lock_path, development=True, signers=signers, destination=self.root / "checkout")
        def commands(*command, **kwargs):
            if "verify-tag" in command:
                raise pipeline.subprocess.CalledProcessError(1, command)
            return ""
        with patch.object(pipeline, "run", side_effect=commands) as run:
            with self.assertRaises(pipeline.subprocess.CalledProcessError):
                pipeline.import_sources(args)
        self.assertTrue(any("verify-tag" in call.args for call in run.call_args_list))
        self.assertFalse(any(call.args[:2] == ("repo", "sync") for call in run.call_args_list))

    def test_development_generated_inputs_still_require_review_and_exact_bytes(self):
        generated = GeneratedInputTests()
        generated.setUp()
        self.addCleanup(generated.doCleanups)
        # Keep the fixture's real synthetic Git commits and hashed archive bytes.
        lock = {**self.lock, **pipeline.read_json(generated.args.lock)}
        generated.args.lock.write_text(json.dumps(lock))
        generated.args.development = True
        generated.capture()
        with self.assertRaisesRegex(ValueError, "not independently pinned"):
            pipeline.verify_tree(generated.args)
        generated.approve()
        pipeline.verify_tree(generated.args)
        generated.payload.write_bytes(b"unreviewed development mutation")
        with self.assertRaisesRegex(ValueError, "generated content or mode differs"):
            pipeline.verify_tree(generated.args)

    def test_development_capture_rejects_unpinned_generator_and_tracked_mutation(self):
        generated = GeneratedInputTests()
        generated.setUp()
        self.addCleanup(generated.doCleanups)
        lock = {**self.lock, **pipeline.read_json(generated.args.lock)}
        generated.args.lock.write_text(json.dumps(lock))
        generated.args.development = True
        original = generated.plan["generators"][0]["commit"]
        generated.plan["generators"][0]["commit"] = "f" * 40
        generated.save_plan()
        with self.assertRaisesRegex(ValueError, "generator is not pinned"):
            generated.capture()
        generated.plan["generators"][0]["commit"] = original
        generated.save_plan()
        (generated.fixture.project / "value").write_text("unreviewed development source")
        with self.assertRaisesRegex(ValueError, "working tree content differs"):
            generated.capture()


if __name__ == "__main__":
    unittest.main()
