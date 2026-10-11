# AI-first Pixel distribution

An independent project to build a maintained AOSP-based OS for **Pixel 9a
(`tegu`)**, centered on the official ChatGPT Android app. The recommended base
is a small **GrapheneOS derivative**, with our own signing keys and OTA channel.
This checkout is an initial bridge/launcher prototype and release-engineering
foundation. **It is not a built or flashable replacement OS.**

Cloud verification: Android debug APK built, lint clean, 44 Python tests and
84 Java safety assertions passed. Official ChatGPT-to-phone execution and the
complete OS build remain unverified; see the verification record below.

The app install/update source is [OpenAI's official Google Play listing](https://play.google.com/store/apps/details?id=com.openai.chatgpt).
Keep the OpenAI-signed app separate from our OS images. On the proposed base,
install sandboxed Google Play in the same Android user profile and use Play to
install/update ChatGPT normally. Signing into the official app preserves access
to the account's supported subscription, conversations, memory, and Voice
features; this project does not reimplement or extract them. Actual compatibility
with our future OS build still needs testing on the dev Pixel.

## Start here

| Deliverable | Location |
|---|---|
| OS comparison, recommendation, licenses, vendor dependencies | [OS foundation](docs/os-foundation.md) |
| Current official ChatGPT capability and account/client limits | [Feasibility matrix](docs/chatgpt-feasibility.md) |
| What actually passed here and what remains untested | [Verification record](docs/verification.md) |
| Launcher, Clock handoff, explicit device confirmation | [Android component](android/README.md) |
| Authenticated relay, MCP SDK tools, status model | [Bridge component](bridge/README.md) |
| Reproducible setup and dev-server transfer | [Development guide](docs/development.md) |
| Upstream imports, signing, OTA rollout, emergency updates | [Security-update process](docs/security-updates.md) |
| Stages and acceptance criteria | [Roadmap](docs/roadmap.md) |
| Review of the two proposed existing bridges | [Bridge candidates](docs/bridge-candidates.md) |
| Security boundaries | [Threat model](docs/threat-model.md) |

## Initial behavior

The optional Android HOME app offers a prominent ChatGPT entry and offline
access to the normal Android Settings and system controls. App installation and
updates use a fixed Play link in its settings area, without a store-browsing home
experience. The supported Play Store itself stays unmodified. A visible test screen
polls the relay and asks the user to approve each request. Only allowlisted app
launches and Clock alarm requests are implemented. No shell, calls, SMS,
accessibility automation, ChatGPT APK modification, or undocumented endpoint is
used. The foreground harness is temporary; the final product requires OS
integration and a tested device-service lifecycle.

The Python MCP SDK adapter exposes `open_app`, `set_alarm`, and
`get_action_status`. The relay uses separate operator and device credentials,
durable queue state, request expiry, and duplicate protection. `handed_off`
means Android accepted an intent, **not** that Clock saved an alarm.

The local stdio/loopback MCP transport is for development. Connecting the
official ChatGPT client requires the supported authentication/transport setup
and account tests in the feasibility matrix. Local MCP tests do not establish
Android typed-chat or Live tool support for the owner's account. No separately
billed API chatbot replaces the official app.

## Development checks

On an already configured Python 3.12/JDK 17+ host:

```sh
make test
```

For dependency installation and the actual APK build, follow the [development
guide](docs/development.md). The APK, OS image, signed OTA, account integration,
and physical-device tests have separate verification gates. CI does not flash
devices, publish a release, generate production keys, or provision resources.

This project is unaffiliated with OpenAI, Google, GrapheneOS, and LineageOS.
See [LICENSE](LICENSE) and [NOTICE](NOTICE).
