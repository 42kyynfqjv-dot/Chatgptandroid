# On-device MCP target

The **Pixel runs the MCP server and Android action executor**. This project
requires no cloud MCP host, remote device relay, or always-on MacBook gateway.
The cloud dev server is for source/build work. The local MacBook transfers
artifacts and supports approved USB installation/testing on the local dev Pixel.

The existing Python MCP/relay implementation and Android relay-polling screen
are an earlier experiment, retained as test/reference code. They do not implement
this target and should not be deployed as the product. No service has been
deployed. The APK built in the initial phase is not an on-device MCP server.

## Next proof

1. Build a minimal authenticated MCP endpoint inside the Android app/service,
   with a harmless read-only test tool. Keep its lifecycle visible and initially
   require the app to be open. A loopback listener alone is not authorization:
   other apps may be able to reach it.
2. Verify its protocol from a local development client. With approval, use the
   MacBook and USB-connected dev Pixel. This proves the endpoint, not integration
   with the official ChatGPT app.
3. Establish a **documented connection from official ChatGPT Android to the
   phone-hosted endpoint**. An actual typed request must return a uniquely
   correlated result without an off-device bridge. This capability has not been
   established; mobile Plugin support alone is insufficient evidence.
4. Once that connection works, add the existing narrow app/alarm actions with
   local approval, validation, replay protection and honest handoff results.
   Test mobile Voice separately. Then integrate the service into the replacement
   OS without weakening verified boot, SELinux or encryption.

Do not invent a ChatGPT localhost setting, proprietary intent, internal API or
Android permission that grants this connection. If the official client cannot
support it, report that limitation before changing the architecture. Do not
silently substitute a cloud relay or separately billed chatbot API.

The modest cloud server can still do component development. Measure its CPU,
RAM and storage before planning a complete OS build; the larger runner profile
is specific to OS compilation and is not a requirement for this phone service.
