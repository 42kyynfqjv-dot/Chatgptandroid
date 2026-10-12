# Roadmap

The current work is a ChatGPT-first UI on the dev Pixel's existing Android OS.
MCP is deferred and is not a prerequisite for any UI test.

| Stage | Work | Exit evidence |
|---|---|---|
| 1 — Small APK | Home opens official ChatGPT; native Phone, Messages, Settings, recovery, and optional controls tile | APK compilation, Android lint, Home-routing regression checks |
| 2 — Dev Pixel UI | Install via local MacBook; try Home, Back, native calls and messages, tile, lock/unlock, app updates, and recovery | Recorded results on the actual Pixel and ChatGPT app versions |
| 3 — Refine daily use | Fix issues observed on the dev Pixel; assess navigation, accessibility, and battery behavior | Repeat physical checks after relevant fixes; usable recovery and app updates |
| 4 — Possible OS candidate | Revisit the original replacement-OS goal after UI acceptance; verify upstream and vendor inputs, independently signed product apps, updater identity | Unsigned OS candidate with provenance and signing rehearsal; no weakened platform security |
| 5 — OS release proof | Separately authorized installation and verified boot, signed OTA, recovery, rollback protection, hardware compatibility | Physical release evidence and an owned security-update process |

The modest cloud server builds the APK. The MacBook and dev Pixel are local;
the Pixel is the test device. An APK build packages our small app, not Android.
The full-OS runner specification is only a reference for later work.

The immediate next step after a verified APK is the
[dev Pixel UI check](pixel-quickstart.md). No Plugin eligibility check, bridge
setup, account migration, new ChatGPT subscription, or cloud service is needed.

Any future OS installation needs a separate procedure naming exact artifacts,
device model, expected data loss, signing/bootloader constraints, backups, and
recovery. A successful APK test does not justify a flash or unlock operation.
