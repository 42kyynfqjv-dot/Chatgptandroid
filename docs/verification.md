# Verification record

Initial-build snapshot date: **2026-10-11**, before GitHub publication. Initial repository state: an empty Git checkout;
the earlier local Android/Python scaffold was not present. All implementation
here was created and reviewed in this cloud workspace.

## Demonstrated in this session

| Component | Evidence | Practical limit |
|---|---|---|
| Python dependency setup | Fresh Python 3.12 environment installed from the complete 31-package, SHA-256 hash-locked requirements | Reproducible component dependencies; no guarantee for an unbuilt OS |
| MCP protocol and relay | Official MCP SDK subprocess initialized, listed tools, queued allowed requests, queried status and exercised duplicate recovery through a running local relay | Simulated device endpoint; no ChatGPT account/client involved |
| Relay security/lifecycle | 16 passing tests covering role separation, strict payloads, expiry, durable claims, bounded storage, no-cache, replay, restart, concurrent claims and late-result conflicts | HTTPS behavior tested at application boundary; no public relay deployed |
| Android core | 84 passing assertions against production Java policy/deadline/journal code | No Android Activity, actual Clock, Play Store, or radio/network behavior is established by these tests |
| Android compilation | Debug APK produced with JDK 17, SDK 35, Build Tools 35.0.0, AGP 8.9.2 and Gradle 8.11.1; APK signature verification passed | Development signing key; no device install or production package |
| Android static analysis | `lintDebug` passed with **0 errors and 0 warnings** | Static analysis does not replace accessibility, lifecycle or hardware testing |
| Upstream research checkout | GrapheneOS manifest and adevtool release tag signatures verified; 1,057 manifest projects explicitly pin commits | Signer initially obtained from official website GitHub source; independent maintainer trust review remains |
| OS release controls | **28 passing tests**, including actual Git patch/tree checks and mutation rejection; checked-in production lock rejects release operations | Evidence structure is checked, not the truth of human assertions or a full build |

The MCP fixture reports a simulated `handed_off` result via the authenticated
device API. It does **not** launch an app or create an alarm. The Android code
only records `handed_off` after a successful `startActivity` call, and that path
still needs physical validation. Neither side emits `completed` for an intent.

The final `./gradlew --no-daemon assembleDebug lintDebug` run succeeded with
43 tasks (13 executed, 30 up-to-date). The verified debug APK is copied to
`artifacts/AIHome-debug.apk` (118,550 bytes); SHA-256:
`abafefb3e72770c913debe585440b9306e2b735420a42426f22b1f87407caf6a`.
Its APK v2 signature verifies. The signing identity is a local Android debug
identity, not an OS release key. The APK and logs are ignored by Git.

The component checks passed **44 Python tests** (28 OS controls,
16 relay/MCP) and **84 Java safety assertions**. The local logs are
`artifacts/component-tests.log` and `artifacts/os-tests.log` (the final OS rerun
includes an additional manifest-tampering regression). Source-tree validation runs before executing
checkout build scripts. Generated vendor/dependency inputs remain blocked until
a reviewed inventory is implemented; filling the lock alone cannot make a full
OS build safe or ready.

## Cloud capacity and toolchain

The runner exposes five logical/affinity CPUs but a cgroup quota of **4 cores**;
its effective memory limit is **16 GiB** with roughly **30 GiB** free in the
workspace. No KVM device is exposed. These resources suffice for the independent
components but not a complete OS source checkout/build. KVM is unnecessary for
compilation; future hardware tests use the owner's dev Pixel.

Initial socket operations were blocked by the command sandbox. A supported
network-enabled command grant resolved this while preserving the configured
proxy and TLS validation. This was not a permanent package-network failure.
No proxy bypass or global TLS-disable setting was used.

The supplied Java 21 runtime lacked a `javac` executable. Android builds instead
used official Temurin **17.0.20.1+1**, archive SHA-256
`3808d1d15e3ec6bd5b84057fb5d84c33d8a1536a258146bcea2e603fc726e08e`,
checked against the public release metadata. Android command-line tools 12.0
(archive 11076708) were checked against Google's repository metadata and recorded
SHA-256 `2d2d50857e4eb553af5a6dc3ad507a17adf43d115264b1afc116f95c92e5e258`.
Installed platform 35 reports revision 2 / extension level 13.

## Not demonstrated or performed

- Official ChatGPT Plugin creation, tunnel connection, account entitlement,
  Android typed tool calls, and Android Live/Voice tool calls. Each is a separate
  test in [the validation protocol](account-device-validation.md).
- Physical APK installation, changing the dev Pixel's launcher, Google Play
  setup, ChatGPT sign-in, alarm handoff, or hardware behavior.
- Full OS source sync, vendor factory-archive verification, complete kernel
  provenance, OS build, production signing, OTA generation, locked verified-boot
  installation, rollback/recovery or update testing.
- GitHub-hosted CI execution, public repository push, hosted relay, public
  Plugin publication, scheduled maintenance, or paid infrastructure provisioning.

The code and runner configuration are ready for further development. Production
release remains blocked by the unset reviewed inputs and hardware evidence;
there is no flashable OS image in this checkout. The owner has a dev Pixel and
has offered a dev server for compilation, but has not authorized physical
modifications or supplied a server connection in this session.

The detailed capability matrix, source URLs and documented/conditional/unproven
distinctions are in [chatgpt-feasibility.md](chatgpt-feasibility.md). The OS
recommendation and update responsibilities are in
[os-foundation.md](os-foundation.md) and [security-updates.md](security-updates.md).
