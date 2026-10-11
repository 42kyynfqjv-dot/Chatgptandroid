# Pixel action bridge prototype

**Superseded transport experiment.** The chosen product requires its MCP server
and action executor to run on the Pixel, with no cloud relay. This Python
implementation is retained as protocol/security reference code; do not deploy
it as the product. See [the on-device plan](../docs/on-device-mcp.md). Its passing
tests do not establish that the phone hosts MCP or that ChatGPT can connect.

This working Python prototype queues two explicitly confirmed Android intents:
`open_app` and `set_alarm`. It provides a durable HTTPS relay, an official MCP
Python SDK adapter, and an operator-only GPT Actions OpenAPI schema. It is a
single-owner, single-device bridge. No route accepts a device ID, package name,
shell command, browser URL, SMS, telephone call, account data, or file operation.

The tests exercise a real MCP stdio process talking to a local relay. They do
**not** establish that the official ChatGPT Android app is connected, that GPT
Actions or Plugins are available to a particular account, or that a physical
phone dispatched an intent. The Android harness and the official ChatGPT app
are separate apps. The harness must be visible to poll and ask for approval.

## Install and verify

Use Python 3.12 in a fresh environment. `requirements.lock` pins the complete
dependency closure used for the included tests, with registry SHA-256 hashes.
It targets Python 3.12; other Python versions are not supported by this project.

```sh
cd bridge
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
python -m unittest discover -s tests -v
```

The 16 tests include wrong-role authentication, rejected payloads, body limits,
HTTPS enforcement, expiration, concurrent delivery, restart persistence,
idempotency, queue bounds, schema metadata, and actual MCP initialization and
tool calls through stdio. They use only loopback sockets and temporary SQLite
files. Restricted sandboxes must permit local sockets. `pytest` can also collect
these standard-library `unittest` tests; it is not required or installed by the
lock file.

## Run a private relay behind HTTPS

Generate two different 32-byte random credentials into environment variables in
the relay's private service environment. They are not command-line arguments:

```sh
export PIXEL_OPERATOR_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export PIXEL_DEVICE_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export PIXEL_DATABASE="$PWD/state/actions.sqlite3"
export PIXEL_TTL_SECONDS=120
python -m uvicorn pixel_bridge.relay:create_app --factory \
  --host 127.0.0.1 --port 8765 --workers 1 \
  --proxy-headers --forwarded-allow-ips=127.0.0.1 --no-access-log
```

Preserve these credentials securely across relay restarts for the same session.
Use your service manager's secret environment injection; never commit them or
put them in the OpenAPI file, URL, logs, screenshots, or a model prompt. The
operator credential belongs only in the MCP process environment or the GPT
Actions API-key configuration. Provision the different device credential to
the Android harness using its setup screen. Never give that credential to a
model or an API client. Both are bearer credentials with no user/device identity
attestation. A stolen credential compromises its role; this is not multi-tenant
authorization.

Terminate TLS on the same host with a reverse proxy, such as the configuration
in `Caddyfile.example`, at an HTTPS origin reachable by both the phone and the
operator client. Configure valid DNS and a trusted certificate. Keep port 8765
bound to loopback and unreachable externally. Trust forwarded headers only
from that loopback proxy. The application rejects HTTP unless a deliberate local
development override is used. Do not enable `PIXEL_ALLOW_LOOPBACK_HTTP` on a
public deployment. No hosting service or public endpoint is provisioned here.

For a loopback-only development relay, set `PIXEL_ALLOW_LOOPBACK_HTTP=1` and run
the same command with `--no-proxy-headers`. The override additionally requires
the connecting peer to be a loopback IP. This mode is for development tools on
the same machine; the phone still requires a reachable HTTPS deployment. Android
`localhost` means the phone, not your workstation or the ChatGPT cloud.

## MCP adapter

Set only the operator token and the actual HTTPS origin in the adapter process:

```sh
export PIXEL_RELAY_URL=https://your-relay.example
# Supply PIXEL_OPERATOR_TOKEN through the MCP client's private environment.
python -m pixel_bridge.mcp_server
```

Configure a local MCP-capable client with this module command, the `bridge/`
working directory, and private environment variables. It uses the official
`mcp` package's stdio transport and exposes:

| Tool | Required arguments | Meaning |
| --- | --- | --- |
| `open_app` | `app`, `idempotency_key` | Queue one of `chatgpt`, `settings`, `clock`, `browser` |
| `set_alarm` | `hour`, `minute`, `idempotency_key`; optional `label` | Request Clock to show or set an alarm in device-local time |
| `get_action_status` | `action_id` | Read the recorded lifecycle status |

For a client or tunnel that starts commands from an arbitrary working directory,
use absolute paths to the environment's Python executable and the source-tree
launcher:

```sh
/absolute/path/bridge/.venv/bin/python /absolute/path/bridge/run_mcp.py
```

The launcher adds the bridge source directory to Python's import path and writes
no startup text to stdout. No editable
package installation is required. The real SDK stdio test starts this launcher
from the system temporary directory.

Writes have MCP annotations `readOnlyHint=false`, `idempotentHint=true` and
`openWorldHint=true`; these are client hints, not an authorization boundary.
There is no automatic network retry and HTTP redirects are not followed.
Every call still needs visible approval in the Android harness.

For SDK transport development only, `--transport streamable-http` serves
`http://127.0.0.1:8766/mcp`. **This local endpoint has no OAuth or HTTP client
authentication. Any trusted-machine process that can reach it can exercise the
operator credential. Never expose it directly or through a public reverse
proxy.** A supported Secure MCP Tunnel or audited OAuth 2.1 deployment remains
a separate integration step; it is not implemented or tested here. A stdio
configuration cannot be pasted into the official Android app and treated as an
installed Plugin. See the repository's integration notes for current official
ChatGPT feature and authentication requirements.

## GPT Actions alternative

`actions.openapi.json` is a sample with the reserved, nonworking origin
`https://relay.example.invalid`. Generate a schema for a real HTTPS origin:

```sh
python -m pixel_bridge.export_openapi --origin https://your-relay.example > actions.openapi.json
```

In an account with GPT Actions access, import the schema and configure **API
Key → Bearer** with the session's operator credential in the product's secret
field. Do not place the key in the schema. The schema exposes only action
creation and status lookup. `requestDeviceAction` explicitly sets
`x-openai-isConsequential: true` so a compatible client asks for confirmation;
the phone's own confirmation remains mandatory regardless of client behavior.
Actions API keys and remote MCP Plugin OAuth are different integrations. This
repository has not performed a real custom-GPT or official-app end-to-end test.

## Exact wire contract

All routes require `Authorization: Bearer <role-specific token>`. JSON request
bodies are limited to 4096 bytes; unknown fields and coercion of alarm numbers
are rejected. There are no caller-selected routing destinations.

Operator creation, `POST /v1/actions`:

```json
{"action":"open_app","params":{"app":"clock"},"idempotency_key":"a_new_random_key_123456"}
```

or:

```json
{"action":"set_alarm","params":{"hour":7,"minute":30,"label":"Wake up"},"idempotency_key":"another_random_key_1234"}
```

An idempotency key must contain 16–80 ASCII letters, digits, `_`, or `-`. Generate
a new random key only for a new user-authorized action. Reuse the identical key
and payload to recover a lost creation response. Reusing a key with a different
payload returns 409. Idempotency records are retained for the whole session,
including expired and rejected actions.

Creation and operator `GET /v1/actions/{id}` return:

```json
{
  "id":"23cce2d6-89bc-4f3f-b5b5-7b211239ba94",
  "action":"open_app",
  "params":{"app":"clock"},
  "status":"queued",
  "created_at":1791763200.0,
  "expires_at":1791763320.0,
  "detail":null
}
```

Timestamps are UTC Unix seconds as JSON numbers, not ISO strings. Alarm hour and
minute use the phone's local clock and are not these UTC timestamps. Valid
hours are integers 0–23, minutes 0–59, and labels are at most 80 characters with
no ASCII control characters. A malformed UUID path is rejected.

The **device credential** accesses:

* `GET /v1/device/next` → `{"action":null}` or `{"action":<Action>}`. A SQLite
  transaction changes `queued` to `awaiting_confirmation` before sending the
  response. A claim is delivered at most once, including if the response is lost.
* `POST /v1/device/actions/{id}/result` with
  `{"status":"handed_off","detail":"Intent dispatched"}` → `<Action>`.
  Allowed reports are `handed_off`, `rejected`, `failed`, and `unknown`; detail
  has at most 240 characters and no ASCII controls. Identical final reports are
  accepted, conflicting reports return 409, and an undelivered action cannot be
  finalized by the device.

The Android harness must check `expires_at` again immediately before dispatch,
record the action ID durably before launching an intent, and never dispatch it
twice after a crash or uncertain report. Server and device clocks must be
reasonably synchronized. The relay cannot transact atomically with Android;
exactly-once effects are deliberately not claimed.

| Status | Meaning |
| --- | --- |
| `queued` | Stored, not delivered |
| `awaiting_confirmation` | Claimed once; may be waiting for phone approval |
| `handed_off` | Device reports `startActivity` accepted an intent, without verifying the resulting app state |
| `rejected` | User declined |
| `failed` | Device reports a known dispatch failure |
| `expired` | Deadline passed before delivery; never delivered afterward |
| `unknown` | Delivered action exceeded deadline or its outcome is uncertain; inspect the phone, never automatically replay |

TTL is server-owned, defaults to 120 seconds, and is bounded to 10–300 seconds.
Deadline transitions are evaluated transactionally when the queue is accessed.
No background worker replays actions. A late result after the deadline returns
409 and leaves the action `unknown`; a reported intent is never `completed`.
Clock may display or create an alarm depending on the handler; inspect and
confirm the desired time there. App launches may still be blocked or interrupted
by Android.

## Storage and session limits

SQLite uses `BEGIN IMMEDIATE`, WAL, and `synchronous=FULL`; state survives a
process restart. Keep the database and its directory private and do not share
them between unrelated owners. The pending queue is capped at 100 records
(429), and total session records at 10,000 (507). Records are not evicted to
make old idempotency keys executable again. At the session limit, stop both
clients, archive the database securely, rotate **both** credentials, and start a
fresh database and session. Never delete state while reusing the old credentials.
This prototype includes no remote delete, account provisioning, device discovery,
automatic session rollover, OAuth server, billing, or production monitoring.

Database-full or busy failures return 503 without implying whether a request
was stored. Recover with the original key. At-most-once delivery favors avoiding
duplicate effects over eventual execution: a network loss after claim can lose
the action until it becomes `unknown`. Inspect the phone before authorizing any
new request with a new key.
