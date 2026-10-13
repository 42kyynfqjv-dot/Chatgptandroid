# AI Home OS for Pixel 9a

This project builds a **replacement Android OS for Pixel 9a (`tegu`)**, based on
a small GrapheneOS derivative. Official ChatGPT is the main conversational app;
Android retains Phone, Messages, Settings, notifications, lock screen and
recovery. MCP remains deferred. Cosmetic refinement is paused while OS
integration and build preparation advance.

**There is no compiled or boot-tested OS image yet.** The current workspace has
16 GiB RAM and about 29 GiB disk capacity, insufficient for a full source sync
and Android build. The work here prepares real framework/product patches and
verified build inputs; it is not a claim that the earlier APK is an OS.

## OS integration now in source

- [Gesture recognizer](os/gestures/README.md): one-finger triangle and square
  geometry, with 239 synthetic assertions. These are not recorded phone tests.
- [Framework observer](os/framework/README.md): a pinned `DisplayPolicy` hook
  maps a completed triangle to the native dialer and a square to default
  Messages. No edge hold or extra finger is required. It defaults **off** through
  `aifirst_shape_gestures_enabled`.
- [Product integration](os/product/README.md): a source-built Soong `AIHome`
  module, initial HOME-role default, and product resource default enabling
  ChatGPT-on-Home. Existing user choice and stock recovery/Settings remain.
- Three canonical patches regenerated against hash-pinned changed files from
  GrapheneOS `2026100600`, plus source and generated-input verification.
- A source-only development lock and `userdebug` build path, separate from
  production signing and OTA release gates.

**Gesture touches still reach ChatGPT.** The observer does not intercept or
retract them; ChatGPT may scroll, select or otherwise react before the native
app opens. The framework controller, full Soong build, input behavior and phone
boot still need real validation. A successful intent handoff does not place a
call or send a message.

The official ChatGPT APK is not bundled or modified. Installation and app
updates use its official Play listing, independently of OS OTAs. Voice and
conversations stay in the official app.

## Build path

Start with the [OS integration guide](docs/os-integration.md), then the
[development setup](docs/development.md) and [security-update process](docs/security-updates.md).
Full compilation requires a suitable runner, exact source verification and
reviewed generated vendor/dependency inputs. No production signing keys or live
update endpoint are required for the isolated development build; those remain
mandatory for production.

The patch assembler fetches/checks only a small pinned source subset and
manifest. It does **not** sync or compile complete upstream projects. No full
source sync, factory/vendor archive verification, vendor generation, full Soong
build, boot or flash has been completed. See [verification](docs/verification.md)
for exact checks and limits.

The local MacBook and dev Pixel remain the later hardware-test path. Publishing
sources or building artifacts does not authorize installation, unlocking,
wiping or flashing.

## Reference

| Reference | Purpose |
|---|---|
| [Architecture](docs/architecture.md) | Framework, product, official-app and recovery boundaries |
| [Roadmap](docs/roadmap.md) | Full OS build and physical validation gates |
| [OS foundation](docs/os-foundation.md) | Base choice, source evidence, licenses and vendor dependencies |
| [Security updates](docs/security-updates.md) | Source provenance, our signed updates and release process |
| [Earlier APK quickstart](docs/pixel-quickstart.md) | Historical standalone UI test harness; not an OS installation guide |
| [Android component](android/README.md) | AI Home app sources and isolated component build |
| [ChatGPT feasibility](docs/chatgpt-feasibility.md) | Historical tool research; MCP is deferred |
| [Archived bridge](bridge/README.md) | Superseded relay experiment |

This project is unaffiliated with OpenAI, Google, GrapheneOS and LineageOS.
See [LICENSE](LICENSE) and [NOTICE](NOTICE).
