# AI Home for Pixel

ChatGPT as the main phone experience, with normal Android Phone, Messages,
Settings, calls, and notifications still available. The current deliverable is
a **small launcher APK for the dev Pixel**, running on its existing Android OS.
MCP and device automation are deferred. No project server runs the phone UI.

## What this version does

- Opens the official ChatGPT app when Home is pressed, after you enable
  **ChatGPT on Home** and select AI Home as the default home app.
- Provides **Phone**, **Messages**, **Settings**, and **All apps** on a controls
  screen. The AI Home app icon always opens these controls.
- Offers an optional **Phone controls** Quick Settings tile: swipe down from
  ChatGPT to reach the native controls.
- Keeps Android's incoming-call UI, notifications, volume controls, lock screen,
  emergency access, and full Settings app in charge of their normal functions.
- Opens the official ChatGPT Play listing for installation and updates. Play
  remains available for maintenance without becoming the home experience.

The official ChatGPT app remains unmodified. Voice and conversations stay inside
it; this launcher cannot make ChatGPT operate the phone. The controls are reached
through Android's shade or AI Home, rather than inserted into ChatGPT's UI.

## Try it on the dev Pixel

1. Download `android-debug-and-lint` from the latest successful
   [GitHub Actions run](https://github.com/42kyynfqjv-dot/Chatgptandroid/actions/workflows/components.yml)
   and extract `app-debug.apk` on your MacBook.
2. Install that APK on the dev Pixel and open **AI Home**. Check Phone,
   Messages, Settings, and Open ChatGPT first.
3. Add the **Phone controls** tile, enable **ChatGPT on Home**, and choose
   **AI Home** as the default home app.

The [short device guide](docs/pixel-quickstart.md) covers USB installation,
the checks to make, and returning to Pixel Launcher. No bootloader unlock,
wipe, OS flashing, or cloud connection is involved in this prototype.

## Development

The modest cloud server builds the APK. The local MacBook transfers it to the
local dev Pixel for physical tests. An APK build packages the launcher; it does
not compile Android. See [development setup](docs/development.md) and the
[Android component](android/README.md).

```sh
bash android/test-core.sh
make apk
```

Build and lint checks do not establish on-phone behavior. Current and historical
results are recorded in [verification](docs/verification.md).

## Later work and reference

The original replacement-OS goal remains a later, separate milestone. There is
no flashable OS image in this repository. The proposed base is a small
GrapheneOS derivative with its own signing and update responsibility.

| Reference | Purpose |
|---|---|
| [Architecture](docs/architecture.md) | Current UI design and official-app boundary |
| [Roadmap](docs/roadmap.md) | UI prototype, physical tests, then possible OS work |
| [OS foundation](docs/os-foundation.md) | Base comparison, licenses, vendor dependencies |
| [Security updates](docs/security-updates.md) | Future OS signing, OTA, and release process |
| [Threat model](docs/threat-model.md) | Current app boundaries and deferred automation |
| [ChatGPT feasibility](docs/chatgpt-feasibility.md) | Dated integration research; not a UI prerequisite |
| [Bridge reference](bridge/README.md) | Archived relay experiment and protocol tests |

This project is unaffiliated with OpenAI, Google, GrapheneOS, and LineageOS.
See [LICENSE](LICENSE) and [NOTICE](NOTICE).
