# Home app and official ChatGPT validation

The current milestone is the **native Home/UI app**. MCP, Plugins, pairing and
conversational device control are deferred, not prerequisites. Calls, messages,
notifications and settings continue to use Android's normal apps and controls.

The user has a dev Pixel and local MacBook. The cloud dev server is for source
and compilation. Physical installation, default-Home changes, unlock/wipe/flash
and relocking require explicit approval for the particular procedure. This
checklist does not grant it. No account/phone validation was performed while
writing this document.

## Current acceptance evidence

| Check | Evidence | Status |
| --- | --- | --- |
| Current UI build | Source commit, APK build/lint, APK hash, manifest/permission inspection. | See current verification report; older bridge APK results do not cover UI changes. |
| Home | Approved installation and Home selection; ChatGPT launch plus reachable recovery controls. | **NOT_RUN on physical device.** |
| Native controls | Dialer, default Messages, Settings, All apps and official Play link resolve or present fallback. | **NOT_RUN on physical device.** |
| Account experience | Official app retains existing account, normal history, subscription, memory settings and supported Voice. | **NOT_RUN on physical device.** No custom-Plugin entitlement needed. |
| Optional tile | User adds/removes tile through Android controls; tap opens controls respecting lock screen. | **NOT_RUN on physical device.** |
| Recovery | Restore prior Home and uninstall without ChatGPT/network. | **NOT_RUN on physical device.** |
| Future OS | Repeat UI/app checks plus hardware, verified boot, encryption, SELinux, OTA and recovery. | Deferred OS milestone; not established by a UI APK. |

Use `PASS`, `FAIL`, `BLOCKED` with a reason, or `NOT_RUN`. Record actual app/OS
versions. Build success does not establish on-device behavior.

## Before installation

Prepare exact APK/hash, signing identity, package name, permissions, procedure
and reversible default-Home/uninstall recovery steps. The current app needs no
Internet, SMS or call permissions. Its optional tile is system-bound; there is
no overlay, accessibility service, polling UI or device-control daemon.

Approval to install a debug app does not permit an OS flash or wipe. Ordinary
Home-app testing does not require bootloader unlock. Keep the daily-use phone
outside testing unless separately authorized.

## Dev Pixel checks after approval

| Case | Expected observation |
| --- | --- |
| ChatGPT present | Launch genuine `com.openai.chatgpt` with standard Android mechanisms. No internal activities, embedded copy or automatic taps. |
| ChatGPT absent/disabled | Native controls/All apps stay usable. Official Play link opens the OpenAI listing or clear supported fallback. |
| Home/navigation | Verify Home, Back and Recents with ChatGPT, other apps and after Settings. No launch loop that prevents recovery. |
| Phone | `ACTION_DIAL` opens native dialer; opening it does not place a call. Native dialer retains calling and emergency-call UI. |
| Messages | Opens default messaging app; launcher does not read messages or send SMS. |
| Settings | Stock Settings opens and owns network, notification, permission, account and default-app controls. |
| All apps | Launchable apps open through Android; missing handlers fail visibly without hiding recovery. |
| Notifications/calls | Notification shade, incoming-call presentation and lock screen remain usable. Launcher does not collect notification content or call state. |
| Offline | Native app controls remain accessible when ChatGPT cannot connect. This does not imply offline ChatGPT, SMS delivery or network-independent calling. |
| Optional tile | Add/use/remove through Quick Settings; a tap opens controls, respects unlocking requirements and does not overlay other apps. |
| Official account | Use existing account/workspace; inspect normal history/settings without exporting private data or resubscribing. |
| Official Voice | Start via official controls; record behavior without assuming external Voice-start or wake-word support. |
| Recovery | Restore prior default Home via Settings and remove app if desired. No network/ChatGPT dependency. |

App handoff does not prove a call happened, a message was sent or a setting
changed. Do not make test calls/send messages unless the user authorizes those
specific actions.

## Minimal evidence

```text
run_id:
date_time_and_timezone:
source_commit:
apk_sha256_and_signing_identity:
dev_pixel_model:
os_build_and_security_patch_level:
chatgpt_android_version:
test_case:
network_and_lock_state:
expected_observation:
actual_observation:
status: PASS | FAIL | BLOCKED | NOT_RUN
sanitized_evidence_location:
```

Do not include credentials, private conversations, memory, messages, contacts
or account identifiers in public evidence. Review screenshots before sharing.

## Deferred integration and OS checks

Earlier MCP discovery, remote queue, authentication/replay, Clock handoff and
typed/Voice tool tests belong to the archived experiment. They are not current
UI acceptance tests. See its [protocol record](../bridge/README.md) and
[historical research](chatgpt-feasibility.md). If reopened, tools must run on the
Pixel with no project cloud runtime; see [on-device-mcp.md](on-device-mcp.md).
Do not configure a Plugin to validate this Home app.

On a later approved GrapheneOS-derived candidate, repeat compatibility checks
with sandboxed Google Play and ChatGPT in the same profile. Use the official
Play listing; do not bundle the APK. App updates remain independent of OS OTAs.
Follow the OS runbook for firmware, signing, verified boot, SELinux, encryption,
rollback protection, physical OTA and recovery. None is implied by installing
the current UI APK.
