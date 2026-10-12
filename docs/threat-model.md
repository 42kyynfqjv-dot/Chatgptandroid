# Home app security boundaries

Current scope is native Android Home and controls around unmodified official
ChatGPT. **MCP and device-tool integration are deferred.** The app has no
Internet, SMS or call permissions, remote queue, relay setup/polling UI or
device-control daemon. Its optional Quick Settings tile is a system-bound
`TileService`, not an overlay.

## Current boundaries

Android owns calls, messages, notifications, locking, permissions and settings.
The launcher opens Phone with `ACTION_DIAL`, launches default Messages and
system Settings, and offers All apps and the official ChatGPT Play listing.
A launch is a user-initiated handoff; it does not complete actions inside the
destination app.

Official ChatGPT/account data are outside this project's domain. The launcher
does not receive conversations, memory, subscription details, credentials or
microphone audio. It uses standard package launching, not private APIs,
modified APKs, accessibility scraping or embedded ChatGPT. The official app's
online service and permissions remain its own.

| Risk | Control | Device check |
| --- | --- | --- |
| Home traps user when ChatGPT is absent/offline | Reachable native controls, Settings and All apps; recovery independent of remote tools. | Home/Back/Recents, offline/missing app, restore previous Home. |
| Shortcut calls or sends unintentionally | Dialer opens with `ACTION_DIAL`; Messages opens its app; no call/SMS permissions. | Opening either UI has no communication side effect. |
| Missing/blocked destination | Standard Android resolution and visible fallback. | Missing/default/disabled handlers. |
| Launcher impersonates/replaces system UI | Android owns Settings, notifications, calls and lock screen. No overlay/accessibility service. | Normal navigation, notification shade and call presentation. |
| Tile bypasses lock screen | System-bound, user-initiated interaction obeying Android launch/lock rules. | Locked/unlocked use and removal. |
| Credentials/content leak | No ChatGPT data interface or network permission; official app owns login. | Inspect manifest/code and sanitize test evidence. |
| All apps implies completed work | Launch Android-resolved activities; no success claims about destination actions. | Labels/icons/handlers and failures. App labels are display data, not instructions. |
| Debug APK mistaken for production OS | Record source/build/hash and debug signing. | UI build does not prove signing, patch coverage or OTA correctness. |

Do not add broad permissions to bypass an unavailable app, background-launch
restriction or unsupported ChatGPT integration. Home selection, installation
and OS unlock/wipe/flash are distinct approvals.

## Historical bridge lessons — not active runtime

The [archived Python experiment](../bridge/README.md) used separate operator and
device bearers, strict schemas, bounded queues/TTL, transactional claims,
idempotency and a device journal before intent dispatch. The old Android relay
UI is removed from this app. No bridge was deployed.

That design treated model/tool arguments as untrusted and required visible
device approval. Relay compromise could fabricate requests/status; separate
bearers limited roles without establishing multi-user identity. Loopback was
not authentication. A lost acknowledgement could leave `unknown`; `handed_off`
did not prove alarm creation. Exactly-once Android effects were not claimed.

Retain those lessons if tooling resumes. The user's requirement is on-Pixel
MCP/execution with no project cloud runtime, requiring a separate review of
caller identity, lifecycle, permissions, replay, consent and result semantics.
Official ChatGPT Android connectivity remains unproven. That research does not
block current UI work or authorize a new relay/background service.

## Eventual OS

Preserve verified boot, SELinux enforcing, encryption and rollback protection.
Production signing, firmware matching, updates and physical recovery follow
the OS runbook. Home-app inclusion does not justify framework privilege, broad
SELinux exceptions or weaker locking/background-start protections. Retain
independent Settings and recovery access.
