"""Source-packaging boundaries; these do not claim a Soong build or device boot."""
import hashlib
import importlib.util
import json
import pathlib
import shutil
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("prepare_os_product", ROOT / "scripts/prepare-os-product.py")
product = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(product)
ANDROID = "{http://schemas.android.com/apk/res/android}"


class ProductPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = pathlib.Path(self.temp.name)

    def test_deterministic_bytes_and_non_executable_modes(self):
        first = product.prepare(self.path / "first")
        second = product.prepare(self.path / "second")
        self.assertEqual(first, second)
        self.assertGreater(len(first), 10)
        for name in first:
            self.assertEqual((self.path / "first" / name).read_bytes(), (self.path / "second" / name).read_bytes())
            self.assertEqual((self.path / "first" / name).stat().st_mode & 0o777, 0o644)

    def test_canonical_java_is_preserved_not_forked(self):
        rendered = product.render_product()
        for source in (ROOT / "android/app/src/main/java").rglob("*.java"):
            relative = "app/src/main/" + source.relative_to(ROOT / "android/app/src/main").as_posix()
            self.assertEqual(rendered[relative], source.read_bytes())

    def test_soong_manifest_package_and_recovery_entrypoints(self):
        manifest = ET.fromstring(product.render_product()["app/src/main/AndroidManifest.xml"])
        self.assertEqual(manifest.get("package"), "dev.aifirst.launcher")
        self.assertIsNone(manifest.get(ANDROID + "sharedUserId"))
        self.assertEqual(manifest.findall("uses-permission"), [])
        application = manifest.find("application")
        self.assertEqual(application.get(ANDROID + "allowBackup"), "false")
        self.assertEqual(application.get(ANDROID + "usesCleartextTraffic"), "false")
        activities = application.findall("activity")
        categories = {category.get(ANDROID + "name") for activity in activities for category in activity.findall("intent-filter/category")}
        self.assertIn("android.intent.category.HOME", categories)
        self.assertIn("android.intent.category.LAUNCHER", categories)
        self.assertTrue(all(int(intent.get(ANDROID + "priority", "0")) == 0 for activity in activities for intent in activity.findall("intent-filter")))

    def test_apk_default_opt_in_but_os_default_enabled(self):
        files = product.render_product()
        regular = ET.fromstring(files["app/src/main/res/values/bools.xml"])
        override = ET.fromstring(files["overlay/vendor/adevtool/config/mk/aifirst/app/src/main/res/values/bools.xml"])
        self.assertEqual(regular.find("bool[@name='chatgpt_on_home_default']").text, "false")
        self.assertEqual(override.find("bool[@name='chatgpt_on_home_default']").text, "true")

    def test_product_uses_source_module_without_overriding_stock_modules(self):
        files = product.render_product()
        module = files["Android.bp"].decode()
        make = files["aifirst.mk"].decode()
        self.assertIn("android_app {", module)
        self.assertNotIn("android_app_import", module)
        self.assertNotIn("overrides:", module)
        self.assertNotIn("privileged:", module)
        self.assertNotIn('certificate: "platform"', module)
        self.assertIn("PRODUCT_PACKAGES += AIHome", make)
        self.assertNotIn("PRODUCT_PACKAGES -=", make)

    def test_existing_output_refused_without_modification(self):
        (self.path / "keep").write_text("user file")
        with self.assertRaisesRegex(ValueError, "absent or empty"):
            product.prepare(self.path)
        self.assertEqual((self.path / "keep").read_text(), "user file")

    def test_symlink_output_refused(self):
        (self.path / "target").mkdir()
        (self.path / "link").symlink_to(self.path / "target")
        with self.assertRaisesRegex(ValueError, "symlink"):
            product.prepare(self.path / "link")

    def fixture_root(self):
        clone = self.path / "fixture"
        shutil.copytree(ROOT / "os/product", clone / "os/product")
        shutil.copytree(ROOT / "android/app/src/main", clone / "android/app/src/main")
        shutil.copyfile(ROOT / "android/app/build.gradle", clone / "android/app/build.gradle")
        shutil.copyfile(ROOT / "LICENSE", clone / "LICENSE")
        return clone

    def test_input_symlink_refused(self):
        clone = self.fixture_root()
        source = clone / "android/app/src/main/java/Unexpected.java"
        source.symlink_to(self.path / "outside")
        with self.assertRaisesRegex(ValueError, "symlink"):
            product.render_product(clone)

    def test_direct_module_symlink_refused(self):
        clone = self.fixture_root()
        module = clone / "os/product/Android.bp"
        outside = self.path / "outside.bp"
        outside.write_bytes(module.read_bytes())
        module.unlink()
        module.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink"):
            product.render_product(clone)

    def test_source_ancestor_symlink_refused(self):
        clone = self.fixture_root()
        source = clone / "android/app/src"
        outside = self.path / "outside-source"
        source.rename(outside)
        source.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            product.render_product(clone)

    def test_unreadable_source_subdirectory_does_not_silently_omit_files(self):
        clone = self.fixture_root()
        original = product.os.scandir
        blocked = clone / "android/app/src/main/java"
        def unreadable(path):
            if pathlib.Path(path) == blocked:
                raise PermissionError("synthetic unreadable source directory")
            return original(path)
        with patch.object(product.os, "scandir", side_effect=unreadable):
            with self.assertRaisesRegex(PermissionError, "unreadable source"):
                product.render_product(clone)

    def test_version_change_needs_review(self):
        clone = self.fixture_root()
        gradle = clone / "android/app/build.gradle"
        gradle.write_text(gradle.read_text().replace("versionCode 2", "versionCode 3"))
        with self.assertRaisesRegex(ValueError, "version changed"):
            product.render_product(clone)

    def test_permission_expansion_needs_review(self):
        clone = self.fixture_root()
        manifest = clone / "android/app/src/main/AndroidManifest.xml"
        manifest.write_text(manifest.read_text().replace("    <queries>", '    <uses-permission android:name="android.permission.INTERNET" />\n    <queries>'))
        with self.assertRaisesRegex(ValueError, "permissions changed"):
            product.render_product(clone)

    def test_sdk_permission_expansion_needs_review(self):
        clone = self.fixture_root()
        manifest = clone / "android/app/src/main/AndroidManifest.xml"
        manifest.write_text(manifest.read_text().replace("    <queries>", '    <uses-permission-sdk-23 android:name="android.permission.CAMERA" />\n    <queries>'))
        with self.assertRaisesRegex(ValueError, "permissions changed"):
            product.render_product(clone)

    def test_privilege_configuration_with_spacing_refused(self):
        clone = self.fixture_root()
        path = clone / "os/product/Android.bp"
        original = path.read_text()
        for field in ('privileged : true,', 'platform_apis : true,', 'certificate : "platform",', 'defaults : ["UnreviewedDefaults"],'):
            with self.subTest(field=field):
                path.write_text(original.replace('    name: "AIHome",', '    name: "AIHome",\n    ' + field))
                with self.assertRaisesRegex(ValueError, "privileged"):
                    product.render_product(clone)

    def test_canonical_patch_contracts_match_files(self):
        contract = json.loads((ROOT / "os/product/upstream-contract.json").read_text())
        self.assertEqual(len(contract["patches"]), 3)
        for entry in contract["patches"]:
            self.assertEqual(hashlib.sha256((ROOT / entry["patch"]).read_bytes()).hexdigest(), entry["patch_sha256"])
            self.assertIn(entry["commit"], entry["raw_url"])
            self.assertEqual(len(entry["base_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
