# Official ChatGPT experience and deferred integration research

Current scope is a **native Android Home app that opens the unmodified official
ChatGPT app**. MCP and conversational device control are deferred. Plugin
eligibility and phone-local tool connectivity do not block this UI milestone.

Phone opens the dialer with `ACTION_DIAL`; Messages opens the default messaging
app; Settings opens system Settings. All apps provides ordinary app access and
recovery. The official Play listing supplies ChatGPT installation and updates.
Optional Quick Settings controls use a system-bound tile, not an overlay.
Android retains calls, notifications, lock screen, permissions and settings.

The current APK has no Internet, SMS, or call permissions, remote-control
endpoint, polling screen, MCP server, or background daemon. Its optional
`TileService` is system-bound. It does not inspect ChatGPT conversations,
memory, credentials, microphone audio, or account entitlements. ChatGPT's own
online behavior and permissions remain within the official app.

## Current experience

| Capability | Implementation boundary | Validation |
| --- | --- | --- |
| Open ChatGPT | Standard package launch API for `com.openai.chatgpt` [A1, A2]; no private activity or proprietary deep link. | Confirm launch and an accessible fallback when absent/disabled. |
| Preserve account experience | Official ChatGPT owns sign-in, subscription, history, memory and Voice [A2, A3]. No account data is copied or migrated. | Use the existing account; confirm normal behavior without exporting personal data or resubscribing. |
| Phone and Messages | User-initiated standard app/intent launches; native apps own calling and sending. | Check handlers. Opening a UI does not prove a call occurred or a message was sent. |
| Controls and recovery | System Settings, All apps and normal navigation remain available. Optional tile opens controls on a tap. | Check offline use, lock-screen behavior and restoring the prior Home app. |
| Install/update ChatGPT | [Official Play listing](https://play.google.com/store/apps/details?id=com.openai.chatgpt). Do not bundle or modify its APK. | Verify publisher and update path on the approved dev Pixel. |
| Official Voice | User selects Voice in the official app. Reviewed help describes user-controlled “Start with Voice” on supported mobile versions for new/empty chats [V2]. | No external Voice-start contract is established. No automatic Voice, wake-word or specific-conversation startup promise. |
| Eventual replacement OS | Retain supported installation/login dependencies. On a GrapheneOS-derived build, sandboxed Google Play and ChatGPT belong in the same profile [A4, A7]. | Physical compatibility on the signed OS remains a later gate. App/Play updates stay independent of OS OTAs. |

No physical-device validation was performed by this documentation work. See
[account-device-validation.md](account-device-validation.md) and the current
build/verification report. An APK build proves neither on-device UI behavior
nor app compatibility on a replacement OS.

## Historical MCP investigation — deferred

These findings preserve the October 11, 2026 investigation. They are not setup
steps, a deployment plan, or current Home-app acceptance gates. The remote
Python MCP/relay and Android polling UI were an earlier experiment. The current
app no longer uses that transport.

If tools are revisited, the user's requirement is MCP and device execution on
the Pixel with **no project cloud runtime**. Official Android connectivity to
that endpoint remains unresolved; see [deferred research](on-device-mcp.md).

| Historical finding | Primary evidence | Limit |
| --- | --- | --- |
| Mobile Plugins | Plugin help and ChatGPT Learn describe mobile surfaces [P1, P2]. | Depends on plan, workspace, role, region and capability. Does not establish Android-local MCP execution. |
| Local MCP | Help says saving local apps to an account does not make their tools available on web/mobile; local MCP apps run on desktop [P1]. | A desktop/USB client reaching a server does not prove official Android access. |
| Custom MCP registration | Web setup accepts a URL or Tunnel, read/write tools, SSE/streaming HTTP and supported auth options [P3]. | No phone-local connection contract was established. Current launcher uses none of these. |
| Live Voice Plugins | September 23, 2026 release notes: “Live now supports plugins on web, iOS, and Android.” [V1] | Does not establish phone-local hosting. Specific typed and Voice paths need separate evidence if resumed. |
| Conflicting older help | Developer-mode help says MCP apps are web-only [P4]; reviewed Voice help retains launch-era plugin restrictions [V2]. | Distinguish generation/client surface instead of assuming universal availability or impossibility. |
| Secure MCP Tunnel | Outbound HTTPS to an OpenAI-hosted endpoint with runtime credentials and organization/workspace permissions [T1, T2]. | Not a direct local Android call. Reviewed release targets were Linux, macOS and Windows, not Android [T3]. No tunnel deployed. |
| Authentication | Plugin auth describes OAuth 2.1/PKCE; tunnel permissions differ from MCP user identity [P5, T1]. | A bearer accepted by a local test client does not prove official ChatGPT auth. |
| GPT Actions | REST APIs in custom GPTs [G1]; reviewed FAQ scheduled standard retirement December 11, 2026, subject to account notices [G2]. | Not part of this UI or a substitute for the official app. |
| Clock intent handoff | Android documents Clock intents and activity-launch restrictions [A5, A6]. | Historical `handed_off` did not prove alarm creation. Current shortcuts do not claim remote action completion. |

Historical tests established local protocol/queue behavior only. No official
account integration, mobile tool invocation, or physical device-control test
was demonstrated. No private ChatGPT endpoints, token extraction or APK
modification were used.

## Sources retained from the investigation

Sources were reviewed through Exa on **2026-10-11**, with bounded follow-up
checks of local-MCP and tunnel platform support. These mutable pages document
the research record, not current account availability. No additional
integration research is required for the UI milestone.

| ID | Primary source |
| --- | --- |
| P1 | [Plugins in ChatGPT](https://help.openai.com/en/articles/20001256-plugins-in-chatgpt) |
| P2 | [Plugins — ChatGPT Learn](https://learn.chatgpt.com/docs/plugins) |
| P3 | [Add custom MCP server](https://developers.openai.com/api/docs/guides/custom-mcp-server) |
| P4 | [Developer mode and MCP apps](https://help.openai.com/en/articles/12584461) |
| P5 | [Plugin authentication](https://developers.openai.com/plugins/build/auth) |
| V1 | [Release notes — September 23, 2026](https://help.openai.com/en/articles/6825453-chatgpt-release-notes) |
| V2 | [ChatGPT Voice](https://help.openai.com/en/articles/20001274/) |
| T1 | [Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) |
| T2 | [Tunnel end-user guide](https://github.com/openai/tunnel-client/blob/master/docs/end-user-guide.md) |
| T3 | [Tunnel release platform matrix](https://github.com/openai/tunnel-client/blob/master/.github/workflows/release.yml) |
| G1 | [GPT Actions](https://developers.openai.com/api/docs/actions/introduction) |
| G2 | [Custom GPT retirement FAQ](https://help.openai.com/en/articles/20001519-custom-gpt-retirement-and-migration-faq) |
| A1 | [Android PackageManager](https://developer.android.com/reference/android/content/pm/PackageManager#getLaunchIntentForPackage(java.lang.String)) |
| A2 | [Official ChatGPT Play listing](https://play.google.com/store/apps/details?id=com.openai.chatgpt) |
| A3 | [ChatGPT Android FAQ](https://help.openai.com/en/articles/8142208-chatgpt-android-app-faq) |
| A4 | [Supported login browsers](https://help.openai.com/en/articles/8194942-google-chrome-as-the-default-browser-for-the-chatgpt-android-app) |
| A5 | [Android Clock intents](https://developer.android.com/guide/components/intents-common#Clock) |
| A6 | [Background activity restrictions](https://developer.android.com/guide/components/activities/background-starts) |
| A7 | [GrapheneOS sandboxed Google Play](https://grapheneos.org/usage#sandboxed-google-play) |
