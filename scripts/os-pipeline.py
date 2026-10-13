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
import unicodedata
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
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(pathlib.Path(path).read_text(), object_pairs_hook=unique)


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


def validate_source_lock(lock, status, status_error):
    """Shared source authenticity requirements; never authorizes a release."""
    require(lock.get("schema_version") == 1, "unknown lock version")
    require(lock.get("status") == status, status_error)
    require(lock.get("foundation") == "GrapheneOS" and lock.get("device") == "tegu", "unsupported foundation or device")
    require(lock.get("manifest_url") == "https://github.com/GrapheneOS/platform_manifest.git", "unexpected manifest origin")
    require(re.fullmatch(r"[0-9]{10}", lock.get("tag") or ""), "pin a specific stable tag")
    require(COMMIT.fullmatch(lock.get("manifest_commit") or ""), "manifest commit missing")
    for name in ("allowed_signers_sha256", "patch_series_sha256"):
        require(hash_value(lock.get(name)), f"{name} missing")
    require(isinstance(lock.get("review_reference"), str) and lock["review_reference"].strip(), "review reference missing")
    vendor = lock.get("vendor", {})
    require(isinstance(vendor.get("build_id"), str) and vendor["build_id"].strip()
            and hash_value(vendor.get("factory_sha256")), "vendor image identity missing")
    url = urllib.parse.urlsplit(vendor.get("source_url") or "")
    require(url.scheme == "https" and url.hostname and not url.username and not url.password and not url.fragment, "vendor origin missing")
    if "generated_inputs" in lock:
        approval = lock["generated_inputs"]
        require(isinstance(approval, dict) and set(approval) == {"inventory_sha256", "review_reference"}, "invalid generated input approval")
        require(hash_value(approval["inventory_sha256"]) and isinstance(approval["review_reference"], str)
                and approval["review_reference"].strip(), "generated inputs require an inventory pin and review reference")


def validate_lock(lock):
    validate_source_lock(lock, "verified", "upstream is not cryptographically pinned and reviewed")
    require(dt.date.fromisoformat(lock["platform_security_patch"]) <= dt.date.today(), "future patch level")
    require(own_endpoint(lock.get("update_url")), "set our real HTTPS update endpoint")
    kernel = lock.get("kernel", {})
    require(COMMIT.fullmatch(kernel.get("source_commit") or "") and hash_value(kernel.get("prebuilts_sha256")), "kernel identity missing")
    for name in ("ota_cert_sha256", "avb_public_key_sha256", "platform_cert_sha256"):
        require(hash_value(lock.get("keys", {}).get(name)), f"public key fingerprint missing: {name}")


def validate_development_lock(lock):
    """Development source preparation only; keys/update service remain release gates."""
    validate_source_lock(lock, "development-pinned", "development source is not explicitly pinned and reviewed")


def validate_profile(lock, args):
    if getattr(args, "development", False):
        validate_development_lock(lock)
    else:
        validate_lock(lock)


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
    validate_profile(lock, args)
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
    validate_profile(lock, args)
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


def walk_error(error):
    raise error


def check_files(root, expected, ignored, generated=None):
    """Check all bytes/modes and reject extras, including files ignored by Git."""
    root = pathlib.Path(root)
    generated = generated or {}
    directories = {str(parent) for name in expected for parent in pathlib.PurePosixPath(name).parents if str(parent) != "."}
    directories |= {name for name, entry in generated.items() if entry["kind"] == "directory"}
    # Ignored paths are fixed Git/Repo metadata paths, never user-provided globs.
    directories |= {str(parent) for name in ignored for parent in pathlib.PurePosixPath(name).parents if str(parent) != "."}
    observed = set()
    for current, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
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
                if relative in generated:
                    check_generated(item, generated[relative], root, expected, generated, ignored)
                    observed.add(relative)
        for name in files:
            item = base / name
            relative = item.relative_to(root).as_posix()
            if relative in ignored:
                continue
            if relative in generated:
                check_generated(item, generated[relative], root, expected, generated, ignored)
                observed.add(relative)
                continue
            require(relative in expected, f"unexpected file: {relative}")
            mode, oid = expected[relative]
            require(blob_hash(item, mode) == oid, f"working tree content differs: {relative}")
            if mode == "120000":
                require(item.resolve().is_relative_to(root.resolve()), f"symlink escapes tree: {relative}")
            observed.add(relative)
    wanted = expected.keys() | generated.keys()
    require(observed == wanted, "expected source files missing: " + ", ".join(sorted(wanted - observed)[:10]))


def prepared_tree(args, lock):
    """Authenticate tracked/index state and return its exact expected file set."""
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
    return source, projects, expected, ignored


def canonical_path(value):
    require(isinstance(value, str) and value and len(value) <= 4096, "invalid generated path")
    path = pathlib.PurePosixPath(value)
    require(path.parts and not path.is_absolute() and str(path) == value and not {".", ".."} & set(path.parts)
            and "\\" not in value and all(ord(c) >= 32 and ord(c) != 127 for c in value)
            and unicodedata.normalize("NFC", value) == value, "noncanonical generated path")
    require(not {".git", ".repo", ".hg", ".svn"} & {p.casefold() for p in path.parts}
            and path.parts[0].casefold() not in {"out", "dist"},
            "metadata or build output path forbidden")
    return value


def literal_path(root, relative):
    """Never let a symlinked parent turn a lexical inventory name into an alias."""
    canonical_path(relative)
    root = pathlib.Path(root).resolve()
    path = root / relative
    for parent in path.parents:
        if parent == root:
            break
        require(not parent.is_symlink(), "symlinked inventory parent")
    return path


def inventory_binding(lock, emergency):
    # Exclude only the approval of this inventory to avoid a circular digest.
    encoded = json.dumps({k: v for k, v in lock.items() if k != "generated_inputs"}, sort_keys=True, separators=(",", ":")).encode()
    return {"source_lock_sha256": hashlib.sha256(encoded).hexdigest(),
            "manifest_commit": lock["manifest_commit"], "patch_series_sha256": lock["patch_series_sha256"],
            "mode": "emergency" if emergency else "normal", "vendor": lock["vendor"]}


def inventory_plan(plan, lock, projects, expected, source, artifacts):
    require(isinstance(plan, dict) and set(plan) == {"generators", "artifacts", "roots"}, "invalid generated input plan")
    ids = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
    generators, inputs, roots = {}, {}, {}
    for entry in plan["generators"]:
        require(isinstance(entry, dict) and set(entry) == {"id", "project", "commit"}, "invalid generator identity")
        require(ids.fullmatch(entry["id"]) and entry["id"] not in generators, "duplicate or invalid generator ID")
        require(entry["project"] in projects and entry["commit"] == projects[entry["project"]], "generator is not pinned in signed manifest")
        generators[entry["id"]] = entry
    artifacts = pathlib.Path(artifacts).resolve()
    require(artifacts.is_dir() and not artifacts.is_relative_to(source), "input artifacts must be outside source checkout")
    for entry in plan["artifacts"]:
        require(isinstance(entry, dict) and set(entry) == {"id", "kind", "path", "sha256", "source_url"}, "invalid input artifact")
        require(ids.fullmatch(entry["id"]) and entry["id"] not in inputs, "duplicate or invalid input ID")
        require(entry["kind"] in {"factory", "dependency"} and hash_value(entry["sha256"]), "unhashed input artifact")
        url = urllib.parse.urlsplit(entry["source_url"])
        require(url.scheme == "https" and url.hostname and not url.username and not url.password and not url.fragment, "invalid input origin")
        path = literal_path(artifacts, entry["path"])
        require(path.is_file() and not path.is_symlink(), "input artifact must be a regular non-symlink file")
        require(not path.resolve().is_relative_to(source), "input artifact is inside source checkout")
        require(digest(path) == entry["sha256"], "input artifact hash mismatch")
        if entry["kind"] == "factory":
            require(entry["sha256"] == lock["vendor"]["factory_sha256"] and entry["source_url"] == lock["vendor"]["source_url"], "factory input differs from lock")
        inputs[entry["id"]] = entry
    require(sum(e["kind"] == "factory" for e in inputs.values()) == 1, "exactly one locked factory input required")
    directories = {"."} | {str(p) for name in expected for p in pathlib.PurePosixPath(name).parents}
    folded = {name.casefold() for name in expected} | {name.casefold() for name in directories}
    for entry in plan["roots"]:
        require(isinstance(entry, dict) and set(entry) == {"path", "generator", "inputs"}, "invalid generated root")
        name = canonical_path(entry["path"])
        require(entry["generator"] in generators and isinstance(entry["inputs"], list) and entry["inputs"]
                and len(set(entry["inputs"])) == len(entry["inputs"]) and set(entry["inputs"]) <= inputs.keys(), "generated root has unbound provenance")
        require(str(pathlib.PurePosixPath(name).parent) in directories, "generated root parent must be an authenticated source directory")
        require(name.casefold() not in folded and not any(p.startswith(name.casefold() + "/") for p in folded), "generated root overlaps tracked source")
        require(not any(name.casefold() == old.casefold() or name.casefold().startswith(old.casefold() + "/")
                        or old.casefold().startswith(name.casefold() + "/") for old in roots), "overlapping generated roots")
        literal_path(source, name)
        roots[name] = entry
    require(roots and generators and set(generators) == {e["generator"] for e in roots.values()}
            and set(inputs) == {i for e in roots.values() for i in e["inputs"]}, "unused or missing generated provenance")
    return roots


def generated_identity(path):
    info = path.lstat()
    mode = format(stat.S_IMODE(info.st_mode), "04o")
    if stat.S_ISLNK(info.st_mode):
        require(mode == "0777", "unsupported symlink mode")
        target = os.readlink(path)
        require(target and not pathlib.PurePosixPath(target).is_absolute() and "\\" not in target
                and all(ord(c) >= 32 and ord(c) != 127 for c in target), "unsafe generated symlink target")
        return {"kind": "symlink", "mode": mode, "target": target}
    require(mode in {"0444", "0555", "0600", "0644", "0700", "0755"}, "unsafe generated file mode")
    if stat.S_ISDIR(info.st_mode):
        require(mode in {"0555", "0700", "0755"}, "unsafe generated directory mode")
        require(not ((path / "HEAD").is_file() and (path / "objects").is_dir()), "nested bare Git repository forbidden")
        return {"kind": "directory", "mode": mode}
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "special or hardlinked generated file forbidden")
    return {"kind": "file", "mode": mode, "sha256": digest(path)}


def generated_entries(entries, roots, source, expected):
    require(isinstance(entries, list) and entries, "generated inventory has no entries")
    generated, folded = {}, {name.casefold() for name in expected}
    for entry in entries:
        require(isinstance(entry, dict), "invalid generated entry")
        name = canonical_path(entry.get("path"))
        require(sum(name == root or name.startswith(root + "/") for root in roots) == 1, "entry outside declared generated roots")
        require(name.casefold() not in folded, "duplicate or case-aliased generated entry")
        folded.add(name.casefold())
        kind = entry.get("kind")
        fields = {"path", "kind", "mode"} | ({"sha256"} if kind == "file" else {"target"} if kind == "symlink" else set())
        require(kind in {"file", "directory", "symlink"} and set(entry) == fields, "invalid generated entry fields")
        require(kind != "file" or hash_value(entry["sha256"]), "generated file digest missing")
        literal_path(source, name)
        generated[name] = entry
    for name in generated:
        require(not any(str(parent) in generated and generated[str(parent)]["kind"] != "directory"
                        for parent in pathlib.PurePosixPath(name).parents), "generated parent is not a directory")
        root = next(root for root in roots if name == root or name.startswith(root + "/"))
        parent = pathlib.PurePosixPath(name).parent
        while str(parent) == root or str(parent).startswith(root + "/"):
            require(str(parent) in generated and generated[str(parent)]["kind"] == "directory", "unrecorded generated directory")
            parent = parent.parent
    require(set(roots) <= generated.keys(), "generated roots missing from inventory")
    return generated


def check_generated(path, entry, source, expected, generated, ignored):
    require(generated_identity(path) == {k: v for k, v in entry.items() if k != "path"}, "generated content or mode differs: " + entry["path"])
    if entry["kind"] == "symlink":
        target = path.resolve(strict=True)
        require(target.is_relative_to(source.resolve()), "generated symlink escapes source")
        name = target.relative_to(source.resolve()).as_posix()
        canonical_path(name)
        require(not any(p == name or p.startswith(name + "/") for p in ignored), "generated symlink exposes repository metadata")
        directories = {str(p) for n in expected for p in pathlib.PurePosixPath(n).parents}
        require(name in expected or name in generated or name in directories, "generated symlink target is not authenticated")


def verify_tree(args):
    """Admit generated bytes only when an independently reviewed lock pins them."""
    lock = read_json(args.lock)
    validate_profile(lock, args)
    source, projects, expected, ignored = prepared_tree(args, lock)
    inventory_path, artifacts = getattr(args, "generated_inventory", None), getattr(args, "artifacts", None)
    require(bool(inventory_path) == bool(artifacts), "generated inventory and artifacts must be supplied together")
    generated = {}
    if inventory_path:
        approval = lock.get("generated_inputs", {})
        require(approval.get("review_reference") and digest(inventory_path) == approval.get("inventory_sha256"), "generated inventory is not independently pinned and reviewed")
        inventory = read_json(inventory_path)
        require(isinstance(inventory, dict) and set(inventory) == {"schema_version", "binding", "plan", "entries"}
                and inventory["schema_version"] == 1, "invalid generated inventory")
        require(inventory["binding"] == inventory_binding(lock, args.emergency), "generated inventory belongs to different source inputs or mode")
        roots = inventory_plan(inventory["plan"], lock, projects, expected, source, artifacts)
        generated = generated_entries(inventory["entries"], roots, source, expected)
    else:
        require("generated_inputs" not in lock, "reviewed generated inventory must be supplied")
    check_files(source, expected, ignored, generated)
    print(json.dumps({"status": "prepared-tree-verified", "projects": len(projects), "files": len(expected), "generated_entries": len(generated), "emergency": args.emergency}))


def capture_generated(args):
    """Capture a review candidate; matching bytes do not establish derivation."""
    lock = read_json(args.lock)
    validate_profile(lock, args)
    source, projects, expected, ignored = prepared_tree(args, lock)
    output = pathlib.Path(args.output).absolute()
    require(not output.resolve().is_relative_to(source) and not output.exists(), "candidate output must be a new file outside source")
    plan = read_json(args.plan)
    roots = inventory_plan(plan, lock, projects, expected, source, args.artifacts)
    entries = []
    for root in roots:
        path = literal_path(source, root)
        entries.append({"path": root, **generated_identity(path)})
        if path.is_dir() and not path.is_symlink():
            for current, dirs, files in os.walk(path, followlinks=False, onerror=walk_error):
                for name in dirs + files:
                    item = pathlib.Path(current) / name
                    entries.append({"path": item.relative_to(source).as_posix(), **generated_identity(item)})
    generated = generated_entries(entries, roots, source, expected)
    check_files(source, expected, ignored, generated)
    inventory = {"schema_version": 1, "binding": inventory_binding(lock, args.emergency), "plan": plan,
                 "entries": sorted(entries, key=lambda e: e["path"])}
    with output.open("x") as stream:
        json.dump(inventory, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": "candidate-needs-independent-review", "inventory_sha256": digest(output),
                      "notice": "Capture proves observed bytes only, not derivation or approval. The release lock was not changed."}))


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
    parser.add_argument("--development", action="store_true", help="explicit development source profile; never valid for release-gate")
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
    tree.add_argument("--generated-inventory")
    tree.add_argument("--artifacts")
    capture = commands.add_parser("capture-generated", help="capture unapproved generated bytes for independent provenance review")
    capture.add_argument("--source", required=True)
    capture.add_argument("--series", default=REPO / "os/patch-series.json")
    capture.add_argument("--emergency", action="store_true")
    capture.add_argument("--plan", required=True)
    capture.add_argument("--artifacts", required=True)
    capture.add_argument("--output", required=True)
    release = commands.add_parser("release-gate")
    release.add_argument("evidence", type=pathlib.Path)
    args = parser.parse_args()
    try:
        require(not args.development or args.command in {"validate-lock", "import", "patches", "verify-tree", "capture-generated"},
                "development profile cannot authorize a release")
        if args.command == "import":
            import_sources(args)
        elif args.command == "patches":
            patch_sources(args)
        elif args.command == "verify-tree":
            verify_tree(args)
        elif args.command == "capture-generated":
            capture_generated(args)
        elif args.command == "release-gate":
            validate_release(read_json(args.lock), read_json(args.evidence), args.evidence.resolve().parent, args.lock)
            print("Evidence consistency gate passed; authorized signer/release review still required.")
        else:
            validate_profile(read_json(args.lock), args)
            print(("Development source lock accepted; not release authorization. " if args.development else "Lock structure accepted. ")
                  + "Import independently verifies the signed source tag.")
    except (ValueError, KeyError, OSError, TypeError, ET.ParseError, subprocess.CalledProcessError) as error:
        print(f"BLOCKED: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
