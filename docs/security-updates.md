# Security maintenance and our OTA pipeline

Our signed derivative requires **our own rebuilt and signed updates**. Google's and GrapheneOS's unchanged OTA packages target their signing identities, partitions and release metadata. They are not our update stream. We import upstream source/device changes, retain our signing identity and update endpoint, build the matching complete release, validate it, then sign/publish our artifacts. We cannot promise ongoing security merely because the upstream project ships fixes.

## Implemented boundary and remaining work

`scripts/os-pipeline.py` implements immutable-input validation, authenticated source-import commands, full-commit manifest checks, patch digest/conflict checks, exact prepared-source verification, and a release-evidence consistency gate. It uses Python's standard library. Local unit tests cover rejection of floating revisions, unhandled manifests, patch targets absent from the signed manifest, staged/unstaged source mutations, Git-ignored extras, modified manifest copy/link outputs, wrong normal/emergency patch selection, path traversal, stale/wrong-release reports, tampered artifacts, missing hardware evidence, unsigned configuration and decreasing build numbers.

The committed production lock is `blocked-unverified`; the tooling refuses production operations with it. Small research checkouts of the upstream manifest and `adevtool` were obtained, their `2026100600` Git tag signatures verified against the public signer from the official website GitHub source, and all 1,057 manifest project revisions checked as explicit commits. This evidence and its initial key-trust limitation are recorded in `os/upstream-observation.json`. No complete OS source sync, vendor archive download, compiled OS, signed OTA, update host, custom AVB key or physical validation was produced here. The empty patch series is an initial container for future product integration. The gate is not an attestation authority: a fabricated human report could still pass its structural checks. Protected release review, independently verified signatures and a signer controlled by maintainers must remain the publication authority.

## Track and import

Assign a primary maintainer and a backup before using this OS on the main phone. Review the [GrapheneOS release feed](https://grapheneos.org/releases.atom), release notes and Pixel/Android security bulletins daily and on urgent advisories. Automation may propose a lock update and summarize upstream commits; a maintainer reviews device applicability and signs off. This repository does not create an unattended schedule or promise a support SLA. Set an operational target such as triaging exploited/critical fixes within 24 hours, but measure and report actual lag.

For each release candidate:

1. Select the stable **tegu** tag from the official release page. Check the signed tag using GrapheneOS's published `allowed_signers`, whose contents/fingerprint must first be authenticated through an independent trusted review. Record exact tag, manifest commit and signer-file SHA-256 in the lock. Never treat a just-downloaded key plus a signature as independent trust establishment.
2. Review the tag's `adevtool` device definitions and release notes. Record the required Google factory build ID, original download URL and archive SHA-256. Pin the matching kernel source commit and SHA-256 of a deterministically archived kernel-prebuilt set from that release. Do not independently choose the newest bootloader, radio, vendor image, kernel or platform branch. Preserve the coherent upstream set including kernel modules/HAL compatibility. If upstream cannot provide an applicable fix, document it and keep the advertised patch level honest.
3. Record platform security patch level only after checking applicable Android and Pixel bulletin fixes, firmware/HAL coverage and upstream deviations. Preserve upstream vendor/boot patch levels; a newer text property does not supply a missing fix. Patch-coverage evidence must explain omissions, backports and CVE applicability.
4. Set our real HTTPS updater base URL and public OTA/AVB/platform-key fingerprints. Private keys stay offline. The server owner and signer pin are reviewed inputs, not automatically generated defaults. Record patch series SHA-256 and a review reference, then mark the lock `verified` only after completing these checks.
5. On the prepared compilation server, use a **new empty checkout**. `repo` must come from a verified runner image/distribution and retain its own update-signature checks:

   ```sh
   python3 scripts/os-pipeline.py validate-lock
   python3 scripts/os-pipeline.py import \
     --signers /srv/trust/grapheneos_allowed_signers \
     --destination /srv/android/tegu-candidate
   ```

The importer checks the signer-file hash, initializes the exact tag with superproject selection disabled, verifies its SSH signature, checks tag/HEAD against the reviewed commit, rejects local manifests and floating project revisions, syncs, checks every project HEAD/cleanliness and emits a resolved manifest hash. The exported manifest is a sibling file named `CHECKOUT-verified-manifest.xml`, outside the source tree. It refuses unfamiliar manifest directives so a changed upstream layout requires a code review. An import failure leaves a diagnostic checkout; do not ignore it or force-sync around it. Investigate and start a new checkout. No key auto-download or unverified branch fallback is performed.

## Apply changes and build

Each `os/patch-series.json` entry has this form (values shown here are placeholders, never production pins):

```json
{"project":"packages/apps/Updater","file":"os/patches/0001-own-updater.patch","sha256":"REVIEWED_SHA256","kind":"critical"}
```

Hash the series file itself into the upstream lock. It covers ordered patch hashes and their classification. Put branding, updater endpoint, own trust configuration and recovery-compatible fallback packaging in `critical`; optional assistant UI/features go in `customization`. Add a separately built APK using a reviewed product module/inclusion patch; do not insert an untracked local manifest. No AOSP packaging patch is present yet.

```sh
python3 scripts/os-pipeline.py patches --source /srv/android/tegu-candidate
python3 scripts/os-pipeline.py patches --source /srv/android/tegu-candidate --apply
```

Before applying, the tool rechecks pinned project HEADs and cleanliness, requires each patch target to be a project in the signed manifest, verifies every patch hash and runs `git apply --check --index` for every target project. It refuses conflicts instead of silently rebasing or fuzzing them. Application is staged in Git. If an unexpected application failure occurs after prechecks, discard that candidate after preserving diagnostics and recreate it; this is not a cross-project transactional operation. Archive the final diff and compare it with the reviewed series.

Verify the exact prepared source with:

```sh
python3 scripts/os-pipeline.py verify-tree --source /srv/android/tegu-candidate
```

This reconstructs the expected tree from every pinned Git commit plus its selected reviewed patches using temporary indexes, compares the actual index trees, then hashes all working-file bytes and executable/symlink modes directly against Git objects. It does not trust `.gitignore`, Git stat caches, or `assume-unchanged` flags. It also authenticates manifest `copyfile` and `linkfile` destinations, including the top-level `build/envsetup.sh` entrypoint, and rejects undeclared files/directories. If a patch changes a `copyfile` source, refresh its declared copy before verifying. Emergency verification uses `--emergency` and rejects an accidentally retained customization patch. Git/Repo administrative metadata is excluded from content scanning; their tool bootstrap and host environment remain separate trusted-runner inputs. Run verification/build in an isolated workspace with no concurrent writers.

**Generated-input inventory support is still pending.** The current verifier intentionally rejects generated/vendor files and dependency directories that are not authenticated tracked source. There is no blanket exclusion for `vendor`, `node_modules`, ignored files, or pre-existing output directories. Therefore an actual OS build remains blocked after vendor generation even after filling the release lock and moving to a larger runner. Before enabling that stage, implement and review a content/mode inventory for generated inputs, pin it to independently verified factory/dependency inputs and the lock, and test mutation rejection. Do not bypass the verifier to compile. The following vendor/build sequence describes the remaining integration work, not a currently completed end-to-end build path.

In that checkout, install the **pinned tag's** adevtool dependencies and execute `adevtool generate-all -d tegu` as described by upstream. Record fetched archive checksums and extracted component identities; compare them to the lock and save logs. Inspect and build/reproduce kernel prebuilts where needed, retaining the upstream toolchain/source linkage. Chromium/WebView and separately built apps also have their own pinned source/build/signing chains; retain their provenance and updates. Do not treat a platform compile as proof that a prebuilt browser/kernel is current.

Once generated-input provenance support is implemented and reviewed, use `scripts/os-build.sh /srv/android/tegu-candidate` with reviewed `BUILD_NUMBER` and `BUILD_DATETIME`. The wrapper invokes `verify-tree` **before sourcing or executing any checkout build script**, requires a fresh output directory, checks resources and our Updater URL, then selects `tegu-cur-user`, includes Updater with `OFFICIAL_BUILD=true`, builds `target-files-package otatools-package`, and runs upstream `script/finalize.sh`. Pass `--emergency` as its second argument for the critical-only patch selection. Confirm targets/dependencies against the pinned release before execution. Set a strictly increasing distribution build number independently from upstream; an emergency rebuild must still exceed every published build. Preserve source manifest, downstream diff, build environment manifest, dependency hashes, all logs, notices/SBOM and unsigned target-files. The wrapper does not prove hardware support, sign, publish or touch a device.

The upstream guide explicitly warns that leaving its official update endpoint in a differently signed build causes repeated failed update downloads. Our build wrapper blocks that endpoint. Additional upstream services/app repositories have separate identities; inventory them and preserve permitted compatible updates or replace them intentionally, instead of broadly rewriting every GrapheneOS URL.

## Signing keys and artifact verification

Generate unique release/AVB/platform and component keys for this distribution/device using the pinned upstream guide on a separate offline signer. Preserve component-specific signing requirements, including APEX, privileged permissions and WebView/APK signer compatibility. The initial key ceremony needs named maintainers, recorded public fingerprints and a tested recovery process before any phone installation.

Use strong encrypted private-key storage, a temporary RAM-backed signing workspace, disabled swap on the signer, least access and encrypted offline backups in at least two controlled locations. Test restoring the backups on an isolated host and compare public fingerprints. Keep production keys and passphrases out of Git, CI, build logs, the relay, containers and cloud build runner. Development keys are a separate identity and never qualify for a production release. Loss of the established signing identity can force reinstall/data loss; routine key rotation is not a transparent OTA operation and requires a separately validated migration plan.

On the signer, independently hash/review input artifacts and use the pinned release's `script/generate-release.sh tegu BUILD_NUMBER`. This generates our signed target-files, full update package, factory archive/signature and channel metadata. `generate-delta.sh` requires the retained **signed** source and destination target-files. Always retain a full OTA fallback; an incremental must target the exact installed source build.

Independently verify the OTA whole-file/payload signatures against our OTA certificate, AVB chain and expected public key, rollback index metadata, partition/device assertions, production `user` properties, APK/APEX certificates and absence of public test keys. Confirm no verity/verification-disable flags, no permissive SELinux domains and no weakened encryption. A package being a ZIP or having a SHA-256 is not signature verification. Save tool versions and verification logs as evidence; inspect AVB rollback indices as well as the user-visible build number.

## Physical acceptance and evidence format

Use the separately available development Pixel, protecting the main phone. Availability of that device does not authorize installing or flashing it. Obtain explicit approval for each initial unlock/install or other unapproved phone modification, identify possible data wipe and record a recovery path first. Carrier bootloader unlock eligibility is a prerequisite. Initial OS installation/relocking is not run by any repository script.

Every production candidate must be tested on the exact supported hardware with its intended locked bootloader/custom AVB key. Test boot and lock-screen security; encryption across reboot; SELinux enforcement; emergency/system UI escape paths; Wi-Fi/cellular/Bluetooth, audio/microphone, camera and suspend; official ChatGPT sign-in/text/Voice as separate outcomes; allowlisted app/Clock handoffs; duplicate/offline/expired/revoked bridge requests; OTA from the previous shipped release; and the candidate's ability to update to a signed later test build. Test interrupted-download and failed-boot behavior on the development device. Evidence must identify hardware model, build, public signing key and which assertions were measured, without publishing a serial/IMEI or user account data.

Create one evidence bundle directory with `release.json`, artifacts and per-check JSON reports. `release.json` has this structure; nulls/empty checks below intentionally **fail** the gate:

```json
{
  "schema_version": 1, "device": "tegu", "release_id": "our-reviewed-release",
  "mode": "normal", "build_number": 2, "previous_build_number": 1,
  "source_lock_sha256": null, "security_patch": null, "update_url": null,
  "keys": {"ota_cert_sha256": null, "avb_public_key_sha256": null, "platform_cert_sha256": null},
  "artifacts": {
    "ota": {"path": "signed-ota.zip", "sha256": null},
    "factory": {"path": "signed-factory.zip", "sha256": null},
    "signed_target_files": {"path": "signed-target-files.zip", "sha256": null},
    "manifest": {"path": "build-manifest.json", "sha256": null},
    "sbom": {"path": "sbom.json", "sha256": null}
  },
  "checks": {}, "release_review_reference": null
}
```

For every check in the script's `CHECKS` set, `checks[check_name]` must contain a relative report path and its SHA-256. Each report has `check`, `release_id`, `ota_sha256`, Boolean `passed`, `reviewer`, and nonempty `details` with the method, observed properties and log references. The list includes matching platform/kernel/vendor/firmware, physical `tegu`, custom-key locked boot, SELinux, encryption, OTA/AVB signatures, rollback protection, upgrade from previous/to next release, forward recovery, key audit, security coverage, notices and our updater endpoint. Every report is bound to the same exact signed OTA digest. Unknown or unperformed observations are failures, not `passed: true`.

```sh
python3 scripts/os-pipeline.py release-gate /srv/releases/candidate/release.json
```

The gate validates the exact lock/artifact/report hashes, complete required checks, identity continuity, non-future reviewed patch level and increasing build number. It never substitutes for actual signature verification or device tests, and its success message says so. Maintainers independently review the evidence and sign an attestation over the bundle manifest on the offline signer; a future publisher must verify that authorized signature and enforce protected approval. Publication/attestation automation is not implemented here, so the repository cannot silently publish a release based on self-asserted JSON.

## Staged publication and recovery

Host our generated metadata/archives on our HTTPS static update endpoint. Keep signing keys completely separate from hosting credentials. Upload immutable OTA/factory objects first, verify their hashes/signatures through the serving URL, then atomically promote the generated `tegu-testing`, `tegu-beta` or `tegu-stable` metadata. Retain previously shipped artifacts and signed target-files. Limit upload credentials and log/audit promotions. The upstream client's signed OTA verification and rollback protection are the integrity boundary; HTTPS/metadata alone cannot establish package trust, and a compromised host can still withhold updates.

Stage through development-device testing, opt-in beta, then stable only after acceptance. Set defined observation windows and failure thresholds before rollout. With one development device, do not claim statistical confidence or a percentage rollout. A separate canary client cohort is needed before automated population-based percentages become meaningful. Monitor user-reported boot/update failures without collecting private conversations or personal device IDs.

For a regression, pause channel promotion and produce a **higher-version forward fix** retaining the same keys. A/B may automatically return to an intact slot after a failed first boot only where the boot chain and rollback state permit; it is not a guaranteed downgrade mechanism. Never decrease hardware rollback indices, disable verification or publish a “rollback” package as a routine rescue. Recovery sideload of our compatible signed full OTA is a candidate recovery path to validate on the development device. If no accepted compatible OS boots, restoring a currently permitted stock factory image or reinstalling our OS may require unlock/relock and a data wipe; obtain approval and check current vendor anti-rollback requirements first. Backups must be tested before initial device installation.

## Emergency minimal release

If optional assistant changes delay an urgent upstream fix, start from the new authenticated stable upstream and apply only the critical patch set:

```sh
python3 scripts/os-pipeline.py patches --source /srv/android/emergency-candidate --emergency --apply
```

Keep our branding, **existing keys**, own updater endpoint, recovery UI and any package/certificate identity needed for safe upgrade. Omit optional UI/bridge additions; if they persist as installed apps, disable their integration without changing their signing identity or deleting private data unexpectedly. Build an otherwise minimal upstream-based image with a higher build number, matching vendor/firmware and the same production security configuration. An upstream image signed by somebody else is not this fallback.

Emergency mode bypasses **no** signature, hardware, rollback, license or security-coverage gate. Maintain and periodically test the critical-only path in advance. If even that path cannot ship safely, disclose the lag and support a separately approved migration/recovery; do not raise the advertised patch level. Automated source/build/digest checks reduce effort, but source applicability, security review, licensing, key custody, hardware acceptance and release accountability remain ongoing human work.

## References

- [GrapheneOS build/signing/update server](https://grapheneos.org/build)
- [GrapheneOS releases and OTA signature/downgrade description](https://grapheneos.org/releases)
- [Android Verified Boot](https://source.android.com/docs/security/features/verifiedboot/verified-boot)
- [AOSP release signing](https://source.android.com/docs/core/ota/sign_builds)
- [Android Security Bulletins](https://source.android.com/docs/security/bulletin)
- [Pixel security bulletins](https://source.android.com/docs/security/bulletin/pixel)
- [Google factory images and anti-rollback warnings](https://developers.google.com/android/images)
