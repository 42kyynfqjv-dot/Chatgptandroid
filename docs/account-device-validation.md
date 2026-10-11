# Account and Pixel 9a validation gates

Prepared **2026-10-11**. **No account integration or physical-device test has been run.** This document is a future test protocol, not an installation instruction to execute now. The user has explicitly withheld authorization to install, flash, unlock, wipe, or otherwise modify their physical phone without separate approval. No step below grants that approval.

The [feasibility assessment](chatgpt-feasibility.md) distinguishes current Plugin documentation from legacy MCP and GPT Actions guidance. Complete web, Android typed, and Android Voice tests separately. Do not mark one passed because a local harness or Codex desktop can invoke MCP tools.

The user has a **development Pixel** available; use it for the real app, Clock, and candidate-OS acceptance tests after approval. No emulator is required to pass these hardware gates. Cloud tests can use a synthetic device to verify transport logic. The server offered for compilation is a build resource, not an approved public relay host. The official Play listing supplied by the user identifies the app but does not identify their ChatGPT plan or custom-MCP entitlement.

## Gate register

| Gate | Required evidence | Current status | Blocks |
| --- | --- | --- | --- |
| G0 — Cloud component verification | Reproducible build/test commands, exit status, artifact hashes, versioned source; distinguish simulator and Android execution. | See repository build/test report; no account/device inference allowed. | Any claim that the code itself builds or runs. |
| G1 — Account eligibility | Actual plan/workspace, permitted custom-MCP Plugin creation path, tool permissions, region and client availability. | **NOT_RUN — account information and UI unverified.** | Calling this user's bridge from ChatGPT. |
| G2 — Authenticated web Plugin | Supported setup, successful MCP initialization/discovery and authorized call; unauthorized/revoked access denied. | **NOT_RUN — no live custom Plugin or tunnel connected.** | Official ChatGPT bridge proof. |
| G3 — Android typed Plugin | On official Android app, typed prompt reaches the exact MCP tool with correlated relay result. | **NOT_RUN — no phone attached.** | Android typed control claim. |
| G4 — Android Live Voice Plugin | Same account, exact Voice mode and surface recorded; spoken prompt causes a real correlated tool request, and results are truthful. | **NOT_RUN — independent of G3.** | Conversational Voice control claim. |
| G5 — Device harness | Approved installation; local review, allowlisted app and Clock handoff, rejection and reconnect tests on Pixel 9a. | **NOT_RUN — physical changes require explicit approval.** | Device action proof. |
| G6 — Candidate OS compatibility | On separately approved signed candidate OS: genuine ChatGPT app installation/update/login, account state, text/Voice, app/Clock intents, network/sleep behavior. | **NOT_RUN — no replacement OS built or flashed by this protocol.** | Releasing the replacement distribution. |
| G7 — Release lifecycle | Real hardware update/recovery/rollback-protection tests, security update policy, staged OTA validation. | **NOT_RUN — see OS release runbook.** | Advertising a maintained production OS. |

Allowed terminal outcomes are `PASS`, `FAIL`, `BLOCKED` (document the permission/availability reason), or `NOT_RUN`. A product refusal, absent feature, or missing entitlement is useful evidence, not a reason to use undocumented endpoints. Record exact error text with personal information removed.

## Evidence record

Keep test results outside the public repository unless sanitized. Never record session cookies, passwords, OAuth codes, bearer tokens, tunnel runtime keys, device pairing tokens, private conversations, or memory contents. A plan label and a nonidentifying workspace alias are sufficient.

For every run record:

```text
run_id:
date_time_and_timezone:
tester:
source_commit:
apk_sha256_and_signing_identity: (only if a device build is involved)
relay_and_adapter_version:
chatgpt_plan_and_workspace_alias:
chatgpt_surface: web | android_chat | android_work | desktop_codex
chatgpt_android_version:
voice_mode: none | dictation | live | advanced | standard
device: simulated | emulator | Pixel_9a
os_build_and_security_patch_level:
plugin_path: current_plugins | legacy_developer_mode
transport: local_harness | secure_mcp_tunnel | public_https_oauth
network_state_and_power_state:
tool_name_and_sanitized_arguments:
action_id_and_idempotency_key: (non-secret correlation values only)
observed_state_transitions:
independent_device_observation:
expected_result:
actual_result:
status: PASS | FAIL | BLOCKED | NOT_RUN
sanitized_evidence_location:
```

Record exact app and OS versions; “latest” is not reproducible. Do not treat a model's verbal claim as proof of a tool call. Correlate the visible tool invocation, MCP/relay event, request ID, device receipt, and final result. Persist only minimal operational metadata. Use synthetic labels such as `BRIDGE-TEST-001` instead of personal alarm names.

## Phase A: account and web, without modifying the phone

1. Confirm the user's existing ChatGPT account and intended personal/workspace context. Do not create another account, buy a plan, or move conversations. Check the supported web UI for Plugins and the **Add custom MCP server** option. Record whether custom write tools are permitted. If only the legacy developer-mode path is available, record its restrictions rather than assuming the current Plugin route applies.
2. Choose a transport already authorized for testing. For Secure MCP Tunnel, verify the Platform organization, target ChatGPT workspace association, Tunnels Read + Use for runtime, and appropriate management permissions. Keep the runtime key on the host; do not put it on the phone or in plugin metadata. Verify tunnel readiness before debugging model behavior. The feasibility document includes a restricted single-operator **No authentication at MCP** lab path: it relies on restricted tunnel/Plugin access plus the adapter's relay bearer and does not establish per-user identity. For public/shared access, complete supported MCP OAuth and device/account authorization first; a local static-bearer test endpoint is not a substitute.
3. Start with synthetic device data and a controlled simulator. First confirm initialization and the exact tool list. Verify unauthenticated, invalid-token, wrong-device, revoked-token, and expired-credential requests fail. Tool-list visibility alone is insufficient proof that mutations are authorized.
4. Connect and install the private Plugin using the documented UI. Record the actual consent prompts and tool permissions. Choose the narrowest available scope. Do not enable silent broad approval merely to remove test friction.
5. In a fresh typed **web** chat, select the Plugin explicitly. Use `get_action_status(action_id)` for a known synthetic action fixture, then ask for `open_app(app="clock", idempotency_key=...)` against the simulator. The app enum is `chatgpt`, `settings`, `clock`, or `browser`; arbitrary package names are not accepted. The MCP adapter binds to one relay/device and has no caller-selected device parameter. Inspect actual arguments and results. Reject ambiguous time requests rather than letting the model guess AM/PM or timezone.
6. Demonstrate queue receipt, local confirmation requirement, rejection, expiry, and status retrieval against the simulator. For alarms use `set_alarm(hour=7, minute=0, label="BRIDGE-TEST-001", idempotency_key=...)`. Generate a fresh random URL-safe key of 16–80 characters for each independently authorized mutation, and reuse exactly that key when recovering the same request. Inspect the returned `id`, `action`, `params`, `status`, `created_at`, `expires_at`, and `detail`. State clearly that simulator acknowledgements cannot prove Android app launch or alarm creation. If the selected official ChatGPT transport/authentication is not ready, mark G2 `BLOCKED` before claiming integration.

G2 passes only after a real call from the official ChatGPT web product, through a documented authenticated path, reaches the intended synthetic device and receives an accurate result. A successful `curl`, Python client, unit test, or desktop Codex call does not pass G2.

## Phase B: official Android typed conversations

This phase requires user participation and, before any phone change, separate approval describing the exact change and recovery path. Merely signing into the same account does not prove the custom Plugin is available in the Android client.

1. Record the official app's version from its About screen and confirm the app is published by OpenAI using [the supplied official Play listing](https://play.google.com/store/apps/details?id=com.openai.chatgpt). Use the user's existing account and workspace. Verify normal chat history, subscription entitlements, memory settings, and existing Voice availability without exporting their contents. Do not resubscribe. On the approved GrapheneOS-derived candidate, sandboxed Google Play and ChatGPT belong in the same profile; do not bundle the APK into the OS or tie app updates to OS OTA releases.
2. Check whether the tested private Plugin is visible/installed on Android in Chat or Work. Record each surface independently. A desktop-only label, missing Plugin, disabled app, or missing write tool is a gate failure/blocker.
3. Before installing a device harness, repeat the web synthetic-device test from an **Android typed** chat if the Plugin is available. A phone can validate the cloud tool path while the target device remains simulated. Explicitly label this result “Android client → simulated device,” not physical-device control.
4. Repeat the same exact read and write prompts. Capture the tool call and relay correlation. Verify the UI shows approvals and accurate `queued`, `awaiting_confirmation`, and failed/expired results. Ask for an unallowlisted action and confirm no request with an unsupported capability reaches execution.

G3 passes only for the actual Android client/surface tested. A browser running on Android is a web-client test, not an official Android-app test.

## Phase C: mobile Voice — separate from typed success

1. Record the selected Voice mode and whether the conversation is in Chat or Work. Select **Live** where supported; keep Advanced and Standard results separate. A microphone keyboard or dictation button followed by sending text does not test live Voice tool calling.
2. Start with the already installed Plugin and synthetic device. Speak a precise request, for example: “Use the Pixel bridge to request the allowlisted Clock app on the test device. Tell me the actual status.” Verify a tool invocation reaches the relay, not just an affirmative spoken response.
3. Speak an alarm request specifying time, such as “Request a one-time alarm for 07:00 in the test device's local timezone, labeled BRIDGE-TEST-001. Tell me if it is only queued.” This remains a simulator test until Phase D is approved. Verify the actual tool arguments, device identity binding, and returned state.
4. Separately speak “Set an alarm for 7.” Expect clarification where context does not disambiguate. Test correction before approval, cancellation, network interruption, and a repeated request with an explicit reference to the same action. Check that retry handling cannot duplicate the action.
5. Confirm Voice reports rejected, expired, offline, and merely handed-off actions accurately. Speak a follow-up to fetch status; verify a new read invocation where current information is needed. Voice transcription alone is not a reliable verbatim log; use actual tool payloads as the action evidence.
6. Record whether any consent control requires touch. The system may be voice-led while still requiring device confirmation. Do not describe it as hands-free if approval requires a tap.

If typed works and Voice does not, mark G3 `PASS`, G4 `FAIL` or `BLOCKED`, and describe the exact mode/client limitation. Keep the official app's normal Voice experience available; do not quietly replace it with a paid inference API chatbot.

## Phase D: physical harness, after explicit approval

Before approval, prepare the exact APK identity/hash, permissions, relay endpoint/authentication design, installation method, and reversible uninstall/default-launcher recovery procedure. Installing the harness and changing the default launcher are separate phone changes that need to be covered by approval. Do not unlock or wipe a stock phone to test an ordinary app. If a later OS test requires unlock/wipe, that needs its own backup, data-loss, verified-boot, and recovery review.

After approval, test these cases on the Pixel 9a:

| Case | Expected evidence |
| --- | --- |
| Official ChatGPT shortcut | Normal launch through Android's documented package launch API; missing/disabled app produces an accessible fallback. No private activities or automatic synthetic taps. |
| Return and recovery controls | Home/recovery UI can reach Settings, Clock and other allowlisted essentials while offline or when ChatGPT is unavailable. The user can restore the previous launcher. |
| Pairing and revocation | Device-bound secret provisioned without logging; wrong credentials fail; revocation stops new requests; no cross-device execution. |
| Local denial | User rejects request; action reaches a terminal rejection without opening anything. |
| App handoff | User reviews and approves an allowlisted action in the harness; Android starts the expected app; truthful state is returned. |
| Clock handoff | User reviews the concrete hour/minute/label, then opens Clock through `ACTION_SET_ALARM` with its UI shown. Report `handed_off`; inspect Clock separately to determine whether an alarm was actually saved. |
| Clock cancellation / missing handler | Cancellation must not become “alarm completed.” No handler or launch exception becomes failure. |
| Lock screen / background | No bypass of lock screen or background activity restrictions. Queue/review notification or visible harness interaction is used according to implemented behavior. |
| Network loss / restart | Offline requests stay queued until expiry; reconnect does not execute stale requests or repeat previously handed-off actions. Restart and lost acknowledgement produce an explicit safe state, not a blind replay. |
| Bounds / allowlist | Invalid times, oversized labels, unsupported fields and app identifiers are rejected at server and device boundaries. No arbitrary intent strings, shell, SMS, calls or URL execution. |
| Timezone / ambiguity | Test device-local timezone interpretation around day boundaries. Never claim date-specific or DST guarantees beyond the implemented Clock contract. |
| Voice after real pairing | Repeat G4 with the real device. Correlate spoken request, tool, relay, local approval and handoff. A simulated-device Voice pass is not enough. |
| Stop / recovery | Disable the bridge, revoke tokens, and restore previous launcher without relying on ChatGPT or network access. |

Keep `completed` unavailable for alarms until an implemented, trustworthy confirmation mechanism proves alarm creation. A user can independently observe an alarm in Clock, but that observation must be recorded as manual evidence, not fabricated as a programmatic callback.

## Phase E: replacement OS acceptance

Repeat account/app and bridge tests on the signed AOSP-derived candidate, not only stock Android. Verify bootloader/verified-boot state, SELinux enforcing, encryption, matching vendor/firmware, app install/update/login, network changes, sleep/battery behavior, and accessible recovery controls. Include a real signed OTA and approved recovery test under the OS release runbook.

Any requirement for Google Play components, supported login browsers, or device attestation must be resolved through supported mechanisms. Do not modify ChatGPT, spoof integrity verdicts, extract tokens, or disable OS security controls. If official-app compatibility cannot be demonstrated on the chosen foundation, report the blocker before promoting it as the distribution's primary experience.

The requested end state is accepted only when a **real official Android typed call**, a **separate real mobile Voice call if required**, and the **device action / signed OS release lifecycle** are each evidenced. Until then, publish precisely scoped prototype and research results.
