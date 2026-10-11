# AI Home Android prototype

**Current target:** host MCP and execute tools on the Pixel. This APK does not
yet host an MCP server; its remote relay controls belong to the superseded
transport experiment. Normal launcher/Settings functions are independent of
that experiment. Do not configure a cloud relay as a product prerequisite.
See [the on-device MCP proof](../docs/on-device-mcp.md).

AI Home is an optional HOME launcher and an explicitly operated relay client. It is **not an operating system, a ROM, an OpenAI product, or a privileged device agent**. It can run on a compatible Android OS while the stock Settings, system controls, installed apps, and the existing launcher remain available. Minimum Android API 30; built against API 35 for the Pixel 9a project.

## What the app does

- Opens the official `com.openai.chatgpt` package using Android's package launch intent. The user starts Voice inside ChatGPT. No private endpoint, Voice deep link, account-token extraction, microphone capture, or chat-content access is used.
- Presents All apps, Clock, Browser, the full Android Settings app, and **Default home / choose launcher**. Making AI Home the default is optional and done in Android's home settings. Back out or choose your existing launcher there to undo the choice.
- Offers **Install / update ChatGPT** under Settings / app updates. It opens the user-specified [official Google Play listing](https://play.google.com/store/apps/details?id=com.openai.chatgpt&referrer=downloadWebPage&pli=1); no ChatGPT APK is bundled, mirrored, or downloaded by this project. The listing may open normal Play UI. There is no store-browsing surface in AI Home.
- Lets the user save an HTTPS relay origin and device bearer token, then tap **Connect and poll once**. Saved results are synchronized first, then at most one queued request is reviewed. This is a foreground-only manual prototype: it does not run a service, schedule background polls, start at boot, or promise delivery while ChatGPT is open or the screen is locked.
- Shows an on-device Approve/Reject dialog for every valid fresh remote action. Supported actions are only `open_app` for `chatgpt`, `settings`, `clock`, or `browser`, and `set_alarm` with validated hour, minute, and label. There is no arbitrary URL, package, shell, SMS, call, accessibility, or admin command.

On GrapheneOS, installing sandboxed Google Play and the official ChatGPT app in the **same user profile** is the supported Play distribution path described by the parent project. App availability, account features, Play compatibility, and Voice still depend on the installed app, OS, region, and account. AI Home neither checks nor guarantees those entitlements. Play-managed app updates and OS updates are separate. The launcher cannot suppress Play's own full UI if the user opens it.

## Build and checks

Requirements: a full JDK 17, Android SDK platform 35 and build-tools 35.0.0, network access to Google's Maven repository/Maven Central/Gradle, and Bash or another POSIX shell. Set `JAVA_HOME` to the JDK and `ANDROID_HOME` to the SDK. The parent repository includes an SDK setup script. Android Studio can also install the named SDK packages.

```sh
cd android
./test-core.sh
./gradlew --no-daemon assembleDebug lintDebug
```

Windows can use `gradlew.bat --no-daemon assembleDebug lintDebug` with the same SDK/JDK. The dependency-free core tests use the JDK compiler module and need a POSIX shell.

The official Gradle wrapper is pinned to **8.11.1**, AGP to **8.9.2**, compile SDK to **35**, and build-tools to **35.0.0**. The wrapper verifies the distribution SHA-256. Its committed JAR checksum is `2db75c40782f5e8ba1fc278a5574bab070adccb2d21ca5a6e5ed840888448046`; the distribution checksum is `f397b287023acdba1e9f6fc5ea72d22dd63669d59ed4a289a29b1a76eee151c6`, both from the [official Gradle checksum reference](https://gradle.org/release-checksums/). Version/checksum pinning makes tool selection repeatable; it is not a claim that signed APK bytes are reproducible across build hosts.

Output: `app/build/outputs/apk/debug/app-debug.apk`. Lint HTML: `app/build/reports/lint-results-debug.html`. Debug builds use a local development signing key and are not a production release. No device installation, launcher-default change, bootloader operation, or flashing is performed by the build.

The core test suite exercises production Java policy, expiration, and journal code: URL/credential validation, action allowlists, integer ranges, Unicode/control characters, clock rollback, process interruption, replay rejection, final-result persistence, conflicting receipts, corrupted journal fail-closed behavior, and concurrent duplicate reservation. Android integration and UI behavior need the device checks below; a passing core suite alone does not prove an APK build or device behavior.

In a managed environment preserve the configured network proxy and CA trust. Gradle needs Java proxy properties when the environment supplies an HTTP proxy; put these in an untracked Gradle user-home configuration. Do not commit proxy credentials, tokens, signing keys, or `local.properties`. SDK/Gradle cache paths must be writable.

## Pair and test manually

1. Build and review the debug APK; install it on a test profile/device through your normal Android process.
2. Leave the original launcher installed. Open AI Home as a normal app first; test Settings, Clock, Browser, All apps, and the ChatGPT link.
3. Start the parent project's relay behind trusted HTTPS. Generate distinct operator and device tokens as described in the relay documentation. Do not put either token in a URL, screenshot, chat, or repository.
4. In **Pair / change relay**, enter only the HTTPS origin (for example `https://relay.example.com`, optionally a port) and the **device** token. Paths, query strings, fragments, HTTP, and URL credentials are rejected. Save does not make a network connection.
5. Queue a supported request using the operator endpoint. Tap **Connect and poll once** in AI Home. Inspect its exact app or alarm time/label and request ID, then Approve or Reject.
6. For an alarm, Android receives `ACTION_SET_ALARM` with `EXTRA_SKIP_UI=false`. Review Clock's UI and confirm the actual alarm exists. The local result is only **handed_off** after `startActivity` accepts the intent; it never claims the alarm was created or completed. Clock behavior varies by installed handler.
7. Return to AI Home and tap the poll button to send the saved result. Check Request history and the relay. A result can become a relay conflict if its confirmation deadline elapsed while another app was open. This is visible as **relay conflict; not acknowledged**, preserves the local evidence, and does not replay the request or stop future polling.
8. Test Reject, expiry, locking the screen during review, leaving the launcher during review, no Clock handler, missing ChatGPT, relay offline/401/409, process death before/after handoff, and duplicate request IDs. No action should launch without a new visible approval; an interrupted in-flight action becomes **unknown** on recovery.

## Safety and practical limits

Pairing is stored in app-private preferences under Android's application sandbox; it is not a separate hardware-encrypted secret vault. Android file-based encryption and the device unlock protect that storage. Android backup and device-transfer rules exclude app data, the journal is in `noBackupFilesDir`, and sensitive app/dialog windows are marked secure. **Disconnect / forget token** removes local pairing while retaining replay history; revoke the token at the relay separately. Clearing app data, uninstalling the app, or removing the journal destroys local replay protection and must not be used as a way to retry an uncertain action.

Networking uses the platform HTTPS implementation and normal certificate validation, no redirects, bounded 64 KiB responses, and 10-second connect/read timeouts. Tokens are sent only in the Authorization header to the exact configured origin. A private/self-signed endpoint without an Android-trusted certificate will fail; there is no trust-all or HTTP switch. A poll in progress is cancelled when the Activity pauses, although a server may already have claimed it. Claimed but unreviewed requests eventually become unknown at the relay.

Approval requires an unlocked device and focus on the confirmation dialog. Fully and partially obscured approval touches are rejected. Expiry is checked against wall time and a local monotonic deadline capped at five minutes; rolling the wall clock back cannot extend an open approval window. The system still requires reasonable clock synchronization with the relay.

The append-only private journal synchronizes its file and initial directory entry to disk before enabling remote work, records reservation and dispatch intent synchronously before any launch, then records the local outcome. On process restart, unfinished entries become **unknown** and cannot execute again. Result transmission may be retried; Android intents are never automatically retried. Matching result receipts are acknowledged; HTTP 404/409 is retained as a terminal conflict. Corrupt/unwritable/full journals disable remote actions. The 2 MiB history limit is deliberately fail-closed; production software needs a reviewed retention/export/migration policy that preserves identifiers. This prototype has no journal-delete button or automatic pruning. Hardware power-loss behavior still needs device validation.

This is a single-device, single-relay-at-a-time prototype. It has no push delivery, background service, notifications, multi-profile management, chat-to-relay authentication inside the official app, or direct app-content control. If you select another relay, unsent results remain associated with their original origin. The parent bridge exposes an API; configuring any ChatGPT action connector is a separate account-dependent step and is not silently provided by opening ChatGPT.
