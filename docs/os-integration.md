# Pixel 9a OS integration

The deliverable is a replacement Android OS for the dev Pixel 9a (`tegu`).
The current source integrates ChatGPT-first Home selection and direct shape
gestures into a pinned GrapheneOS base. **There is no bootable OS image yet.**
The existing APK remains a component/recovery prototype; installing it does not
add the framework gestures.

## Implemented behavior

- AIHome is built from source into the product and selected as the initial Home
  role holder. Its OS resource default opens official ChatGPT on Home. A later
  user choice of another launcher is preserved.
- A single-finger closed triangle in the focused ChatGPT window opens the
  native dialer. A closed square opens the default Messages app. There is no
  edge hold or activation step for each gesture.
- Recognition is experimental and initially disabled through a development
  setting. It requires the unlocked owner profile, full-screen ChatGPT, a hidden
  keyboard, no overlapping touchable windows, and a stroke inside the screen's
  safe interior. Calls, lock/focus changes and multitouch cancel recognition.
- The observer does not consume or delay app input. **ChatGPT can scroll or react
  while the shape is drawn.** Eliminating that effect requires further input
  arbitration work and a responsiveness tradeoff.
- Phone, Messages, Settings, stock launcher, lockscreen and ordinary navigation
  remain available. These patches do not yet hide all Android system UI or turn
  dialer/messages into embedded panels. Native apps open as activities; their
  Back/task behavior needs Pixel testing.

Official ChatGPT and sandboxed Google Play are installed through the base OS's
supported app path after setup; neither proprietary app is bundled here. ChatGPT
keeps its official Play update channel. A restricted update-only Play interface,
the monochrome recovery-screen redesign and complete onboarding are still work
to do. MCP is deferred; this OS integration has no project cloud runtime.

## Source layout and local checks

| Source | Role |
|---|---|
| `os/gestures` | Bounded, dependency-free triangle/square recognizer |
| `os/framework` | DisplayPolicy hook, stroke lifecycle and native-app handoff |
| `os/product` | Soong AIHome module, product resources and initial Home selection |
| `os/integration-base.json` | Exact upstream manifest, project commits and changed-file hashes |
| `os/patches`, `os/patch-series.json` | Three generated patches and their digests |
| `os/development-lock.json` | Development source pins; cannot authorize releases |
| `os/upstream-lock.json` | Separate production lock, still blocked |

Run these from the repository with Python 3 and a complete JDK 17:

```sh
python3 -m unittest discover -s tests -v
bash os/gestures/test.sh
bash os/framework/test.sh
bash android/test-core.sh
python3 scripts/prepare-os-integration.py \
  --base-cache /tmp/aifirst-integration-base --fetch --check
python3 scripts/os-pipeline.py \
  --lock os/development-lock.json --development validate-lock
```

The patch check fetches only the manifest and listed changed files at exact
commits. It reconstructs the combined patches from canonical sources and checks
the development lock's matching patch digest. It does not sync full projects,
prove new paths are absent throughout upstream trees, or compile Android.
Full-tree patch application remains a separate check on the actual checkout.

After editing canonical sources, run the assembler with `--write`, review the
patch diffs, and update the development lock's `patch_series_sha256` to the new
SHA-256 of `os/patch-series.json`. `--write` never approves a lock automatically.
Changes invalidate any inventory bound to those source pins. Do not directly
edit the generated patches.

CI repeats the component and pinned-file checks and builds/lints the AIHome APK.
Its `pixel-os-source-integration` artifact is source material, **not a flashable
image**. The whole Git repository is needed to regenerate it.

## Development source review

The development profile selects tag `2026100600`, manifest commit
`26f7e8a760d4343a501faf09773ec4cc61a6b56b`. The signed manifest and adevtool tag
were verified against the public signer from the official GrapheneOS website
repository. The signer source, hashes, vendor identity and limits are recorded
in [upstream-observation.json](../os/upstream-observation.json). This is a
source-development decision, not independent production trust approval.

The three patches were reconstructed against hash-pinned source files. Product
resources and Java were separately checked against Android SDK 35. Pure JVM
tests exercise recognizer geometry and stroke-session state. The framework
controller and DisplayPolicy changes have **not** been compiled by Soong.
The factory archive has **not** been downloaded/verified here, and the pinned
kernel prebuilt has **not** been independently reproduced from source.

## First complete development build

This is a maintainer procedure for a suitable Linux x86-64 build host. The
current cloud workspace has 16 GiB RAM and about 30 GiB free disk, so a full
source import would not fit. The wrappers require at least 64 GiB RAM and
400 GiB free disk; the [recommended runner](../os/runner.json) provides more
headroom. Compilation needs no emulator. The local dev Pixel is the test device.

1. Prepare the upstream build prerequisites and `repo` on that host, following
   [the source/build runbook](security-updates.md). Obtain the public signer file
   from the recorded source and verify its pinned hash. Keep the source checkout
   separate from this project, factory archives, dependency archives and logs.
2. Import the signed full source and apply the patches. For example, with
   `PIXEL_SOURCE`, `PIXEL_SIGNERS` and later `PIXEL_ARTIFACTS` set to absolute
   paths chosen for that host:

   ```sh
   python3 scripts/os-pipeline.py --lock os/development-lock.json --development \
     import --signers "$PIXEL_SIGNERS" --destination "$PIXEL_SOURCE"
   python3 scripts/os-pipeline.py --lock os/development-lock.json --development \
     patches --source "$PIXEL_SOURCE" --apply
   python3 scripts/os-pipeline.py --lock os/development-lock.json --development \
     verify-tree --source "$PIXEL_SOURCE"
   ```

3. Use the pinned upstream vendor/dependency preparation instructions. Retain
   the exact factory and dependency archives outside the checkout and hash
   every input. Record commands, generator revision and resulting paths. This
   step has not been executed here; a complete generated-input plan cannot be
   truthfully supplied before examining those outputs.
4. Capture the actual outputs with a plan in the schema described in
   [the generated-input runbook](security-updates.md):

   ```sh
   python3 scripts/os-pipeline.py --lock os/development-lock.json --development \
     capture-generated --source "$PIXEL_SOURCE" \
     --plan "$PIXEL_GENERATED_PLAN" --artifacts "$PIXEL_ARTIFACTS" \
     --output "$PIXEL_GENERATED_INVENTORY"
   ```

   Capture is not approval. Review the provenance and outputs, then add their
   exact inventory SHA-256 and review reference under `generated_inputs` in the
   development lock. Hashes prove byte identity, not correct derivation. The
   verifier admits only those declared paths, bytes, modes and safe links;
   there is no blanket exemption for vendor files or `node_modules`.
5. Record numeric `BUILD_NUMBER`, Unix `BUILD_DATETIME` and optional `BUILD_JOBS`
   (default 8), then run:

   ```sh
   bash scripts/os-build-development.sh "$PIXEL_SOURCE" \
     --generated-inventory "$PIXEL_GENERATED_INVENTORY" \
     --artifacts "$PIXEL_ARTIFACTS"
   ```

   This verifies the development source and reviewed generated bytes before
   sourcing build code, selects `tegu-cur-userdebug`, leaves `OFFICIAL_BUILD`
   unset, and rejects a resolved product that includes the official `Updater`.
   It builds target-files and OTA tools with development identities; it does not
   run production signing, release finalization, publication or flashing.

The pinned upstream [product definition](https://github.com/GrapheneOS/platform_build/blob/b0f697df8cc9519408ca0a404e918cd51bde0735/target/product/media_system.mk#L39-L41)
includes `Updater` only when `OFFICIAL_BUILD` equals `true`. The wrapper also
checks resolved base and debug package lists before building. The pinned
[envsetup](https://github.com/GrapheneOS/platform_build/blob/b0f697df8cc9519408ca0a404e918cd51bde0735/envsetup.sh#L598-L618)
accepts the `tegu-cur-userdebug` product/release/variant syntax.

A successful first compile must be followed by image/package inspection and a
device-specific installation and recovery procedure. No flash commands are
included here and no phone has been modified by this workspace. The separate
production build/release workflow keeps its own key, updater, provenance and
hardware-evidence requirements.

## Pixel validation after the first build

Confirm initial Home selection and ChatGPT setup first, then test the opt-in
setting documented in [the framework guide](../os/framework/README.md). Verify
triangle/dialer and square/Messages, ordinary scrolling, deliberate near-misses,
keyboard behavior, Back navigation, incoming calls, screen lock, rotation,
overlays and profile changes. Measure mistaken activations and missed shapes
using real strokes; synthetic assertions do not supply those rates.

Keep recovery access available throughout development. Complete notification,
alarm, emergency calling, Settings, Play update and reboot tests before making
the Android controls less visible. Gesture recognition alone does not validate
the full phone experience.
