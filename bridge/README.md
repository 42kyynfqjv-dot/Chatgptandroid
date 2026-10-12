# Archived Python bridge experiment

**This directory is not part of the current Home app runtime or setup.** MCP
is deferred while the project builds native ChatGPT launching, Phone, Messages,
Settings, All apps and optional Quick Settings controls. The current Android
app has no relay configuration/polling UI or command client. It needs no project
server, Plugin, tunnel or pairing credential.

This experiment remains for reproducible protocol/security tests and design
history. It was not deployed and did not demonstrate official ChatGPT Android
integration or physical-device execution. If tools resume, MCP and execution
must run **on the Pixel**, without a project cloud runtime; see
[deferred research](../docs/on-device-mcp.md). Do not deploy this remote
architecture as the product.

## Reproduce archived tests

Tests run a real MCP stdio process against a loopback relay with temporary
SQLite files. They do not connect a phone, change an account or create an
external service. Python 3.12 is required. The complete dependency lock includes
registry SHA-256 hashes.

```sh
cd bridge
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
python -m unittest discover -s tests -v
```

Coverage includes role authentication, strict payload/body limits, HTTPS,
expiry, concurrent delivery, persistence, idempotency, queue bounds, metadata
and SDK initialization/tool calls. Local sockets must be permitted. These
archived component tests do not require MCP account access for current UI work.

## Historical architecture

The single-owner/device experiment combined a Python relay, official MCP Python
SDK adapter, GPT Actions OpenAPI sample, and Android client that polled while
visible and requested approval. That Android client/UI is no longer in the
current app. Simulated acknowledgements never proved physical app launch or
alarm creation.

Separate bearer roles allowed operators to create/read actions and devices to
claim/report bounded results. No route accepted caller-selected devices,
packages, shell, URLs, SMS, telephone calls, account data or file operations.
A stolen bearer compromised its role; this was not multi-tenant identity.

No current setup step asks users to generate those credentials, start a relay,
import an Action or configure a tunnel. Retained deployment samples are
historical fixtures, not production instructions.

## Archived MCP/wire contract

| Tool | Arguments | Historical meaning |
| --- | --- | --- |
| `open_app` | `app`, `idempotency_key` | Queue `chatgpt`, `settings`, `clock`, or `browser` for the old client. |
| `set_alarm` | `hour`, `minute`, `idempotency_key`; optional `label` | Request Clock intent after approval, without alarm-created proof. |
| `get_action_status` | `action_id` | Read recorded queue state. |

Write annotations were client hints, not authorization. The adapter avoided
automatic retries and redirects. The absolute-path `run_mcp.py` launcher was
tested from a different working directory.

Relay routes required role-specific bearer auth. JSON bodies were capped at
4096 bytes; unknown fields/numeric coercion were rejected. Operator requests:

```json
{"action":"open_app","params":{"app":"clock"},"idempotency_key":"a_new_random_key_123456"}
```

```json
{"action":"set_alarm","params":{"hour":7,"minute":30,"label":"Test"},"idempotency_key":"another_random_key_1234"}
```

`POST /v1/actions` created and `GET /v1/actions/{id}` read records with `id`,
`action`, `params`, `status`, numeric UTC Unix `created_at`/`expires_at`, and
nullable `detail`. Alarm time was device-local: hour 0–23, minute 0–59, label
up to 80 characters without ASCII controls. IDs were UUID-validated; keys were
16–80 ASCII letters/digits/`_`/`-`. Changed payload with an existing key
returned 409.

The device used `GET /v1/device/next` to claim once, transactionally changing
`queued` to `awaiting_confirmation` before delivery, and
`POST /v1/device/actions/{id}/result` for bounded results. Lost responses did
not redeliver claims. Identical final reports were accepted; conflicts and
finalizing undelivered records failed.

| State | Historical meaning |
| --- | --- |
| `queued` | Persisted, not delivered. |
| `awaiting_confirmation` | Claimed once; lost response could prevent UI appearing. |
| `handed_off` | Device reported Android accepted an intent; destination state unverified. |
| `rejected` | User declined. |
| `failed` | Known validation/dispatch failure. |
| `expired` | Deadline passed before delivery. |
| `unknown` | Delivered action deadline passed or outcome uncertain; no automatic replay. |

No operation emitted `completed`. Exactly-once external Android effects were
not claimed. The old client rechecked expiry and journaled before dispatch;
lost results did not justify repeating actions. These are historical contract
details, not current launcher behavior.

TTL defaulted to 120 seconds, bounded 10–300. SQLite used `BEGIN IMMEDIATE`,
WAL and `synchronous=FULL`. Caps were 100 pending and 10,000 session records;
records were retained rather than permitting old keys to execute again.
Full/busy database errors did not imply successful creation.

## Archived limitations

- Optional loopback Streamable HTTP has no client auth/OAuth. Processes able to
  reach it can exercise operator authority. Loopback is not authentication;
  do not expose this endpoint.
- OpenAPI uses a reserved nonworking example origin. Actions auth differs from
  MCP Plugin auth; no official-account integration was tested.
- No production pairing, user/device identity, OAuth server, monitoring,
  automatic session rollover or Android background channel was implemented.
- Desktop MCP and queue tests do not establish Android typed or Voice access.

See [historical feasibility](../docs/chatgpt-feasibility.md) and the
[current UI threat model](../docs/threat-model.md). Future tooling requires a
separate review; it is not needed to use the current Home app.
