#!/usr/bin/env python3
"""Recreate reviewed OS patches against small, pinned upstream source files.

This verifies patch construction, not a framework compile or complete OS image.
It never modifies an Android checkout, a device, release keys, or the release lock.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def require(value, message):
    if not value:
        raise ValueError(message)


def relative(value):
    require(isinstance(value, str) and value, "missing relative path")
    path = PurePosixPath(value)
    require(path.parts and not path.is_absolute() and str(path) == value
            and re.fullmatch(r"[a-zA-Z0-9_./-]+", value)
            and not any(part in {"..", ".git", ".repo"} for part in path.parts),
            f"unsafe relative path: {value}")
    return path


def within(root, value):
    path = Path(root) / relative(value)
    require(path.resolve().is_relative_to(Path(root).resolve()), f"path escapes root: {value}")
    current = Path(root)
    require(not current.is_symlink(), "symlink root is not allowed")
    for part in relative(value).parts:
        current = current / part
        require(not current.is_symlink(), f"symlink path component: {value}")
    return path


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(root, *arguments):
    # Synthetic indexes must never inherit a caller's repository selector,
    # index, replacement refs, config injection, hooks, or content filters.
    # These Git invocations are local only; proxy and CA environment stays intact.
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(GIT_NO_REPLACE_OBJECTS="1", GIT_CONFIG_NOSYSTEM="1",
                       GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                       GIT_ATTR_NOSYSTEM="1")
    result = subprocess.run(["git", "-c", "core.autocrlf=false",
                             "-c", "core.attributesFile=" + os.devnull,
                             "-c", "core.hooksPath=" + os.devnull, *arguments], cwd=root, check=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env=environment)
    return result.stdout


def load_contract():
    contract = json.loads((ROOT / "os/integration-base.json").read_text())
    require(contract.get("schema_version") == 1, "unknown integration contract")
    require(COMMIT.fullmatch(contract.get("manifest_commit", "")), "manifest pin missing")
    require(SHA256.fullmatch(contract.get("manifest_sha256", "")), "manifest content pin missing")
    seen = set()
    outputs = set()
    for project in contract["projects"]:
        name = str(relative(project["project"]))
        require(name not in seen, "duplicate project")
        seen.add(name)
        require(COMMIT.fullmatch(project.get("commit", "")), "project commit missing")
        require(re.fullmatch(r"GrapheneOS/[a-zA-Z0-9_.-]+", project["repository"]),
                "unexpected upstream repository")
        output = str(relative(project["output"]))
        require(output.startswith("os/patches/") and output.endswith(".patch"), "invalid patch output")
        require(output not in outputs, "duplicate patch output")
        outputs.add(output)
        base_names = set()
        for base in project["base_files"]:
            name = str(relative(base["path"]))
            require(name not in base_names, "duplicate base file")
            base_names.add(name)
            require(SHA256.fullmatch(base.get("sha256", "")), "base content pin missing")
    require(seen, "empty integration contract")
    return contract


def base_file(cache, project, base, fetch):
    path = within(within(cache, project["project"]), base["path"])
    if not path.exists():
        require(fetch, f"missing base file: {path}; use --fetch once to populate the cache")
        url = (f"https://raw.githubusercontent.com/{project['repository']}/"
               f"{project['commit']}/{base['path']}")
        # urllib preserves the inherited HTTPS proxy and normal CA verification.
        with urllib.request.urlopen(url, timeout=45) as response:
            data = response.read(2 * 1024 * 1024 + 1)
        require(len(data) <= 2 * 1024 * 1024, "upstream source file exceeds size limit")
        require(hashlib.sha256(data).hexdigest() == base["sha256"], "downloaded source differs from pin")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    require(path.is_file() and not path.is_symlink(), "base must be a regular file")
    require(sha256(path) == base["sha256"], f"upstream file differs from pin: {base['path']}")
    return path


def verify_manifest(contract, cache, fetch):
    project = {"project": "_manifest", "repository": "GrapheneOS/platform_manifest",
               "commit": contract["manifest_commit"]}
    path = base_file(cache, project, {"path": "default.xml", "sha256": contract["manifest_sha256"]}, fetch)
    manifest = ET.parse(path).getroot()
    require(manifest.tag == "manifest" and not manifest.findall("include"), "unsupported integration manifest")
    projects = {node.get("path", node.get("name")): node for node in manifest.findall("project")}
    for target in contract["projects"]:
        entry = projects.get(target["project"])
        require(entry is not None and entry.get("revision") == target["commit"],
                f"integration target differs from manifest pin: {target['project']}")
        require(entry.get("name") == target["repository"].split("/", 1)[1]
                and entry.get("remote") == "grapheneos", "unexpected integration repository mapping")


def add_tree(source, destination):
    require(source.is_dir() and not source.is_symlink(), f"source tree missing: {source}")
    count = 0

    def unreadable(error):
        raise error

    for current, directories, files in os.walk(source, onerror=unreadable, followlinks=False):
        directories.sort()
        for name in directories:
            require(not (Path(current) / name).is_symlink(), "symlink directory in component sources")
        for name in sorted(files):
            entry = Path(current) / name
            require(not entry.is_symlink(), f"symlink in component sources: {entry}")
            require(entry.is_file(), "component source is not a regular file")
            target = within(destination, entry.relative_to(source).as_posix())
            require(not target.exists(), f"component would replace another source: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(entry, target)
            target.chmod(0o644)
            count += 1
    require(count, f"empty component source tree: {source}")


def assemble(project, cache, fetch, product):
    with tempfile.TemporaryDirectory(prefix="aifirst-os-patch-") as directory:
        tree = Path(directory)
        git(tree, "init", "-q")
        for base in project["base_files"]:
            target = within(tree, base["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(base_file(cache, project, base, fetch), target)
            target.chmod(0o644)
        git(tree, "add", "--", ".")
        original = git(tree, "write-tree").decode().strip()
        for patch in project["hooks"]:
            path = within(ROOT, patch)
            require(path.is_file(), f"hook patch missing: {patch}")
            git(tree, "apply", "--check", "--index", str(path))
            git(tree, "apply", "--index", str(path))
        for addition in project.get("source_trees", []):
            source = product if addition["source"] == "@product" else within(ROOT, addition["source"])
            add_tree(source, within(tree, addition["destination"]))
        git(tree, "add", "--", ".")
        patch = git(tree, "diff", "--cached", "--binary", "--no-ext-diff", original, "--")
        require(patch, "empty integration patch")
        # The resulting full patch, including new source files, must reverse cleanly.
        output = tree / ".git/generated.patch"
        output.write_bytes(patch)
        git(tree, "apply", "--check", "--reverse", "--index", str(output))
        return patch


def check_development_pin(contract, series_bytes):
    """Do not let regenerated source patches silently drift from the dev profile."""
    lock = json.loads(within(ROOT, "os/development-lock.json").read_text())
    require(lock.get("status") == "development-pinned", "development profile is not pinned")
    require(lock.get("tag") == contract["upstream_tag"]
            and lock.get("manifest_commit") == contract["manifest_commit"],
            "development profile selects another upstream base")
    require(lock.get("patch_series_sha256") == hashlib.sha256(series_bytes).hexdigest(),
            "development patch-series pin is stale; review before updating the lock")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-cache", type=Path, required=True)
    parser.add_argument("--fetch", action="store_true", help="fetch only missing, hash-pinned upstream files")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="fail if checked-in patches differ from current sources")
    mode.add_argument("--write", action="store_true", help="write reviewable patch files and their series; never approve a release")
    args = parser.parse_args()
    try:
        contract = load_contract()
        verify_manifest(contract, args.base_cache, args.fetch)
        prepared = {}
        with tempfile.TemporaryDirectory(prefix="aifirst-os-product-") as directory:
            product = Path(directory) / "product"
            subprocess.run([sys.executable, str(ROOT / "scripts/prepare-os-product.py"),
                            "--output", str(product)], check=True)
            for project in contract["projects"]:
                prepared[project["output"]] = assemble(project, args.base_cache, args.fetch, product)
        series = {"schema_version": 1, "patches": [
            {"project": project["project"], "file": project["output"],
             "sha256": hashlib.sha256(prepared[project["output"]]).hexdigest(),
             "kind": project["kind"]}
            for project in contract["projects"]]}
        prepared["os/patch-series.json"] = (json.dumps(series, indent=2) + "\n").encode()
        if args.check:
            check_development_pin(contract, prepared["os/patch-series.json"])
        for name, content in prepared.items():
            path = within(ROOT, name)
            if args.check:
                require(path.is_file() and path.read_bytes() == content,
                        f"stale integration output: {name}; review regenerated patches with --write")
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        print(json.dumps({"status": "integration-patches-checked" if args.check else "integration-patches-written",
                          "projects": len(contract["projects"]), "full_os_compiled": False,
                          "release_lock_changed": False}))
    except (ValueError, KeyError, OSError, TypeError, ET.ParseError, subprocess.CalledProcessError) as error:
        print(f"BLOCKED: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr.decode(errors="replace"), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
