# AI Home 0.2 — native phone controls

This Android launcher prototype centers the **official ChatGPT app** while keeping the phone's native apps accessible. It is an ordinary app, not an operating system or an OpenAI product. No MCP server, relay, token, background polling, overlay, or accessibility service is required.

## Current behavior

- **Open ChatGPT** uses the package launch intent for `com.openai.chatgpt`. Chat and Voice run inside the official app; the user starts Voice there. AI Home cannot read conversations or modify ChatGPT's interface.
- **Phone** opens Android's dialer with `ACTION_DIAL`. **Messages** opens the OS-selected default SMS app, with a standard messaging-app selector as fallback. These are normal app launches; AI Home does not place calls, send messages, request their permissions, or replace incoming-call handling.
- **Android Settings**, **All apps**, and **Default home / choose launcher** remain accessible. Outbound apps open in their own tasks, so returning to controls does not finish a native phone screen.
- The **Phone controls** Quick Settings tile opens AI Home controls from ChatGPT or another app. It uses Android's supported `TileService`, including the immutable `PendingIntent` API on Android 14+. When locked, it asks Android to unlock before opening controls. This service is bound by SystemUI and runs no background worker.
- **ChatGPT on Home** is off initially. After opting in and choosing AI Home as the default home app, each fresh `MAIN`/`HOME` intent can open ChatGPT once. Resuming the Activity, recreating it after rotation/process death, launching the AI Home app icon, and using the tile do not trigger that route. Locked-device Home requests are skipped and never deferred to a later resume. If ChatGPT is unavailable, controls remain visible.
- **Install / update ChatGPT** opens the user-provided [official Google Play listing](https://play.google.com/store/apps/details?id=com.openai.chatgpt&referrer=downloadWebPage&pli=1) from App updates. The listing may display Play's normal interface. No store-browsing surface or ChatGPT APK is bundled here.

Android continues to handle notifications, the notification shade, lock screen, default apps, and incoming calls. AI Home has **no requested permissions**, including no Internet, alarm, call, or SMS permission. The tile's manifest `BIND_QUICK_SETTINGS_TILE` requirement restricts who can bind the service; it is not a permission granted to AI Home.

Version 0.1's relay UI and network/intent dispatcher have been removed. Upgrading clears the old pairing preferences. Its private journal and pure helper classes/tests are retained as historical material with no runtime callers; they do not provide any live remote-control feature.

## Try the controls

1. Install the reviewed build on a test device/profile through your normal Android process. Leave the existing launcher installed. Open **AI Home** from its app icon first.
2. Install/open official ChatGPT in the same profile. On GrapheneOS, the parent project describes sandboxed Google Play as the supported Play distribution path. Availability and account features depend on the actual app, OS, region, and account.
3. Tap **Add Phone controls tile**. Android 13+ shows the system add-tile prompt. On older supported versions, open Quick Settings → Edit and add **Phone controls** manually.
4. From ChatGPT, swipe down and tap **Phone controls**. Verify Phone, Messages, Settings, and All apps open correctly, and that their Back behavior leaves controls usable.
5. If desired, enable **ChatGPT on Home**, then use **Default home / choose launcher** to select AI Home. Verify a Home press opens ChatGPT, while the app icon/tile opens controls. Test repeated Home presses, Back, rotation, process recreation, locked Home, and missing/disabled ChatGPT.
6. Check incoming calls, notification access, and lock/unlock on the actual phone. To undo the launcher choice, use **Default home / choose launcher** and select the previous launcher.

No device installation or hardware verification is performed by the build. Device behavior, particularly OEM Quick Settings/task management and call interruptions, still requires these checks. This is not a kiosk mode and does not restrict other apps.

## Build and verification

Use a full JDK 17, Android SDK platform 35 and build-tools 35.0.0. Set `JAVA_HOME` and `ANDROID_HOME`; the parent repository supplies an SDK setup script. Android Studio can also install these packages.

```sh
cd android
./test-core.sh
./gradlew --no-daemon assembleDebug lintDebug
```

The core suite includes **16 current Home-routing assertions** and **84 retained legacy safety assertions**. The latter do not establish a live bridge or device integration. Lint and APK assembly check the Android sources; no emulator/instrumentation or physical-device test is claimed.

Build output: `app/build/outputs/apk/debug/app-debug.apk`. Lint report: `app/build/reports/lint-results-debug.html`. This is a development APK signed with a local debug key, not a production release. Windows can build using `gradlew.bat`; the dependency-free core test script requires a POSIX shell.

Tool versions are pinned: Gradle **8.11.1**, Android Gradle Plugin **8.9.2**, compile/target SDK **35**, build-tools **35.0.0**, minimum SDK **30**. The committed official wrapper JAR SHA-256 is `2db75c40782f5e8ba1fc278a5574bab070adccb2d21ca5a6e5ed840888448046`; its pinned distribution SHA-256 is `f397b287023acdba1e9f6fc5ea72d22dd63669d59ed4a289a29b1a76eee151c6`, verified against the [official Gradle checksum reference](https://gradle.org/release-checksums/). Tool pinning is not a claim that debug-signed APK bytes are reproducible across hosts.

In managed environments, preserve the configured proxy and CA trust. Map the inherited proxy hostname/port to Java's `systemProp.http.proxyHost`, `systemProp.http.proxyPort`, and HTTPS counterparts in an **untracked** Gradle user-home configuration. Use writable SDK/Gradle cache paths. Do not commit proxy credentials, signing keys, or `local.properties`.
