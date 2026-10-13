# OS foundation decision

Research date: 2026-10-11. Recommendation: build a distinctly branded, minimally modified **GrapheneOS derivative for Pixel 9a (`tegu`)**, preserving the upstream device, kernel, firmware, verified-boot and SELinux architecture. This is a source-based replacement OS project. The independently buildable Android app is its initial development harness; installing that app does not replace Android.

This repository now contains concrete framework/gesture/product integration for the full-OS target, but **not** a synchronized OS source tree, compiled OS image, release keys, or complete verified production lock. No custom OS has booted or been tested on a phone. A separate explicit development profile permits reviewed source preparation and `userdebug` builds without production keys/live update service; production operations remain blocked until all release inputs are reviewed. See [OS integration](os-integration.md).

## Alternatives evaluated

| Foundation | Pixel 9a evidence | Maintenance and security | Decision |
| --- | --- | --- | --- |
| Direct AOSP | Google lists `tegu` vendor binaries and a Pixel kernel branch. This proves available components, not that a current complete, secure custom `tegu` image builds automatically. | We must assemble/test the device tree, platform, kernel modules, HALs, vendor image, firmware, signing, updater and recovery. Current AOSP documentation says public source releases occur in Q2/Q4 from 2026; the moving latest-release branch is not a sufficient monthly security-update plan. | Too much device/update ownership for the first release. Retain AOSP as the architectural base and primary security reference. |
| GrapheneOS | Official FAQ/build documentation lists Pixel 9a `tegu` as a production-supported target. The release page fetched on the research date displayed stable `2026100600` for Pixel 9a. | Device-specific integration, kernel hardening, vendor extraction with `adevtool`, release signing, A/B OTA generation and update client already documented. Its published releases include platform and device-support fixes, but our derivative must rebuild and validate every update itself. | Recommended, conditional on our own ability to maintain keys, updates and physical release testing. Upstream does not support or endorse our derivative. |
| LineageOS | Official `tegu` device page identifies maintainer `mikeioannina` and offers install/build/update instructions; the fetched page displayed version 24.0 (Android 17). | Maintained alternative with customization/build infrastructure. Its install guide sends relocking questions to its FAQ and warns about device-integrity compatibility. We did not establish a supported locked-bootloader/custom-AVB-key release path for this target from reviewed documentation. | Viable research alternative, but GrapheneOS gives stronger documented alignment with this project's locked verified-boot requirement. Do not extrapolate security guarantees from another device. |

The observed release number was subsequently checked with a small Git checkout: `git verify-tag 2026100600` succeeded against the public signer from GrapheneOS's official website source, and the manifest points to commit `26f7e8a760d4343a501faf09773ec4cc61a6b56b` with 1,057 explicitly commit-pinned projects. The pinned `adevtool` commit and its signed tag were also checked; its `tegu` configuration selects Google build `CP3A.261005.005`. Exact identities, checksum expectations and trust limitations are recorded in `os/upstream-observation.json`. The factory archive itself was **not** downloaded or verified, and kernel source provenance/build validation is still pending.

These are **research observations, not a production release approval**. Direct retrieval of the website's `allowed_signers` endpoint returned HTTP 403; the public key came from the official website's GitHub source at a recorded commit. Initial independent maintainer review of that trust root is still required. Refresh the device's release page and verify the exact signed manifest before a real import. Never automatically select “latest”, a development branch, or a tag intended for a different device. `os/upstream-lock.json` remains deliberately blocked until our own endpoint/keys, full component identities and review are present.

## Keep the downstream changes small

1. A separate HOME activity provides ChatGPT launch, allowlisted actions, local settings and recovery UI. Keep the official ChatGPT app installed through its supported distribution, separately updated and unmodified.
2. MCP/device-tool services remain deferred. The current framework addition is a narrow `DisplayPolicy` pointer observer for one-finger triangle-to-dialer and square-to-default-Messages gestures, with no edge hold. It defaults off via `aifirst_shape_gestures_enabled`. It does not place calls, send messages or read ChatGPT data.
3. Add build packaging, default HOME selection and branding using product configuration/overlays first. Use small reviewed patches only when the selected tag cannot express a requirement through those mechanisms.
4. Preserve the full normal Android Settings app and system controls, lock screen, notification shade, Clock and fallback launcher. Expose **App updates** and the official ChatGPT Play listing; keep Play updates independent from OS OTAs. The small framework/PermissionController patches implement the concrete initial-HOME and shape-observation requirements. The observer leaves touches delivered to ChatGPT, which may scroll/select before the handoff; this tradeoff has not been physically validated. Offline operation retains native controls.
5. Keep distribution identity, our Updater endpoint and trusted keys in the **critical** patch set. Mark optional UI/bridge features as **customization** patches so urgent updates can omit them.

`os/patch-series.json` now contains three `customization` patches for `frameworks/base`, `packages/modules/Permission` and `vendor/adevtool`. The assembler binds changed base files and manifest to SHA-256/project revisions from `2026100600`; checking those small snapshots is not full-project compilation. The product preinstalls source-built Soong `AIHome`, supplies an initial HOME-role holder only when none exists, and defaults ChatGPT-on-Home to true through a product resource. Existing choices, Launcher3 and stock Settings remain. Production identity/updater critical patches still require completion; the current customization series alone is not a safe emergency release identity.

## Official ChatGPT compatibility

An AOSP-compatible Android runtime and ordinary Android intents are necessary, but do not prove that the official app, account sign-in, Play distribution, subscription recognition, audio routing, notifications or Voice work on our signed derivative. GrapheneOS supports installing sandboxed Google Play as ordinary apps; place it in the same profile as ChatGPT, use the supported official app installation path on the development Pixel and test the user's account there. Play remains available for app installation and updates without becoming the primary interface. Never bundle a modified APK, extract account tokens, mirror conversations, or imply that an API subscription is the existing ChatGPT subscription.

Account features remain implemented by OpenAI's official app/service. Verify ordinary sign-in, text, Voice, background/lock behavior and app updates on the candidate. Tool integration is deferred and does not block OS source work. No physical/account test has been completed in this session.

## Licenses, vendor binaries and branding

AOSP is not covered by one blanket license: most userspace is Apache-2.0, the kernel is GPLv2, and individual projects contain other licenses. GrapheneOS also combines separately licensed components; the inspected `adevtool` at commit `17df3b79a73e67ad68387b35c7d41c85e1d8103c` uses MIT with copyright/permission-notice retention. Preserve each component's notices, record a bill of materials, and provide corresponding source/offers wherever its license requires them. Review the pinned source licenses rather than applying this repository's license to upstream code or binaries. A complete distribution license audit remains a release prerequisite.

Google's [driver binaries](https://developers.google.com/android/drivers) and [factory images](https://developers.google.com/android/images) pages restrict use and redistribution under their accompanying terms. `adevtool` extraction is a build mechanism, not a redistribution license. Do not upload extracted blobs or images to the public repository. Keep downloads private to the authorized build and review component-specific rights before distributing an OTA/factory image. Firmware may remain Google-signed because the hardware verifies its manufacturer signature; do not attempt to replace or bypass that trust chain.

Use our own distribution name and branding. Describe it as based on GrapheneOS without claiming to be official GrapheneOS or an OpenAI-endorsed operating system. Do not redistribute the proprietary ChatGPT APK without permission. Public source, build instructions and checks can be published independently of a binary release.

## Dedicated compilation runner

The measured cloud workspace has only 4 quota CPUs, 16 GiB RAM and about 29 GiB disk capacity; it cannot sync/build the OS. Upstream GrapheneOS lists at least 32 GiB RAM, about 136 GiB for a normal source checkout and another 100 GiB for an OS build. Current AOSP requirements list at least 64 GB RAM and 400 GB free disk. Both leave additional capacity desirable for kernel/browser builds and retained release artifacts.

The runner specification is **x86-64, 32 vCPU, 128 GiB RAM, 1 TiB local NVMe Ubuntu 24.04 LTS**, with at least 600 GiB initially free on `/srv/android`. Build wrappers verify capacity and exact prepared source before executing checkout code; production uses 16 jobs and stops below 64 GiB effective RAM or 400 GiB free space. Generated-input provenance inventory support is now implemented, but real factory/dependency artifact verification, vendor generation and independent inventory review remain undone; see [security-updates.md](security-updates.md). The development wrapper targets `userdebug` only and does not require production keys/update hosting. **KVM is not required** for compilation. The dev Pixel supplies later approved hardware testing.

Install the listed apt packages plus Node.js 24 LTS/Yarn using verified distribution artifacts. Record exact package versions, repository snapshots, image digest, tool versions and the current upstream dependency guide in the runner's build manifest. The runner image digest is deliberately unset until that image exists. Keep the existing egress proxy/CA policy; do not work around blocked download domains. Use a non-root build account, case-sensitive storage and upstream build sandboxing. Signing runs on a separate offline host; release secrets never enter PR CI or this compilation host.

For transfer, copy/clone this repository and its reviewed source commit, recreate the documented Python/Android development environment, and rerun local tests before any OS download. Transfer no account sessions, private signing keys or pairing credentials. Then establish the reviewed upstream lock and follow the source-import commands in [security-updates.md](security-updates.md). This is a configuration for an existing or separately approved server; nothing has been provisioned or billed.

## Primary references

- [GrapheneOS build, vendor extraction, signing and update server](https://grapheneos.org/build)
- [GrapheneOS supported devices](https://grapheneos.org/faq#supported-devices)
- [GrapheneOS release channel and changelog](https://grapheneos.org/releases)
- [GrapheneOS sandboxed Google Play](https://grapheneos.org/usage#sandboxed-google-play)
- [GrapheneOS branding guidance](https://grapheneos.org/faq#trademark)
- [LineageOS Pixel 9a device page](https://wiki.lineageos.org/devices/tegu/), [installation](https://wiki.lineageos.org/devices/tegu/install/)
- [AOSP build requirements](https://source.android.com/docs/setup/start/requirements), [building](https://source.android.com/docs/setup/build/building)
- [AOSP Pixel kernels](https://source.android.com/docs/setup/build/building-pixel-kernels), [licenses](https://source.android.com/docs/setup/about/licenses)

Primary documentation was read through Exa Search/fetch; the limited Git checks above were executed through the permitted network proxy. These establish documented support and source evidence; they do not replace complete source authentication/import, a full build, license review or tests on our hardware.
