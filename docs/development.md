# Development and build-server setup

**Immediate scope: prepare and compile the complete replacement OS.** The
current workspace can build components and regenerate the framework/product
patches, but its 16 GiB RAM and roughly 29 GiB disk cannot support a full source
sync/build. Follow [OS integration](os-integration.md) for the current work;
the standalone APK is an independently testable component, not the deliverable.

The server compiles the software. The owner's **dev Pixel** supplies physical
hardware testing after explicit installation/flash approval. KVM and an emulator
are not required for that workflow.

The development layout is a **cloud dev server**, a **local MacBook**, and a
**local dev Pixel**. The cloud server produces artifacts; the MacBook downloads
and verifies them, then handles an approved USB installation/test procedure on
the Pixel. AIHome supplies Home/native controls inside the OS; framework sources
add a default-off shape observer. MCP is deferred and no project cloud runtime
is required. The [earlier dev Pixel guide](pixel-quickstart.md) concerns only
the standalone APK. The full-OS runner profile below is now relevant to the
next complete compilation, not a requirement for small component tests.

## OS source integration and development profile

`scripts/prepare-os-integration.py` regenerates three canonical patches from
`os/framework`, `os/gestures` and the source-built `os/product` payload against
the manifest and selected base files pinned in `os/integration-base.json`.
`--base-cache PATH --fetch --check` fetches only those small inputs and fails on
stale output. `--write` prepares reviewable patches; it does not approve a lock.
Neither mode downloads a full tree or compiles an upstream project.

The recognizer suite has 239 synthetic assertions and the framework session
suite has 88; product preparation/resource checks have separate scopes. They do not compile
the complete framework controller, prove Soong assembly or test physical input.
The passive observer leaves touches delivered to ChatGPT, so scrolling or other
partial effects remain possible before a recognized shape opens a native app.

Use the explicit source-only profile for development preparation:

```sh
python3 scripts/os-pipeline.py --development \
  --lock os/development-lock.json validate-lock
```

The same global options select development `import`, `patches`, `verify-tree`
and `capture-generated`. `scripts/os-build-development.sh` is the dedicated
`userdebug`-only entry point; see the integration guide for its full invocation.
It still requires capacity, a complete exact verified checkout and reviewed
generated inputs. Development does not require production signing keys or a
live update URL, excludes the official updater, and cannot authorize
`release-gate`. Production continues to
use `os/upstream-lock.json` and the strict `scripts/os-build.sh` path.

## Component development

For the APK, use Linux x86-64, a full JDK 17, `make`, Git, curl, unzip and ordinary
package-repository access. Approximately 8 GiB RAM and 10 GiB free disk suffice
for these small components; this is not an Android OS build estimate.

Python is only needed for the retained bridge and OS-control checks, not to
build or run the launcher. To run those reference checks, use Python 3.12 and
install the complete hashed dependency lock in a private environment:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r bridge/requirements.lock
make test PYTHON="$PWD/.venv/bin/python"
```

`make test` covers retained relay/MCP checks, OS-control failure cases and
Android's platform-independent component code. The OS integration/gesture test
commands and their exact scopes are listed in the integration guide. No test installs software
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
is for the dev Pixel prototype and is **not** a signed production OS app release.
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

`os/upstream-lock.json` remains production-blocked: release key identity, our
update endpoint and complete vendor/kernel/firmware evidence are not established.
The separate development lock permits source preparation without those
production identities; it is not proof of downloaded vendor bytes, kernel
validation, a completed build or security-patch coverage.

Generated vendor/dependency inventory support is implemented. `verify-tree`
authenticates pinned projects, exact patches, index/worktree bytes and manifest
copy/link outputs, then admits only explicitly inventoried generated content
bound to reviewed source/generator identities and hashed factory/dependency
artifacts. It rejects undeclared or mutated additions, including ignored files.
`capture-generated` records a candidate inventory; it does not approve it.
An independent review reference and exact inventory digest must be pinned in
the selected lock before use. The actual full vendor/dependency generation and
review have not happened here, so that remains a build-input blocker alongside
runner capacity. See [security-updates.md](security-updates.md).
`scripts/os-pipeline.py` implements import/patch/evidence checks, and
`scripts/os-build.sh` is the unsigned build entry point. Do not change the lock
to `verified` simply to make a build start. Cryptographic tag verification and
component-version coverage are separate requirements.

The runner builds reviewed code only. Run untrusted pull-request jobs on
ephemeral hosted runners; never give them a persistent OS checkout, release
credentials, signing keys or hardware access. Production signing stays separate
from the compilation host.

## Automation boundaries

`.github/workflows/components.yml` runs component and OS integration checks,
including gesture/session tests and patch regeneration, compiles the Android
app, runs lint, and retains component/integration artifacts. It does not perform
a full OS build. Actions are commit-pinned, workflow permissions are
read-only, and no secrets or phone access are required. The workflow has been
run successfully on GitHub for an earlier revision. Check the run associated
with the commit being installed, not merely the most recent green result.

Upstream import/patch checks and release-evidence consistency can be automated.
First key trust, licensing decisions, interpreting security bulletin coverage,
physical testing, approval of an irreversible device procedure, signing custody,
and release promotion remain human responsibilities. See the release process for
the exact gates and emergency path.
