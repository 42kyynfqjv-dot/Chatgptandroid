#!/usr/bin/env python3
"""Emit the reviewed source subtree for vendor/adevtool/config/mk/aifirst.

No APK downloads, signing, network, OS checkout mutation, or device operations.
The integration assembler turns these deterministic files into a pinned-source patch.
"""

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGE = "dev.aifirst.launcher"
VERSION_CODE = 2
VERSION_NAME = "0.2.0"
ANDROID = "{http://schemas.android.com/apk/res/android}"


def ensure(condition, message):
    if not condition:
        raise ValueError(message)


def source_path(root, path):
    """Reject links in the file or any source directory before opening input."""
    ensure(path.is_relative_to(root), f"input escapes repository: {path}")
    cursor = root
    for part in path.relative_to(root).parts:
        cursor = cursor / part
        ensure(not cursor.is_symlink(), f"symlink input is not permitted: {cursor}")
    ensure(path.resolve().is_relative_to(root), f"input resolves outside repository: {path}")
    return path


def inputs(root):
    """Use one Java/resource source of truth; reject source links/special files."""
    product = root / "os/product"
    app = root / "android/app/src/main"
    selected = {"Android.bp": product / "Android.bp", "aifirst.mk": product / "aifirst.mk",
                "LICENSE": root / "LICENSE"}
    for source, prefix in ((app, "app/src/main"), (product / "overlay", "overlay")):
        source_path(root, source)
        ensure(source.is_dir(), f"missing source directory: {source}")
        def enumeration_failed(error):
            raise error
        for current, dirs, files in os.walk(source, followlinks=False, onerror=enumeration_failed):
            for name in sorted(dirs):
                item = source_path(root, pathlib.Path(current) / name)
                ensure(item.is_dir(), f"non-directory input: {item}")
            for name in sorted(files):
                item = source_path(root, pathlib.Path(current) / name)
                ensure(item.is_file(), f"non-regular input: {item}")
                selected[prefix + "/" + item.relative_to(source).as_posix()] = item
    for item in selected.values():
        source_path(root, item)
        ensure(item.is_file(), f"non-regular input: {item}")
    return selected


def render_product(root=ROOT):
    root = pathlib.Path(root).resolve()
    gradle = source_path(root, root / "android/app/build.gradle").read_text()
    ensure(re.search(r"versionCode\s+2\b", gradle) and re.search(r"versionName\s+['\"]0\.2\.0['\"]", gradle),
           "Android version changed; review the Soong module and preparation version together")
    ensure(re.search(r"applicationId\s+['\"]dev\.aifirst\.launcher['\"]", gradle), "unexpected application ID")
    files = {name: path.read_bytes() for name, path in inputs(root).items()}
    manifest_name = "app/src/main/AndroidManifest.xml"
    raw = files[manifest_name].decode("utf-8")
    manifest = ET.fromstring(raw)
    ensure(manifest.tag == "manifest" and manifest.get("package") in (None, PACKAGE), "unexpected Android manifest")
    ensure(not any(node.tag.startswith("uses-permission") for node in manifest), "AI Home permissions changed; review product privilege contract")
    ensure(manifest.get(ANDROID + "sharedUserId") is None, "shared system UID is forbidden")
    ensure(not manifest.findall("uses-sdk"), "SDK versions are owned by Soong")
    ensure("<manifest xmlns:android=" in raw and "package=" not in raw, "manifest format changed; review preparation")
    files[manifest_name] = raw.replace("<manifest xmlns:android=", '<manifest package="' + PACKAGE + '" xmlns:android=', 1).encode()
    module = files["Android.bp"].decode()
    ensure(not re.search(r"\b(?:privileged|platform_apis|defaults|overrides)\s*:", module)
           and not re.search(r'\bcertificate\s*:\s*"platform"', module),
           "privileged application configuration is forbidden")
    return dict(sorted(files.items()))


def prepare(output, root=ROOT):
    output = pathlib.Path(output)
    ensure(not output.is_symlink(), "output cannot be a symlink")
    ensure(not output.exists() or (output.is_dir() and not any(output.iterdir())), "output must be absent or empty")
    files = render_product(root)
    output.mkdir(parents=True, exist_ok=True)
    output.chmod(0o755)
    for relative, data in files.items():
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        destination.chmod(0o644)
    for directory in output.rglob("*"):
        if directory.is_dir():
            directory.chmod(0o755)
    return {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    args = parser.parse_args()
    try:
        hashes = prepare(args.output)
        print(json.dumps({"destination_in_adevtool": "config/mk/aifirst", "package": PACKAGE,
                          "version": VERSION_NAME, "files": hashes}, indent=2, sort_keys=True))
    except (ValueError, OSError, ET.ParseError) as error:
        print("BLOCKED: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
