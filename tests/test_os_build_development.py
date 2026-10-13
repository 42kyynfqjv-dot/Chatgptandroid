"""Run the development shell wrapper against instrumented, non-building commands."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


WRAPPER = Path(__file__).resolve().parents[1] / "scripts/os-build-development.sh"


class DevelopmentBuildWrapperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project with spaces"
        (self.project / "scripts").mkdir(parents=True)
        self.wrapper = self.project / "scripts/os-build-development.sh"
        shutil.copyfile(WRAPPER, self.wrapper)
        self.source = self.root / "prepared checkout"
        (self.source / "build").mkdir(parents=True)
        self.inventory = self.root / "reviewed inventory.json"
        self.inventory.write_text("synthetic inventory; fake verifier boundary")
        self.artifacts = self.root / "external artifacts"
        self.artifacts.mkdir()
        self.log = self.root / "events.jsonl"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.program("uname", '#!/bin/sh\nprintf "%s\\n" "${TEST_SYSTEM:-Linux}"\n')
        self.program("python3", f"#!{sys.executable}\n" + '''import json, os, pathlib, shutil, sys
from unittest.mock import patch
def event(value):
    with open(os.environ["TEST_LOG"], "a") as log: log.write(json.dumps(value) + "\\n")
if sys.argv[1] != "-":
    event(["verify", *sys.argv[1:]])
    raise SystemExit(int(os.environ.get("TEST_VERIFY_EXIT", "0")))
event(["preflight"])
script = sys.stdin.read()
original_read = pathlib.Path.read_text
original_exists = pathlib.Path.exists
def read(path, *args, **kwargs):
    if str(path) == "/proc/meminfo":
        return "MemTotal: " + os.environ.get("TEST_MEMORY_KIB", str(64 * 1024**2)) + " kB\\n"
    if str(path).startswith("/sys/fs/cgroup/"): return os.environ.get("TEST_CGROUP", "max")
    return original_read(path, *args, **kwargs)
def exists(path):
    if str(path).startswith("/sys/fs/cgroup/"): return True
    return original_exists(path)
sys.argv = sys.argv[1:]
with patch.object(pathlib.Path, "read_text", read), patch.object(pathlib.Path, "exists", exists), \\
     patch.object(shutil, "disk_usage", return_value=shutil._ntuple_diskusage(0, 0, int(os.environ.get("TEST_FREE", str(400 * 1024**3))))):
    exec(compile(script, "actual-wrapper-preflight", "exec"))
''')
        self.program("record", f"#!{sys.executable}\n" + '''import json, os, sys
with open(os.environ["TEST_LOG"], "a") as log:
    log.write(json.dumps([*sys.argv[1:], {name: os.environ.get(name) for name in (
        "OFFICIAL_BUILD", "OUT_DIR", "OUT_DIR_COMMON_BASE", "DIST_DIR", "BUILD_NUMBER", "BUILD_DATETIME",
        "TOP", "ANDROID_BUILD_TOP", "USE_LEFTOVERS")}]) + "\\n")
''')
        (self.source / "build/envsetup.sh").write_text('''record source
lunch() { record lunch "$@"; return "${TEST_LUNCH_EXIT:-0}"; }
get_build_var() {
  record packages "$@"
  if [[ "$1" == PRODUCT_PACKAGES_DEBUG ]]; then
    printf '%s\\n' "${TEST_PACKAGES_DEBUG:-}"
    return "${TEST_DEBUG_EXIT:-0}"
  fi
  printf '%s\\n' "${TEST_PACKAGES:-AIHome Settings}"
  return "${TEST_PACKAGES_EXIT:-0}"
}
m() { record build "$@"; return "${TEST_BUILD_EXIT:-0}"; }
''')
        self.env = {**os.environ, "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
                    "TEST_LOG": str(self.log), "BUILD_NUMBER": "1234", "BUILD_DATETIME": "1700000000"}
        for key in ("BUILD_JOBS", "BASH_ENV", "ENV"):
            self.env.pop(key, None)

    def program(self, name, value):
        path = self.bin / name
        path.write_text(value)
        path.chmod(0o755)

    def run_wrapper(self, args=None, **updates):
        self.log.unlink(missing_ok=True)
        command = ["bash", str(self.wrapper)] + (args if args is not None else [str(self.source),
            "--generated-inventory", str(self.inventory), "--artifacts", str(self.artifacts)])
        return subprocess.run(command, env={**self.env, **updates}, capture_output=True, text=True)

    def events(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_verified_userdebug_build_has_exact_targets_and_sanitized_environment(self):
        result = self.run_wrapper(OFFICIAL_BUILD="true", OUT_DIR="elsewhere", OUT_DIR_COMMON_BASE="elsewhere", DIST_DIR="elsewhere")
        self.assertEqual(result.returncode, 0, result.stderr)
        events = self.events()
        self.assertEqual([event[0] for event in events], ["preflight", "verify", "source", "lunch", "packages", "packages", "build"])
        self.assertEqual(events[1][1:], [str(self.project / "scripts/os-pipeline.py"), "--lock",
            str(self.project / "os/development-lock.json"), "--development", "verify-tree", "--source", str(self.source),
            "--generated-inventory", str(self.inventory), "--artifacts", str(self.artifacts)])
        self.assertEqual(events[3][1:-1], ["tegu-cur-userdebug"])
        self.assertEqual([events[4][1], events[5][1]], ["PRODUCT_PACKAGES", "PRODUCT_PACKAGES_DEBUG"])
        self.assertEqual(events[-1][1:-1], ["-j8", "target-files-package", "otatools-package"])
        for event in (events[2], events[-1]):
            self.assertEqual(event[-1], {"OFFICIAL_BUILD": None, "OUT_DIR": str(self.source / "out"),
                "OUT_DIR_COMMON_BASE": None, "DIST_DIR": None, "BUILD_NUMBER": "1234", "BUILD_DATETIME": "1700000000",
                "TOP": str(self.source), "ANDROID_BUILD_TOP": str(self.source), "USE_LEFTOVERS": None})

    def test_inherited_top_cannot_source_an_unverified_checkout(self):
        foreign = self.root / "unverified checkout"
        (foreign / "build").mkdir(parents=True)
        (foreign / "build/continuation.sh").write_text("record unverified-source\n")
        (self.source / "build/continuation.sh").write_text("record verified-continuation\n")
        setup = self.source / "build/envsetup.sh"
        setup.write_text('source "$TOP/build/continuation.sh"\n' + setup.read_text())
        result = self.run_wrapper(TOP=str(foreign), ANDROID_BUILD_TOP=str(foreign), USE_LEFTOVERS="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        events = self.events()
        self.assertIn("verified-continuation", [event[0] for event in events])
        self.assertNotIn("unverified-source", [event[0] for event in events])
        self.assertIsNone(events[-1][-1]["USE_LEFTOVERS"])

    def test_parser_rejects_missing_duplicate_and_unknown_options_before_code_execution(self):
        cases = [[], [str(self.source)], [str(self.source), "--generated-inventory"],
                 [str(self.source), "--artifacts", str(self.artifacts)],
                 [str(self.source), "--lock", "other.json"], [str(self.source), "--emergency"],
                 [str(self.source), "--generated-inventory", str(self.inventory), "--generated-inventory", str(self.inventory)],
                 [str(self.source), "--artifacts", str(self.artifacts), "--artifacts", str(self.artifacts)]]
        for args in cases:
            with self.subTest(args=args):
                self.assertNotEqual(self.run_wrapper(args).returncode, 0)
                self.assertEqual(self.events(), [])

    def test_explicit_numeric_build_identity_and_positive_jobs_required(self):
        for key, values in {"BUILD_NUMBER": ("", "next", "1;touch nope"), "BUILD_DATETIME": ("", "now", "-1"),
                            "BUILD_JOBS": ("0", "-1", "1.5", "1 --other", "08")}.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    self.assertNotEqual(self.run_wrapper(**{key: value}).returncode, 0)
                    self.assertEqual(self.events(), [])
        self.assertEqual(self.run_wrapper(BUILD_JOBS="2").returncode, 0)
        self.assertEqual(self.events()[-1][1], "-j2")

    def test_linux_and_real_resource_threshold_checks_run_before_source(self):
        for overrides in ({"TEST_SYSTEM": "Darwin"}, {"TEST_MEMORY_KIB": str(64 * 1024**2 - 1)},
                          {"TEST_CGROUP": str(64 * 1024**3 - 1)}, {"TEST_FREE": str(400 * 1024**3 - 1)}):
            with self.subTest(overrides=overrides):
                self.assertNotEqual(self.run_wrapper(**overrides).returncode, 0)
                self.assertTrue(all(event[0] == "preflight" for event in self.events()))

    def test_existing_outputs_and_dangling_output_symlink_are_rejected(self):
        output = self.source / "out"
        output.mkdir()
        self.assertNotEqual(self.run_wrapper().returncode, 0)
        self.assertEqual(self.events(), [["preflight"]])
        output.rmdir()
        output.symlink_to("nonexistent")
        self.assertNotEqual(self.run_wrapper().returncode, 0)
        self.assertEqual(self.events(), [["preflight"]])

    def test_failed_verification_never_sources_checkout(self):
        result = self.run_wrapper(TEST_VERIFY_EXIT="7")
        self.assertEqual(result.returncode, 7)
        self.assertEqual([event[0] for event in self.events()], ["preflight", "verify"])

    def test_resolved_updater_empty_or_failed_package_query_never_builds(self):
        for packages in ("AIHome Updater Settings", "Updater:arm64", "//packages/apps/Updater:Updater", " \n\t"):
            with self.subTest(packages=packages):
                self.assertNotEqual(self.run_wrapper(TEST_PACKAGES=packages).returncode, 0)
                self.assertNotIn("build", [event[0] for event in self.events()])
        self.assertNotEqual(self.run_wrapper(TEST_PACKAGES_EXIT="9").returncode, 0)
        self.assertNotIn("build", [event[0] for event in self.events()])

    def test_userdebug_additional_packages_cannot_include_updater(self):
        self.assertNotEqual(self.run_wrapper(TEST_PACKAGES_DEBUG="DebugTool Updater").returncode, 0)
        self.assertNotIn("build", [event[0] for event in self.events()])
        self.assertNotEqual(self.run_wrapper(TEST_DEBUG_EXIT="8").returncode, 0)
        self.assertNotIn("build", [event[0] for event in self.events()])
        self.assertEqual(self.run_wrapper(TEST_PACKAGES_DEBUG="DebugTool").returncode, 0)

    def test_lunch_and_build_failure_propagate_without_success_claim(self):
        result = self.run_wrapper(TEST_LUNCH_EXIT="3")
        self.assertEqual(result.returncode, 3)
        self.assertNotIn("build", [event[0] for event in self.events()])
        result = self.run_wrapper(TEST_BUILD_EXIT="4")
        self.assertEqual(result.returncode, 4)
        self.assertNotIn("Development artifacts are in", result.stdout)


if __name__ == "__main__":
    unittest.main()
