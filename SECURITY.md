# Security and reporting

This repository contains a development prototype, not a supported phone OS
release or an audited remotely administered device service. No physical phone
has been modified or tested by this project yet.

For a suspected vulnerability, use GitHub private vulnerability reporting when
enabled by the repository owner. Do not post credentials, request databases,
personal messages, device identifiers, or signing keys in public issues. Until
private reporting is enabled, contact the owner privately without posting the
exploit or private data publicly. There is no staffed response SLA yet.

Do not expose the loopback MCP development server to the internet. Official
ChatGPT registration needs the documented supported transport and authentication
described in docs/chatgpt-feasibility.md. A working local MCP session does not
prove a working ChatGPT Android connection.

The prototype deliberately limits device actions to a small app allowlist and
Clock alarm handoff. Device approval is required for each remote request.
Successful intent dispatch means `handed_off`; it does not prove an alarm was
saved. Never authorize arbitrary shell, file access, accessibility automation,
SMS, calls, or downloaded code through this bridge.

Release signing and device installation are separate human-controlled gates.
See docs/security-updates.md and docs/threat-model.md.
