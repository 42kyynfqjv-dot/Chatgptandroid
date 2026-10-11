# Architecture decisions

## ADR-001: A small GrapheneOS derivative

Recommend the maintained Pixel hardware/security integration of GrapheneOS as
the upstream, subject to the evidence in [the foundation comparison](os-foundation.md).
Our distribution owns its names, signatures, updater endpoints, build records,
and release responsibility. Upstream signed OTA packages cannot update our
modified, differently signed OS. Each upstream release is imported, rebuilt,
validated, and signed by us. Initial changes should be ordinary apps and small
product configuration patches; no broad framework fork is justified yet.

## ADR-002: Preserve the official app boundary

Use the OpenAI-signed app from Google Play. The launcher invokes its ordinary
launcher Activity through Android package resolution and exposes the fixed Play
listing for installation/updates under settings. Keep the full standard Android
Settings app accessible, with Play serving app maintenance rather than a
store-browsing home experience. The Play Store itself remains unmodified and can
show its ordinary UI when opened. Play updates the app independently of OS OTA.
The UI is not embedded, intercepted, scraped, or cloned. No API subscription is
assumed to be interchangeable with the user's ChatGPT subscription.

## ADR-003: MCP and device execution on the Pixel

```mermaid
flowchart LR
    subgraph Pixel
        A[Official ChatGPT Android] -. Documented local connection: unproven .-> B[On-device MCP service: planned]
        B --> C[Local validation and approval]
        C --> D[Allowlisted Android action]
    end
```

There is no project-operated cloud runtime or remote relay in the target.
The existing Python adapter/relay and Android polling screen are an earlier
experiment, not this implementation. No service has been deployed.

The first proof is a harmless read-only tool on a phone-hosted MCP endpoint,
then a documented official ChatGPT Android connection to it. The latter is
**not established** by current tests or mobile Plugin documentation. A Mac/USB
client test does not prove it. See [the on-device plan](on-device-mcp.md).

Android execution and background-activity restrictions still apply. Start with
a visible local service and retain explicit confirmation. Do not work around an
unsupported official-client connection with private APIs or a cloud relay.

## ADR-004: Conservative results and at-most-once attempts

An intent handoff cannot prove downstream completion. Persist the attempt before
dispatch, keep a request journal, and report ambiguity after interruption. Never
automatically retry an ambiguous side effect. The user must approve a new request
if they decide to retry. The narrow schema and local confirmation remain in force
even if a future model or client claims a request is already authorized.

## ADR-005: Separate compilation, physical validation, and signing

The dev server compiles components and OS candidates. The owner's **dev Pixel**
performs hardware and official-app validation after approval. An isolated signing
process holds production keys. KVM/emulation is optional and unnecessary for the
physical-device workflow. Public pull-request CI never receives production
credentials or access to a signing host.

The server is in the cloud; the MacBook and Pixel are local. Download verified
build artifacts to the MacBook for approved USB installation/testing on the
Pixel. MCP and device actions run on the phone. The cloud server is modest;
measure its capacity rather than assume it can compile the full OS. It does
not need the full-OS runner specification for ordinary component development.
