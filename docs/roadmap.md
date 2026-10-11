# Staged path to a replacement OS

Stages are acceptance gates, not a delivery-date promise. The present cloud
work implements the independently testable parts of stage 0. A working launcher
on stock Android does not satisfy the final OS requirement.

The target is **MCP and device execution on the Pixel**. The cloud server is
for builds, with the local MacBook handling approved USB tests on the dev Pixel.
The server-relay experiment in stage 0 is superseded, not a deployment target.

| Stage | Work | Exit evidence |
|---|---|---|
| 0 — Cloud prototype | Narrow relay, SDK MCP adapter, Android harness, release controls, setup and CI | Local protocol/security tests and actual APK build + lint passed; GitHub-hosted CI not run |
| 1 — On-device MCP proof | Implement a minimal authenticated MCP endpoint on the Pixel; first use a harmless read-only tool | Local protocol test plus a documented connection from official ChatGPT Android to this phone-hosted endpoint; no off-device relay |
| 2 — Dev Pixel actions | With approval, test genuine ChatGPT and the phone-hosted service; add allowlisted app/alarm actions with local confirmation | Actual Android typed and Live tests recorded separately; rejection, expiry, replay, restart and truthful handoff results on the dev Pixel |
| 3 — First OS candidate | Verify upstream tag/manifests, import exact vendor/kernel/firmware set, add independently signed launcher as product app, customize updater identity/URLs and fallback navigation | Reproducible unsigned candidate and signing rehearsal; license review; no security property disabled |
| 4 — Verified boot + OTA proof | With separate device approval, run unlock/wipe/install/relock procedure for exact device/build/key set; upgrade between two signed candidates | Boot with own trusted AVB key; encryption and SELinux enforcing; forward OTA, slot failure/recovery, rollback rejection, compatibility and hardware checklist |
| 5 — Maintained distribution | Background device service only as justified; staged OTA cohorts, release monitoring, emergency security-only path | Repeated timely upstream imports; release ownership/coverage; actual dev Pixel acceptance; recovery and key-backup drill |

Do not proceed to an irreversible device procedure based only on a build passing.
Each approved procedure must name the exact Pixel model, candidate artifact
hashes, expected data loss (unlocking/relocking can wipe), bootloader/rollback
constraints, backup verification, and a compatible recovery image/process.
Recovery should favor a newer fixed build signed by the same keys; an old image
may be blocked by rollback protection. Do not prescribe generic downgrade steps.

The immediate hardware target is the owner's dev Pixel. The primary daily-use
phone remains outside testing unless the owner separately authorizes it.

Remaining choices after component validation: project branding, release domain,
owner/account authentication, supported ChatGPT plan, fleet size, physical-device
test access, signing custodians, and operational update budget. None is silently
replaced with paid infrastructure or a separately billed chatbot API.
