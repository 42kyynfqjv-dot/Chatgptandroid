# Development and build-server setup

**Immediate scope: APK development and physical tests on the dev Pixel.** The
existing modest cloud server is the component build environment; the local
MacBook handles approved USB transfer/testing. Do not start a full Android
source build or provision a larger runner for this phase. The full-OS runner
section below is a later-stage planning reference.

The server compiles the software. The owner's **dev Pixel** supplies physical
hardware testing after explicit installation/flash approval. KVM and an emulator
are not required for that workflow.

The deployment layout is a **cloud dev server**, a **local MacBook**, and a
**local dev Pixel**. The cloud server produces artifacts; the MacBook downloads
and verifies them, then handles an approved USB installation/test procedure on
the Pixel. MCP and device execution belong **on the Pixel**, with no project
cloud runtime or relay. The existing Python relay is a superseded experiment;
do not deploy it as a prerequisite. See [on-device MCP](on-device-mcp.md).
The cloud server is modest and its actual specs remain to be checked. The large
runner profile below applies only to compiling the complete Android OS.

## Component development

Use Linux x86-64, Python 3.12, JDK 17 or 21, `make`, Git, curl, unzip and ordinary
package-repository access. Approximately 8 GiB RAM and 10 GiB free disk suffice
for these small components; this is not an Android OS build estimate.

From this repository root, create a private environment and install the complete
hashed dependency lock:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r bridge/requirements.lock
make test PYTHON="$PWD/.venv/bin/python"
```

`make test` covers the relay/MCP protocol, release-control failure cases and
Android's platform-independent safety/journal code. It does not install software
on a phone. The MCP integration test needs permission to create **loopback
sockets**. In managed Codex sandboxes, use a network-enabled command grant while
retaining the configured proxy/CA. Do not turn off TLS validation or bypass the
network policy when a destination is denied.

Install only the SDK components needed by this app; the script verifies the
command-line-tools archive SHA-256 and displays applicable SDK licenses:

```sh
export ANDROID_HOME="$PWD/.sdk"
export ANDROID_USER_HOME="$PWD/.android"
export GRADLE_USER_HOME="$PWD/.gradle"
bash scripts/setup-android-sdk.sh
make apk
```

The Android project pins Gradle/Android Gradle Plugin, SDK API 35 and Build Tools
35.0.0. The Gradle distribution has a checked SHA-256; see the Android README for
the exact versions and source provenance. SDK package revisions and host JDK
must also be recorded for release builds. This is a repeatable setup, not a
claim of a hermetic or bit-identical OS/APK build.

Java/Gradle networking does not always honor `HTTPS_PROXY`. The SDK setup script
maps a credential-free HTTP CONNECT proxy URL into sdkmanager arguments. For
Gradle, pass the corresponding `-Dhttps.proxyHost`, `-Dhttps.proxyPort`,
`-Dhttp.proxyHost`, and `-Dhttp.proxyPort` properties on that command. Preserve
the supplied CA trust. Do not commit an authenticated proxy URL or trust store
containing private material. Read the Android build notes for the verified local
command. Keep all tool caches in writable paths in a restricted cloud workspace.

The APK is produced under `android/app/build/outputs/apk/debug/`. A debug APK
is for the dev Pixel harness and is **not** a signed production OS app release.
Build/lint success does not establish on-device behavior. No install command is
run by the setup script, Makefile, or CI.

## Transfer to the dev server

Transfer this source checkout (or its source archive) and public documentation;
exclude `.venv`, SDK/Gradle caches, runtime databases, pairing credentials, debug
keys, and build output. Recreate dependencies using the pinned files. Do not
place relay credentials or OS signing keys in Git. If using GitHub, review the
pending source and secret scan before publishing. Publishing source to GitHub
does not publish a signed OS release or authorize phone installation.

On the destination, run `python3 scripts/environment-report.py` and the component
checks above first. Preserve the report with build provenance. The program
prints capacity/tool paths only, not environment-variable or credential values.

## Full OS build runner

The concrete compilation profile is [os/runner.json](../os/runner.json):
**Ubuntu 24.04 LTS, x86-64, 32 vCPU, 128 GiB RAM, 1 TiB local fast SSD**, with
at least 600 GiB free at the initial checkout/build stage. Build jobs default to
16; source-sync jobs to 8. Neither paid resources nor a server have been
provisioned here. Use an existing suitable server or obtain cost approval before
renting one.

Follow the exact package list and upstream commands in
[security-updates.md](security-updates.md). Source downloads need GitHub,
Android/Chromium source hosts, Google's device-image endpoints and the package
hosts named by the pinned release. Obtain any missing network-policy grants
through the supported environment configuration rather than altering the proxy.

`os/upstream-lock.json` deliberately starts blocked: key identity, our update
endpoint, and the complete vendor/kernel/firmware evidence are not established.

There is another explicit build blocker: generated vendor/dependency inputs need
a reviewed, pinned content inventory and verifier support. The current
`verify-tree` gate authenticates every pinned project plus exact selected patches,
index/worktree bytes, and manifest copy/link outputs, and rejects all undeclared
or Git-ignored additions. It runs before the build wrapper executes checkout
code. Filling the lock and moving to a bigger server alone does not make a full
OS build ready; implement and test generated-input provenance first. See
[security-updates.md](security-updates.md).
`scripts/os-pipeline.py` implements import/patch/evidence checks, and
`scripts/os-build.sh` is the unsigned build entry point. Do not change the lock
to `verified` simply to make a build start. Cryptographic tag verification and
component-version coverage are separate requirements.

The runner builds reviewed code only. Run untrusted pull-request jobs on
ephemeral hosted runners; never give them a persistent OS checkout, release
credentials, signing keys or hardware access. Production signing stays separate
from the compilation host.

## Automation boundaries

`.github/workflows/components.yml` installs hashed Python dependencies, runs
protocol/release-control tests, compiles the Android app, runs lint, and retains
debug APK/lint artifacts. Actions are commit-pinned, workflow permissions are
read-only, and no secrets or phone access are required. The workflow has been
prepared locally; an actual GitHub run is a separate verification event.

Upstream import/patch checks and release-evidence consistency can be automated.
First key trust, licensing decisions, interpreting security bulletin coverage,
physical testing, approval of an irreversible device procedure, signing custody,
and release promotion remain human responsibilities. See the release process for
the exact gates and emergency path.
