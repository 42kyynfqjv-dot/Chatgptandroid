#!/usr/bin/env python3
"""Fail-closed OS source import, patch checks and local release-evidence gate.

No phone operations, key generation, signing, hosting or publication occur here.
The evidence gate checks consistency, not the truth of a human test report.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import stat
import subprocess
import sys
import tempfile
import urllib.parse
import xml.etree.ElementTree as ET

REPO = pathlib.Path(__file__).resolve().parents[1]
SHA = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
CHECKS = {
    "matched_platform_kernel_vendor_firmware", "app_regressions", "physical_tegu",
    "locked_boot_custom_key", "selinux_enforcing", "file_based_encryption",
    "ota_signature", "avb_chain", "rollback_protection", "upgrade_previous_release",
    "upgrade_to_next_candidate", "recovery_forward_fix", "release_keys_no_test_keys",
    "security_patch_coverage", "licenses_and_notices", "updater_own_endpoint",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(pathlib.Path(path).read_text())


def digest(path):
    h = hashlib.sha256()
    with pathlib.Path(path).open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def hash_value(value):
    return isinstance(value, str) and SHA.fullmatch(value) and value != "0" * 64


def contained(root, relative):
    require(isinstance(relative, str) and relative and not pathlib.Path(relative).is_absolute(), "relative path required")
    root = pathlib.Path(root).resolve()
    result = (root / relative).resolve()
    require(result != root and result.is_relative_to(root), "path escapes its root")
    return result


def own_endpoint(url):
    parsed = urllib.parse.urlparse(url or "")
    host = (parsed.hostname or "").lower()
    return (parsed.scheme == "https" and host and not parsed.username and not parsed.password
            and not parsed.query and not parsed.fragment and "." in host
            and not host.endswith((".invalid", ".example", ".localhost"))
            and host not in {"example.com", "example.org", "example.net", "grapheneos.org"}
            and not host.endswith(".grapheneos.org"))


def validate_lock(lock):
    require(lock.get("schema_version") == 1, "unknown lock version")
    require(lock.get("status") == "verified", "upstream is not cryptographically pinned and reviewed")
    require(lock.get("foundation") == "GrapheneOS" and lock.get("device") == "tegu", "unsupported foundation or device")
    require(lock.get("manifest_url") == "https://github.com/GrapheneOS/platform_manifest.git", "unexpected manifest origin")
    require(re.fullmatch(r"[0-9]{10}", lock.get("tag") or ""), "pin a specific stable tag")
    require(COMMIT.fullmatch(lock.get("manifest_commit") or ""), "manifest commit missing")
    for name in ("allowed_signers_sha256", "patch_series_sha256"):
        require(hash_value(lock.get(name)), f"{name} missing")
    require(dt.date.fromisoformat(lock["platform_security_patch"]) <= dt.date.today(), "future patch level")
    require(lock.get("review_reference"), "review reference missing")
    require(own_endpoint(lock.get("update_url")), "set our real HTTPS update endpoint")
    vendor = lock.get("vendor", {})
    require(vendor.get("build_id") and hash_value(vendor.get("factory_sha256")), "vendor image identity missing")
    require(urllib.parse.urlparse(vendor.get("source_url") or "").scheme == "https", "vendor origin missing")
    kernel = lock.get("kernel", {})
    require(COMMIT.fullmatch(kernel.get("source_commit") or "") and hash_value(kernel.get("prebuilts_sha256")), "kernel identity missing")
    for name in ("ota_cert_sha256", "avb_public_key_sha256", "platform_cert_sha256"):
        require(hash_value(lock.get("keys", {}).get(name)), f"public key fingerprint missing: {name}")


def run(*args, cwd=None, env=None):
    environment = dict(os.environ, GIT_NO_REPLACE_OBJECTS="1")
    if env:
        environment.update(env)
    return subprocess.run(args, cwd=cwd, env=environment, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()


def manifest_data(directory):
    """Reject floating revisions before fetching any project. Includes stay inside signed repo."""
    directory = pathlib.Path(directory).resolve()
    seen, projects, outputs = set(), {}, []

    def visit(relative):
        path = contained(directory, relative)
        require(path not in seen, "repeated/cyclic manifest include")
        seen.add(path)
        root = ET.parse(path).getroot()
        require(root.tag == "manifest", "not a manifest")
        for node in root:
            # Superproject selection is disabled at repo init. Only each project's
            # explicit signed-manifest revision governs this checkout.
            require(node.tag in {"remote", "default", "project", "include", "notice", "manifest-server", "repo-hooks", "contactinfo", "superproject"}, f"unsupported manifest directive: {node.tag}")
            if node.tag == "include":
                visit(node.attrib["name"])
            if node.tag == "project":
                require(COMMIT.fullmatch(node.get("revision", "")), "every project must explicitly pin a commit")
                name = node.get("path", node.get("name"))
                contained(directory, name)
                require(name not in projects, "duplicate project path")
                require(not node.findall("project"), "nested projects require manual support")
                projects[name] = node.attrib["revision"]
                for child in node:
                    require(child.tag in {"copyfile", "linkfile", "annotation"}, "unsupported project directive")
                    if child.tag in {"copyfile", "linkfile"}:
                        outputs.append((child.tag, name, child.attrib["src"], child.attrib["dest"]))

    visit("default.xml")
    require(projects, "manifest has no projects")
    return projects, outputs


def manifest_projects(directory):
    return manifest_data(directory)[0]


def import_sources(args):
    lock = read_json(args.lock)
    validate_lock(lock)
    require(digest(args.signers) == lock["allowed_signers_sha256"], "signer file differs from reviewed fingerprint")
    dest = pathlib.Path(args.destination).resolve()
    require(not dest.exists() or not any(dest.iterdir()), "destination must be a new empty checkout")
    dest.mkdir(parents=True, exist_ok=True)
    run("repo", "init", "--no-use-superproject", "-u", lock["manifest_url"], "-b", "refs/tags/" + lock["tag"], cwd=dest)
    manifests = dest / ".repo/manifests"
    run("git", "-c", "gpg.ssh.allowedSignersFile=" + str(pathlib.Path(args.signers).resolve()), "verify-tag", lock["tag"], cwd=manifests)
    require(run("git", "rev-parse", lock["tag"] + "^{commit}", cwd=manifests) == lock["manifest_commit"], "tag commit differs from pin")
    require(run("git", "rev-parse", "HEAD", cwd=manifests) == lock["manifest_commit"], "manifest HEAD differs from pin")
    require(not run("git", "status", "--porcelain", cwd=manifests), "modified manifest")
    require(not (dest / ".repo/local_manifests").exists(), "local manifests are not permitted in release imports")
    projects = manifest_projects(manifests)
    run("repo", "sync", "-j8", "--fail-fast", cwd=dest)
    for name, commit in projects.items():
        path = contained(dest, name)
        require(run("git", "rev-parse", "HEAD", cwd=path) == commit, f"revision mismatch: {name}")
        require(not run("git", "status", "--porcelain", cwd=path), f"dirty project: {name}")
    exported = dest.parent / (dest.name + "-verified-manifest.xml")
    require(not exported.exists(), "exported manifest path already exists")
    run("repo", "manifest", "-r", "-o", str(exported), cwd=dest)
    print(json.dumps({"status": "source-import-verified", "lock_sha256": digest(args.lock), "projects": len(projects), "exported_manifest_sha256": digest(exported)}))


def selected_patches(args, lock, projects):
    require(digest(args.series) == lock["patch_series_sha256"], "patch series differs from pin")
    series = read_json(args.series)
    require(series.get("schema_version") == 1 and isinstance(series.get("patches"), list), "invalid series")
    groups = {}
    for entry in series["patches"]:
        require(entry.get("project") in projects, "patch target is not in signed manifest")
        require(entry.get("kind") in {"critical", "customization"}, "classify each patch")
        patch = contained(REPO, entry["file"])
        require(patch.is_relative_to(REPO / "os/patches"), "patch must be under os/patches")
        require(hash_value(entry.get("sha256")) and digest(patch) == entry["sha256"], "patch hash mismatch")
        if args.emergency and entry["kind"] != "critical":
            continue
        groups.setdefault(entry["project"], []).append(str(patch))
    return groups


def patch_sources(args):
    lock = read_json(args.lock)
    validate_lock(lock)
    require(digest(args.series) == lock["patch_series_sha256"], "patch series differs from pin")
    manifests = pathlib.Path(args.source).resolve() / ".repo/manifests"
    require(not (pathlib.Path(args.source) / ".repo/local_manifests").exists(), "local manifests are not permitted in release imports")
    require(run("git", "rev-parse", "HEAD", cwd=manifests) == lock["manifest_commit"], "source manifest differs from pin")
    require(not run("git", "status", "--porcelain", cwd=manifests), "modified manifest")
    check_files(manifests, tree_files(manifests, lock["manifest_commit"]), {".git"})
    projects = manifest_projects(manifests)
    for name, commit in projects.items():
        path = contained(args.source, name)
        require(run("git", "rev-parse", "HEAD", cwd=path) == commit, f"source revision mismatch: {name}")
        require(not run("git", "status", "--porcelain", cwd=path), f"dirty source project: {name}")
    groups = selected_patches(args, lock, projects)
    for name, patches in groups.items():
        path = contained(args.source, name)
        require(not run("git", "status", "--porcelain", cwd=path), f"dirty patch target: {path}")
        run("git", "apply", "--check", "--index", *patches, cwd=path)
    if args.apply:
        for name, patches in groups.items():
            path = contained(args.source, name)
            run("git", "apply", "--index", *patches, cwd=path)
    print(json.dumps({"status": "patches-applied" if args.apply else "patch-checks-passed", "projects": len(groups), "emergency": args.emergency}))


def tree_files(project, tree):
    """Read raw Git objects; no worktree filters, ignore rules or stat-cache trust."""
    raw = subprocess.run(("git", "ls-tree", "-rz", "--full-tree", tree), cwd=project,
                         env=dict(os.environ, GIT_NO_REPLACE_OBJECTS="1"),
                         check=True, stdout=subprocess.PIPE).stdout
    files = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, name = record.split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split()
        require(kind == "blob" and mode in {"100644", "100755", "120000"}, "unsupported Git tree entry; manual provenance support required")
        files[os.fsdecode(name)] = (mode, oid)
    return files


def blob_hash(path, mode):
    if mode == "120000":
        require(path.is_symlink(), f"expected symlink: {path}")
        content = os.fsencode(os.readlink(path))
        return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode), f"expected regular file: {path}")
    require(bool(info.st_mode & 0o111) == (mode == "100755"), f"executable mode differs: {path}")
    result = hashlib.sha1(b"blob " + str(info.st_size).encode() + b"\0")
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def check_files(root, expected, ignored):
    """Check all bytes/modes and reject extras, including files ignored by Git."""
    root = pathlib.Path(root)
    directories = {str(parent) for name in expected for parent in pathlib.PurePosixPath(name).parents if str(parent) != "."}
    # Ignored paths are fixed Git/Repo metadata paths, never user-provided globs.
    directories |= {str(parent) for name in ignored for parent in pathlib.PurePosixPath(name).parents if str(parent) != "."}
    observed = set()
    for current, dirs, files in os.walk(root, followlinks=False):
        base = pathlib.Path(current)
        for name in list(dirs):
            item = base / name
            relative = item.relative_to(root).as_posix()
            if relative in ignored:
                dirs.remove(name)
            elif item.is_symlink():
                dirs.remove(name)
                files.append(name)
            else:
                require(relative in directories, f"unexpected directory: {relative}")
        for name in files:
            item = base / name
            relative = item.relative_to(root).as_posix()
            if relative in ignored:
                continue
            require(relative in expected, f"unexpected file: {relative}")
            mode, oid = expected[relative]
            require(blob_hash(item, mode) == oid, f"working tree content differs: {relative}")
            if mode == "120000":
                require(item.resolve().is_relative_to(root.resolve()), f"symlink escapes tree: {relative}")
            observed.add(relative)
    require(observed == expected.keys(), "expected source files missing: " + ", ".join(sorted(expected.keys() - observed)[:10]))


def verify_tree(args):
    """Authenticate the exact prepared tree before any checkout code executes.

    Generated vendor/build inputs are intentionally not exempted. Until a reviewed
    generated-input inventory is implemented, such extras block a full OS build.
    """
    lock = read_json(args.lock)
    validate_lock(lock)
    source = pathlib.Path(args.source).resolve()
    manifests = source / ".repo/manifests"
    require(not (source / ".repo/local_manifests").exists(), "local manifests are not permitted")
    require(run("git", "rev-parse", "HEAD", cwd=manifests) == lock["manifest_commit"], "source manifest differs from pin")
    require(run("git", "write-tree", cwd=manifests) == run("git", "rev-parse", "HEAD^{tree}", cwd=manifests), "manifest index differs")
    check_files(manifests, tree_files(manifests, lock["manifest_commit"]), {".git"})
    projects, outputs = manifest_data(manifests)
    groups = selected_patches(args, lock, projects)
    expected = {}
    for name, commit in projects.items():
        project = contained(source, name)
        require(run("git", "rev-parse", "HEAD", cwd=project) == commit, f"source revision mismatch: {name}")
        with tempfile.TemporaryDirectory(prefix="os-expected-index-") as temp:
            index = {"GIT_INDEX_FILE": str(pathlib.Path(temp) / "index")}
            run("git", "read-tree", commit, cwd=project, env=index)
            if name in groups:
                run("git", "apply", "--cached", *groups[name], cwd=project, env=index)
            tree = run("git", "write-tree", cwd=project, env=index)
        require(run("git", "write-tree", cwd=project) == tree, f"index differs from expected patches: {name}")
        for relative, identity in tree_files(project, tree).items():
            full = name + "/" + relative
            require(full not in expected, "overlapping tracked project files")
            expected[full] = identity
    for kind, project, original, destination in outputs:
        # Validate lexical names without resolving pre-existing links first.
        for value in (original, destination):
            require(value and not pathlib.PurePosixPath(value).is_absolute() and ".." not in pathlib.PurePosixPath(value).parts, "unsafe manifest output path")
        original = project + "/" + original
        require(destination not in expected, "manifest output collides with tracked source")
        if kind == "copyfile":
            require(original in expected and expected[original][0] != "120000", "copyfile source must be a tracked regular file")
            expected[destination] = expected[original]
        else:
            require(original in expected or any(path.startswith(original + "/") for path in expected), "linkfile source is not tracked")
            target = os.fsencode(os.path.relpath(source / original, (source / destination).parent))
            expected[destination] = ("120000", hashlib.sha1(b"blob " + str(len(target)).encode() + b"\0" + target).hexdigest())
    ignored = {".repo"} | {name + "/.git" for name in projects}
    check_files(source, expected, ignored)
    print(json.dumps({"status": "prepared-tree-verified", "projects": len(projects), "files": len(expected), "emergency": args.emergency}))


def validate_release(lock, evidence, base, lock_path):
    validate_lock(lock)
    require(evidence.get("schema_version") == 1 and evidence.get("device") == "tegu", "release identity invalid")
    require(evidence.get("source_lock_sha256") == digest(lock_path), "release built against another lock")
    release = evidence.get("release_id")
    require(isinstance(release, str) and re.fullmatch(r"[a-zA-Z0-9._-]{1,80}", release), "release ID missing")
    require(evidence.get("mode") in {"normal", "emergency"}, "release mode missing")
    build, previous = evidence.get("build_number"), evidence.get("previous_build_number")
    require(type(build) is int and type(previous) is int and build > previous >= 0, "build numbers must increase")
    require(evidence.get("security_patch") == lock["platform_security_patch"], "patch level differs from reviewed coverage")
    require(evidence.get("update_url") == lock["update_url"] and evidence.get("keys") == lock["keys"], "update identity changed")
    artifacts = evidence.get("artifacts", {})
    for name in ("ota", "factory", "signed_target_files", "manifest", "sbom"):
        item = artifacts.get(name, {})
        require(hash_value(item.get("sha256")), f"missing artifact digest: {name}")
        require(digest(contained(base, item.get("path"))) == item["sha256"], f"artifact hash mismatch: {name}")
    checks = evidence.get("checks", {})
    require(CHECKS <= checks.keys(), "required validation evidence missing: " + ", ".join(sorted(CHECKS - checks.keys())))
    for name in CHECKS:
        record = checks[name]
        require(hash_value(record.get("sha256")), f"report digest missing: {name}")
        report_path = contained(base, record.get("path"))
        require(digest(report_path) == record["sha256"], f"report hash mismatch: {name}")
        report = read_json(report_path)
        require(report.get("release_id") == release and report.get("ota_sha256") == artifacts["ota"]["sha256"], f"report belongs to another release: {name}")
        require(report.get("check") == name and report.get("passed") is True and report.get("reviewer") and report.get("details"), f"failed or incomplete check: {name}")
    require(evidence.get("release_review_reference"), "release review missing")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=pathlib.Path, default=REPO / "os/upstream-lock.json")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate-lock")
    importer = commands.add_parser("import")
    importer.add_argument("--signers", required=True)
    importer.add_argument("--destination", required=True)
    patches = commands.add_parser("patches")
    patches.add_argument("--source", required=True)
    patches.add_argument("--series", default=REPO / "os/patch-series.json")
    patches.add_argument("--apply", action="store_true")
    patches.add_argument("--emergency", action="store_true")
    tree = commands.add_parser("verify-tree")
    tree.add_argument("--source", required=True)
    tree.add_argument("--series", default=REPO / "os/patch-series.json")
    tree.add_argument("--emergency", action="store_true")
    release = commands.add_parser("release-gate")
    release.add_argument("evidence", type=pathlib.Path)
    args = parser.parse_args()
    try:
        if args.command == "import":
            import_sources(args)
        elif args.command == "patches":
            patch_sources(args)
        elif args.command == "verify-tree":
            verify_tree(args)
        elif args.command == "release-gate":
            validate_release(read_json(args.lock), read_json(args.evidence), args.evidence.resolve().parent, args.lock)
            print("Evidence consistency gate passed; authorized signer/release review still required.")
        else:
            validate_lock(read_json(args.lock))
            print("Lock structure accepted; import independently verifies the signed source tag.")
    except (ValueError, KeyError, OSError, TypeError, ET.ParseError, subprocess.CalledProcessError) as error:
        print(f"BLOCKED: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
