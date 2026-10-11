# Contributing

Keep the integration in ordinary apps, narrow services, resource overlays, and
small reviewable patches. A change requiring framework privileges must explain
why a documented unprivileged Android API is insufficient.

Include validation appropriate to the behavior changed. Bridge changes need
authentication, validation, replay, expiry, and truthful-result coverage. Android
changes need a reproducible APK build and lint; physical behavior remains a
separate test gate. OS changes need a pinned release manifest and hardware
validation before promotion. Never label source-only work as a built ROM.

Use the original OpenAI-signed ChatGPT app from its official Google Play listing.
Do not check in its APK, credentials, or extracted app data. Do not implement
undocumented endpoints, token extraction, APK modifications, or UI scraping.

Dependencies should be version-pinned, reviewed, and updated through pull
requests. Record provenance for imported source. Do not run untrusted pull
requests on signing machines or persistent self-hosted Android build runners.

No device unlock, flash, install, wipe, relock, or other physical modification
may be performed without the owner's explicit approval for that procedure.
Paid infrastructure requires a separately approved cost and configuration.
