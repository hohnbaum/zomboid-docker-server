# Project Zomboid Docker migration plan

Updated: 2026-10-02, Europe/Berlin. **Phase 1 completed; implementation authorized.** Keep snapshot data immutable and never connect to production. Imported-world starts require exact 42.21.0. Original discovery involved no remote Git operations. Publication of the separate public project is now authorized after audit.

## Current architecture and verified evidence

Windows `C:\PZ` hosts fixed instance szs, bundled Java, SteamCMD, PowerShell operations, file intent/maintenance locks, directory snapshots, two-minute health CSV and guild Discord bot. Four Windows task exports cover watchdog, maintenance, logger and bot. Main manager owns safe save/quit/start and fresh-start pending completion. Snapshot ops HEAD is <private-source-commit>, matches handoff, tracked tree clean, copied origin/main has no divergence.

Current config derives 111 Workshop items, 137 Mods, singular INI Map with one entry. Console version is 42.21.0; source update policy is public/anonymous app 380870; Workshop namespace 108600. There is no active pending/desired flag. Current source already has schema-v2 exact-array guards and strict schema-v1 replay fallback. Extra persistence includes Lua mod records and options.ini outside the old ops backup's three-folder coverage. Operational rotating backups, app/Workshop cache, SteamCMD and Discord token are absent from the snapshot. Six game-native historical ZIP backups are included.

Read the complete evidence and chosen design:

- [CURRENT-SYSTEM.md](docs/CURRENT-SYSTEM.md): script responsibilities, paths, state, tasks, persistence, credentials and discrepancies.
- [ARCHITECTURE.md](docs/ARCHITECTURE.md): services, volumes, networks, control, health, scheduling and behavior changes.
- [DATA-MIGRATION.md](docs/DATA-MIGRATION.md): complete copy disposition, import/backup/restore contracts and smoke-test gates.
- [MOD-PLAN-LIFECYCLE.md](docs/MOD-PLAN-LIFECYCLE.md): exact order, legacy compatibility, config commit authority and recovery.

## Target architecture

Three Linux services: pz-server owns Linux installation and a controlled Java child; pz-ops owns policy, desired state, health, backups/config/mod jobs and schedules; optional pz-discord preserves existing commands through private authenticated ops API. A restricted Unix socket lets ops ask the server agent for typed actions/telemetry without Docker socket access. Named Linux volumes hold app, nested app-relative Workshop content, cachedir, ops state/control, backups and logs. Only game UDP ports publish; no public RCON or ops API. Nonroot runtime, private file secrets, no copied Windows binaries/venv.

Docker restarts control services; persisted desired-running decides whether ops launches Java. Imported data starts with desired=false; existing project boot preserves intent. Add distinct operator maintenance without confusing it with operation locking. Preserve no degraded-process autorestart and player/unknown-count shutdown refusal. Prefer packaged Linux launcher, Python operational components and small lifecycle integration scripts.

## Phases and exit gates

| Phase | Work | Required result before advancing |
| --- | --- | --- |
| 1: discovery | Inspect source and create these five documents | Evidence/discrepancies recorded, proposed architecture and decision gates reviewable; **current deliverable** |
| 2: vanilla Linux container | Images/Compose/secrets/example/ignore/wrappers, minimal server agent/readiness; no production data | Linux engine accessible; SteamCMD dedicated package and selected build verified; named-volume vanilla server READY and actual local client join; restarts retain app install |
| 3: imported copy | Manifest-based import into new Linux target, preserve active data/private archives | Byte/count/hash verification; matching Linux version; complete configured Workshop download; account/world/mod state loads; logs reviewed; READY and client join/rejoin; pristine import retained |
| 4: operations | CLI/API jobs, locks/intent/maintenance, schedules, update/Workshop, backup/restore, config/mod lifecycle | Unit/failure tests pass; graceful refusal and offline semantics match source; no exposed RCON/API; restored test backup reaches READY |
| 5: Discord | Port six commands, pagination/role rules, configured host endpoints, durable progress | Test guild or isolated bot credentials supplied; no duplicate production bot; commands and authorization verified without raw secrets/errors |
| 6: recovery/handoff | Crash/intent/restart/mod/readiness/RCON/restore tests; final docs/export | Recorded failure matrix, client recovery, complete restore smoke test; README/LINUX-HANDOFF.md give repeatable Linux setup |

Phase 2 will implement only minimal ops control needed for vanilla start/status; full operational port stays phase 4. Each phase ends with files changed, exact command categories, test results, blockers and next step. Environment-blocked integration gates remain explicitly incomplete; static/unit success never substitutes for a game READY/restore test. Production transfer requires a later explicit production instruction.

## Decisions and open questions

| Question | Proposed default / evidence | When required |
| --- | --- | --- |
| Initial branch/build | Preserve source public policy; verify downloaded Linux 42.21.0 before world use. [42.21 reached Stable September 28](https://projectzomboid.com/blog/news/2026/09/42-21-stable-released/). App manifest absent; no depot pin proven. | Phase 2/3 gate; do not silently import into different build |
| Docker readiness | CLI 29.8.0/Compose v5.5.1 installed, desktop-linux engine pipe absent even outside sandbox. WSL executable exists, backend not verified. | Running Linux engine prerequisite for phase 2; no software installation/start performed |
| Architecture/resources | Linux amd64 test target, source 6 GiB Java heap plus overhead; use named volumes for live data | Confirm available Docker Desktop resources before download/start; final Linux CPU/RAM/storage later |
| Advertised endpoints | Configured host/LAN/VPN/public addresses for `/pzip`; never advertise container IP | Operator values needed for client/Discord tests and final host; no production discovery connection |
| Import activation | New target desired=false, pristine copy retained, explicit test start | Phase 3; no import performed now |
| Maintenance/autoupdate | Preserve six-hour build check/hourly safe maintenance; zero-player refusal; operator maintenance added separately | Implement/test in phase 4; upstream-Workshop-only autorestart stays off unless later requested |
| Mod provenance | Emit v2; confined explicit v1 importer only for demonstrable legacy record; preserve sequential apply via audited supersession | Phase 4; current archived v1 must not become active |
| Backups/data | Include Lua/options and all approved persistence; archive historical 6.10 GiB game ZIPs separately | Phase 3/4; no deleting existing ZIPs or source data |
| Config hashing | Linux ordinal sort and explicit active szs config scope; new post-start baseline, preserve Windows history privately | Phase 4; document deliberate difference from old all-file/culture hash |
| Emergency shutdown | Preserve source's refusal/no kill; emergency force termination separate and explicit if later implemented | No need to choose for discovery; ordinary Force remains occupied graceful permission |
| Discord test destination | Bot disabled by default; use test guild/bot profile with separately supplied token | Phase 5; snapshot lacks token, no messages sent |
| Snapshot consistency | Offline/shutdown evidence is encouraging, but export atomicity and SQLite integrity unproved | Phase 3: validate copies and preserve originals; obtain later authorized consistent export only if evidence requires |
| Exact Workshop refresh | Prefer PZ Linux startup downloader; timestamp/API comparison is advisory; validate manifests/logs | Phase 2/3/4 tests; do not promise historical mod content or anonymous SteamCMD item download availability |

No user decision is required to finish this discovery deliverable. Before actual implementation work, settle the desired build policy, local resources/port bindings and the proposed control-agent/volume design; the defaults above make those choices concrete. Discord endpoints/token and final-host specifics can wait until their phases. Steam/Linux installer verification can be performed in a disposable empty phase-2 project, without importing the world.

## Risks and mitigations

| Risk | Mitigation / acceptance evidence |
| --- | --- |
| Save upgrade or version mismatch | Verify version before imported start; immutable source and pristine copy; never downgrade silently |
| Windows case behavior hides broken mods | Live app/Workshop/data on Linux volumes, preserve case, inspect exact resource paths and join with matching client |
| Missing outside-save mod data | Explicit per-path import manifest; Lua/options included; unknown entries preserved/classified |
| Snapshot or DB inconsistency | Read-only source; hash comparisons; SQLite checks on copies; complete stopped-state backups and restored game proof |
| Historical logs already noisy | Compare Windows baseline (many Workshop/media missing-file errors) with Linux logs; zero ERROR keywords is not the only readiness criterion |
| Docker policy resurrects intentional stop | Idle server agent; persisted intent and locked reconciliation; test false through service restart |
| Degraded game killed while players online | No degraded-process autorestart; RCON player uncertainty fails safe; preserve graceful stop |
| Mod plan acknowledged by unrelated config hash | Exact ordered arrays, immutable plan, fresh generation, internal completion authority; regression/fault tests |
| Crash between INI/pending/baseline writes | Atomic single-file writes plus recoverable journal; ambiguous recovery inhibits launch/acknowledgement |
| Uncontrolled Docker/API authority | No Docker socket, typed Unix control, private authenticated ops API, nonroot and scoped volumes |
| Credentials leak through logs or Git | No full configs/DB rows/raw manager tails, fixture secret tests, ignore runtime/archives/.env/secrets before any staging |
| Steam update queries race installs | Central server-agent serialization, bounded remote-query cache, no bot SteamCMD process |
| Workshop timestamp detection misses changes/outages | Expose Unknown and metadata freshness; validate downloaded items on fresh start; do not promise exact historic reproducibility |
| Backup retention destroys useful history | Preserve recent/weekly rules, valid completion markers, protected/import archives outside rotating catalog |
| Disk growth/high file count | Capacity check for install/staging/backups; separate game-native ZIPs; track >138k world files without unsafe flattening |
| Discord timeout aborts maintenance | Durable ops job IDs and progress polling; client disconnection cannot kill an executing job |
| Test ports or guild conflict | Unique Compose project/volumes, loopback ports by default, bot off, no unrelated service stops |

## Acceptance criteria

1. Only Docker source/project docs are tracked; no source-snapshot, .env, credentials, worlds, backups, app/Workshop, caches/log/state/pending. Git initialization, if used later, is confined to docker; no push.
2. Same Compose project works on Docker Desktop Linux/WSL2 and ordinary Linux with documented host binding/advertised endpoints/resource adjustments only.
3. Linux SteamCMD installs the dedicated package freshly; no Windows app/Workshop/venv copied. Install volume persists across restarts; container reboot does not run app_update by default.
4. Vanilla test first, then explicitly imported copy: world/account/player/vehicle/mod data verified; ordered INI arrays preserved; logs reviewed; READY plus actual client play/load/rejoin.
5. Only configured game UDP host ports publish. RCON and ops API stay private and API requests authenticated. No Docker socket/privileged dependency.
6. Simple Windows/Linux wrappers cover status, health, logs, players/save where useful, start/stop/restart/update/workshop-update/backup/restore/config-state/apply-mod-plan/maintenance. Output distinguishes process, playable readiness, desired state and reasons.
7. Offline intent survives Docker/service restart. Absent desired=true game recovers; degraded present game is not automatically restarted. Startup timeout leaves pending and existing child intact unless explicitly handled.
8. Player refusal, unknown-count refusal and graceful save/quit/termination remain; offline update stays offline. Safety backup precedes changed-config/update load.
9. Pending schema v2 requires exact ordered WorkshopItems/Mods/Maps and unchanged plan/record authority; unrelated startup rewrites pass; public config commit cannot override pending. Legacy ambiguous state fails safe.
10. Full persistent backups use completed catalog/retention; safe explicit restore works; a restored disposable server reaches READY and client verifies state. Partial snapshots never count as successful backups.
11. Useful two-minute telemetry and hourly/five-minute automation persist without Windows task infrastructure. UTC JSONL and catalog age calculations are documented changes.
12. Existing `/pzstatus`, `/pzinfo`, `/pzmods`, `/pzip`, `/pzhealth`, `/pzrestart` ported with role/zero-player policy and durable progress. No unimplemented stats/events features represented as existing.
13. Final README and LINUX-HANDOFF.md cover install, private config/secrets, import, lifecycle, updates, backups/restore, Discord, health/troubleshooting, moving hosts and remaining limitations. Handoff includes tested archive/manifest and operator-created secrets separately.

## Test strategy

Unit tests use synthetic fixtures and temporary directories, with no Steam download/live game. Cover INI byte-preserving edits, ordered arrays, plan validation/deltas/anchors, exact v2, safe v1 replay/hash relocation, config-state/pending exclusion, locked intent and maintenance, backup catalog/retention/metadata/hashes, traversal/path safety, API action/auth constraints and redacted output. Crash-boundary tests model apply and acknowledgement recovery. No test writes to source-snapshot.

Integration tests run a unique Linux Compose project, empty data first then a new imported copy. Record Linux version/app manifest, Workshop item evidence, process/UDP/RCON, host publication and client join. Restore smoke steps are in DATA-MIGRATION.md. Test failed API/update queries without misclassifying Unknown as Current; verify normal reboot avoids app update while documenting PZ startup Workshop refresh.

| Failure scenario | Expected result |
| --- | --- |
| Absent Java, desired=true | DOWN_UNEXPECTED then safe new start, subject to lock/recovery checks |
| Intentional stop + service restart | OFFLINE_EXPECTED, agent healthy, Java remains stopped |
| Maintenance mode | MAINTENANCE, auto lifecycle deferred, owner/manual exit validated |
| Agent/ops container restart | Reconcile same child/intent; no duplicate game, install or stale PID acknowledgement |
| Host/Docker restart simulation | Restart only this test project's services; intent retained; do not restart host engine or unrelated projects |
| RCON unavailable | STARTING_OR_DEGRADED with unknown players; shutdown/automatic restart refused |
| UDP/process present but not RCON-ready | No READY/acknowledgement; reasons retained |
| Mod update/pending | Safety snapshot, fresh start, exact lists and evidence; pending retained on failure |
| Malformed plan/tampered pending | Fail before writes/stop; unchanged target and retained evidence |
| Backup/restore failure | No published complete marker for failed backup; target not partially replaced/started |
| Client disconnects mid-ops job | Job continues independently; reconnect/poll operation ID |

## Phase-1 execution record

Changed files: only PLAN.md and the four linked design documents under docker/docs. No implementation, secrets, source copies, Git initialization or test runtime added.

Commands/checks: `rg --files`/read-only PowerShell Get-Content and Get-ChildItem; Python stdlib recursive inventories/byte-format and safe-key parsing, ZIP central-directory listings and AST parse; read-only immutable SQLite table-name inspection; command-scoped safe-directory `git --no-optional-locks status`, `log`, `ls-files`, `rev-parse`, `rev-list`; `docker version`, `docker compose version`, `docker info --format '{{.OSType}}'` (including approved read-only outside-sandbox checks); official developer/Valve web references for release and Workshop semantics. Source fingerprint recomputed with PowerShell sorting and compared without printing credential values. No source management script or exported task was executed.

Results: source bot AST parses; tracked ops tree clean; commit metadata agrees; latest nine config history files match current bytes; config and Workshop baselines match source algorithms; ports/counts/encoding derived. Docker client/Compose found but Linux engine unavailable, so container OSType, image builds, SteamCMD installation, empty/imported server readiness, client play, recovery and restore are **not tested**. Source scripts/tests were not dynamically run because they hardcode C:\PZ and some create files even in reporting paths. No unit tests created in discovery; requested automated suite starts with implementation.

Document validation passed: exactly five Markdown deliverables, valid local links, UTF-8/LF formatting with final newlines, and no occurrences of checked private source credential values. Twenty-two source SHA256 fingerprints (all operations scripts/launchers/bot/README, Git index/HEAD, state JSON, active INI/sandbox and health CSV) remained unchanged across document creation. The copied ops tracked tree remains clean. These checks are not an exhaustive hash comparison of every world file; all mutation commands were confined to the five Docker documents.

Unresolved: runtime Linux package/build confirmation, available Docker resources, future downloaded mod compatibility, source export consistency/DB integrity, configured new-host advertised endpoints and later isolated Discord credentials. Next recommended step is phase 2 after review of these documents and availability of a running Docker Desktop Linux engine, using only a fresh vanilla test project.
