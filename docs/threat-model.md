# Initial bridge threat model

This document records the earlier server-relay experiment. The chosen product
hosts MCP and device actions on the Pixel; no project cloud relay is part of
that target. Retain the validation/confirmation/replay lessons, but reassess
local caller authentication and Android service lifecycle for the
[on-device implementation](on-device-mcp.md). The remote deployment checklist
below is historical reference, not the current plan.

## Scope and trust

The official ChatGPT app and cloud account remain outside this project's trust
domain. No service here reads ChatGPT conversations, memory, authentication
tokens, subscription state, or microphone streams. The model can propose one
of the documented narrow tools. Its arguments are untrusted, including arguments
derived from messages, websites, documents, or tool output.

For the prototype there is one owner and one device per relay instance. The
operator credential may enqueue requests and read their status; the distinct
device credential may receive requests and report a bounded result. Neither
credential is a ChatGPT token. Multi-user account binding, OAuth, automated
pairing, secure credential rotation UX, and production hosting remain gates.

The authenticated relay is trusted: compromise can fabricate requests and
status, so the device independently validates allowed operations and requires
visible confirmation. TLS protects transport, not a compromised relay. Device
approval displays the actual parsed action. No free-text command is evaluated.

## Boundaries and controls

| Threat | Initial control | Remaining limitation |
|---|---|---|
| Prompt injection asks for destructive operations | Closed app identifiers, bounded clock fields, no shell/calls/SMS/files/URLs; device approval | User can still approve an unwanted allowed action |
| Stolen operator credential | Separate device credential, bounded queue/TTL, local confirmation | Attacker can enqueue nuisance requests/read status until rotation |
| Stolen device credential | Role separation and fixed single-device routing | Attacker can consume requests or fabricate a handoff; tokens need private storage and rotation |
| Replayed or retried request | Transactional relay claim, idempotency key, durable device journal before side effect | Process loss may produce `unknown`; exactly-once external intent delivery cannot be guaranteed |
| Network or app crash | Bounded lifetime, terminal uncertainty, explicit manual retry with new request | Availability is limited; no automatic re-execution of ambiguous actions |
| UI reports false success | Only `handed_off` after intent accepted; no `completed` for Clock intents | Android provides no reliable alarm-creation acknowledgment through this mechanism |
| Cloud tries phone localhost | Phone initiates authenticated outbound relay requests | Foreground polling is a test harness; no reliable unattended background channel yet |
| Unexpected app handler | Fixed allowlist, Android resolver/standard launch mechanisms | The user must trust installed handlers and default-app configuration |
| Secret leakage | No secrets in code, no request-body logging, private runtime paths; Android backups disabled | Logs, crash reports, server backups, and screenshots still need operator review |

## State semantics

`queued` means persisted at the relay. `awaiting_confirmation` means claimed
by the device path; network loss can still prevent the screen from appearing.
`handed_off` means the Android call to start the relevant Activity returned
without a dispatch error. `rejected` means the user declined. `failed` means a
known validation/dispatch failure. `expired` means the queued request timed out
before delivery. `unknown` means the system cannot establish whether execution
occurred, including loss after claim. No current operation emits `completed`.

The protocol favors avoiding duplicate actions over availability. A lost result
is not grounds to execute again. A manual new request must show the uncertainty
to the user first. The relay's idempotency record retention and queue capacity
are part of this guarantee; operators must not delete live state to clear errors.

## Production gates

Before exposing an official remote MCP integration: implement and review the
documented ChatGPT OAuth 2.1 flow or validate an explicitly supported private
transport/authentication combination; enforce resource/audience binding and
PKCE as applicable; deploy HTTPS with trusted certificates; provide rotation,
revocation, rate limits, backup/retention policy, monitoring, and abuse handling.
Do not mistake tunnel authentication for end-user authorization without evidence
from the relevant official transport documentation.

The optional loopback MCP HTTP listener has no client authentication. Other
local processes that can reach it can exercise the adapter's operator authority.
Use it only on a trusted development machine; prefer the stdio adapter. Loopback
binding by itself is not authentication. A restricted private Secure MCP Tunnel
may provide a documented lab transport boundary; its exact access constraints
and untested status are in [the integration assessment](chatgpt-feasibility.md).

Before OS inclusion: choose a narrowly scoped background delivery strategy,
prove Android background-start/lock-screen behavior, make any required
privileged permissions explicit, add SELinux policy only when justified, and
test on the exact pinned OS build. Preserve encryption, verified boot, rollback
protection, and SELinux enforcing. The launcher must retain offline access to
Settings, Clock, system navigation, and recovery controls.
