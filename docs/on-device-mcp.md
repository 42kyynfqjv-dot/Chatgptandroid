# Deferred on-device MCP research

**MCP is deferred and is not a prerequisite for the current Home app.** Current
work is a native Android interface centered on opening official ChatGPT, with
Phone, Messages, Settings, and All apps. Calls, messages, notifications and
system settings remain Android's responsibility. An optional Quick Settings
tile opens controls; it is not an overlay or device-control daemon.

The current APK contains no MCP server, relay client, or remote command queue.
It needs no Plugin, developer-mode entitlement, tunnel, token, or project
server. The earlier Android polling UI is removed from this app. The Python
bridge is an [archived experiment](../bridge/README.md), retained for tests and
design history.

## Constraints if the user reopens this work

The user requires MCP and device execution **on the Pixel**, without a project
cloud runtime, remote device relay, or always-on MacBook gateway. The cloud dev
server is for source/build work; the MacBook supports local development and
approved USB testing. Preserve those boundaries unless the user changes them.

A documented connection from official ChatGPT Android to phone-local MCP has
not been established. Mobile Plugin support does not prove local MCP access.
Reviewed OpenAI documentation describes local MCP apps as desktop capabilities;
documented tunnel release platforms do not establish Android runtime support.
See the [historical assessment](chatgpt-feasibility.md).

If research resumes, the first integration proof would be an actual typed
request from the official Android app invoking a harmless authenticated tool on
the Pixel and returning a uniquely correlated result over a documented
connection. A Mac/USB client proves only the server; Voice needs a separate
test. These are future research conditions, not current installation steps or
Home-app release gates.

Do not invent a ChatGPT localhost setting, proprietary intent, internal API,
or Android permission to obtain that connection. Do not substitute a project
cloud relay or separately billed chatbot API. The official app's own online
service remains separate from our Android UI.
