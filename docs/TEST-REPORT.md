# Implementation and test report

Evidence recorded on 2026-10-02. This report distinguishes synthetic checks,
running Linux server checks, private data verification and outstanding acceptance.
It contains no world files, credentials, operator identities or deployment addresses.

## Result

The portable Compose implementation, host commands, restricted agent, operations
service, optional Discord adapter, migration, backup/restore and CI are implemented.
The Linux empty-world and disposable restored-world runtime checks passed.
The private source world is imported and has a verified protected pristine backup.
Its runtime integration is **not completed because of host memory headroom**.
The exact required PZ version is available; there is no version mismatch blocker.

Human client acceptance and live Discord authentication remain outstanding.
GitHub publication requires a user-provided installation/authentication route;
GitHub CLI is absent and no public repository was created during this run.

## Local Git delivery

The independent public-code repository uses branch main. Seven logical commits
cover the delivered implementation and final documentation:

| Commit | Change |
| --- | --- |
| 85a5e80 | Public Compose scaffolding and sanitized discovery baseline |
| aaa151a | Restricted Linux agent and durable lifecycle operations |
| 9b4d806 | Offline guards, source transfer and pending provenance recovery |
| b3662e4 | Optional Discord adapter, synthetic failure tests and CI |
| 27b6b57 | Credential filtering, interrupted installation and intent guards |
| e24f333 | Copied restore verification and durable staging |
| Final documentation commit | Completed evidence, limitations and operator documentation |

The final working tree is clean. Runtime data and private deployment artifacts
are ignored and untracked. There is no GitHub remote or public URL yet.

## Environment and version

| Measurement | Observed value |
| --- | --- |
| Host | Windows 11, 31.92 GiB visible RAM |
| Docker | Desktop 4.91.0, Engine 29.8.0, Linux amd64, WSL2 |
| Compose | 5.5.1 |
| Docker capacity | Approximately 15.6 GiB RAM, 12 CPUs |
| WSL kernel | 6.6.87.2 |
| PZ | 42.21.0, Steam app 380870, build 25485538 |
| Packaged Java | Zulu 25.0.1+8 LTS |
| Tested disposable heap | Xms2g / Xmx2g through ProjectZomboid64.json |
| Imported-world target heap | Xms6g / Xmx6g, retained unchanged |

Linux SteamCMD installation succeeded using anonymous login and a Linux persistent
app volume. The packaged start-server.sh/native embedded JVM launcher was used.
Its launcher SHA-256 was
`9bfcb6a6367e4a6e833680ce09a373ee8ac930f1bd6fb1d8085bbe20cb725957`.
Version evidence came from the running Linux launcher and is tied to this build.
Windows executables, Java, Workshop cache and Python environments were not copied.

Host free RAM fell below 1 GiB during large transfer work and recovered to about
7 GiB after it finished; the final quiet reading was 6.27 GiB. Docker guest
MemAvailable was about 14 GiB, but that does
not supply physical Windows headroom for a 6 GiB heap plus native memory. The
imported game was not started. Final free Windows disk was 244.56 GiB;
the guest filesystem reported a different, larger virtual capacity.

## Automated checks

| Check | Result |
| --- | --- |
| Linux unittest suite | 96 tests, PASS, no skips |
| Windows unittest suite | 96 tests, PASS, five skips |
| Windows skips | Three optional Discord dependency tests, Linux case-collision fixture, symlink privilege fixture |
| Python compilation | PASS for ops, server, Discord, scripts and tests |
| Resolved Compose boundary assertions | PASS |
| Public staged/tracked and complete Git history audit | PASS |

The suite covers INI byte preservation, exact ordered mod arrays, Maps, duplicates,
remove-before-add and anchors, frozen schema-2 provenance, legacy decoded-text
hash/replay, ambiguous recovery, every apply/ack publication boundary, pending
tampering, backup inventory/SQLite/retention, coherent pending restore, marker
absence, replacement confirmation, tar traversal/link/case safety, live kernel
guards, readiness, unknown/occupied players, desired state and maintenance,
interrupted jobs, API authentication and action allowlists, disconnected clients,
redaction and public-tree secret fixtures. Tests use synthetic data only.

## Running PZ checks

| Scenario | Result and limit |
| --- | --- |
| Empty Linux world start | READY: owned game process, both UDP sockets and authenticated RCON players=0 |
| Empty world stop | Graceful save/quit completed; desired=false persisted |
| Intentional stop plus control-service restart | Remained OFFLINE_EXPECTED without a game child |
| desired=true plus service restart | Reconciliation eventually started a fresh READY child; Steam app was not updated |
| Temporary RCON-port failure in disposable copied config | STARTING_OR_DEGRADED with UDP still present and players unknown; no automatic kill/restart; restoring config returned READY with same generation |
| Explicit offline update | Completed safety backup and Steam installation; same build; desired=false and game remained stopped |
| Game-log redaction | Verified configured game, RCON and bootstrap secrets absent from saved filtered game output after a new READY start |

The service-restart test encountered an initial AGENT_UNAVAILABLE job during
startup ordering. A later five-minute reconciliation succeeded. This is eventual
recovery, not an instantaneous restart guarantee. No job was interrupted to hide
the failure. Vanilla startup emitted existing model/room/zone diagnostics; READY
is not a claim that the game produced no warnings.

The native JVM's RSS was approximately 2.9 GiB with a 2 GiB heap. Container cgroup
memory included additional memory and cache. Neither is labeled host RAM.

## Source import and private backup

The stopped private instance had 138,549 files and 7,688,133,573 bytes, including
historical native archives. Native Windows hashing and tar transfer avoided very
slow per-file Windows/WSL crossings. The final original-source inventory check
after Linux import matched every file's SHA-256 and size.

The active import copied 138,416 files: four active server configuration files,
the complete Multiplayer world, account database, persistent Lua data including
Skill Recovery Journal and stats, and options.ini. Historical/other-instance
files were retained in a protected private reference, not activated as live data.
Three copied SQLite databases passed quick_check. No archived pending record was
implicitly activated. Imported intent remained false.

The pristine protected backup completed at 20:23:37 UTC with 138,417 files,
1,071,275,305 bytes, three checked databases and a verified manifest. The extra
file is migration-gate metadata. This backup contains active persistence and
coherent state, excludes historical native ZIPs and runtime logs, and is excluded
from rotating retention. Backup-age telemetry uses the common rotating completed
catalog; it does not count the protected pristine/reference archives as a new
operational backup.

An additional 31-file critical source fingerprint comparison passed, covering
ops, bot, active/reference config, Git/state and health evidence. The original
Windows ops repository was not reused for the public repository. No production
server or SSH connection was used.

## Workshop and mod evidence

All configured 111 Workshop IDs were derived from the private active INI and
downloaded through anonymous Linux SteamCMD to the persistent Linux Workshop
volume. Download success and content directories were recorded per ID privately:
111 downloaded, 111 present, zero unresolved download failures.

The agent's independent manifest/remote timestamp comparison at 20:43 UTC reported
111 Current, zero Update, zero Missing and zero Unknown. A case-sensitive static
mod.info inventory found exact definitions for all 137 configured mod IDs, with
zero unresolved IDs. IDs/order and the one configured Map were preserved.

These checks establish downloaded content and mod ID definitions. They do not
establish successful imported-world mod loading, case-sensitive media references,
Lua or gameplay correctness. Linux runtime log comparison against the noisy
Windows baseline and representative vehicle/item/UI checks await the 6 GiB run
and a human client. Full per-ID evidence stays in private logs, not Git.

## Backup and restore smoke

The disposable world reached READY, stopped gracefully and produced a full
41-file stopped backup. Its verified private gzip export was 814,673 bytes, SHA-256
`150ef5218c929487476e3bbb76b487c5fabf21ab760e0b72baf186b433956410`.
An initial independent target restored it and reached READY.

The ordered smoke test was then completed explicitly: a harmless marker was added
to the stopped disposable source after backup; the original archive was restored
to another new target; archive manifest and databases were validated; the marker
was absent; intent was false; and a deliberate start reached READY at 20:45:42 UTC.
Both UDP sockets and authenticated zero-player RCON were observed. It was then
gracefully stopped. A tar round trip alone is not the basis of this result.

The private imported-world pristine export is 98,061,552 bytes with SHA-256
`493084c2ee3ed4243485107114c660cb66039c4af8b1dddc2b6625c3126ee74d`.
It was restored into a new independent Linux data/state/backup target. All
138,417 archived files passed archive and copied-stage hash/inventory checks,
SQLite validation and publication at 20:57 UTC. The restored controller reported
OFFLINE_EXPECTED, desired=false, no child, 111 Workshop IDs and 137 mods. Its
whole-config baseline is correctly missing until the first healthy start.
Imported-world runtime and client restore acceptance remain outstanding despite
this verified data restore.

## Fault evidence and remaining live limits

| Fault | Exercised behavior |
| --- | --- |
| Startup readiness timeout | Synthetic: child retained, no kill |
| Unknown/occupied players | Synthetic refusals, including force with unknown state; refused restart preserves intent |
| Missing UDP or RCON | Synthetic UDP and live RCON degradation; no automatic restart |
| Malformed/tampered pending | Synthetic fixed errors and unchanged authoritative state |
| Interrupted apply/ack | Synthetic publication-boundary recovery; ambiguous/superseded generation refused |
| Backup failure | Synthetic: no complete publication |
| Restore corrupt manifest/data/control paths or copied staging data | Synthetic: target unchanged before publication |
| Interrupted update/install | Synthetic: stopped state; install marker blocks start/version; explicit installer required |
| Workshop/build API failure | Synthetic: Unknown/unavailable, never silently Current |
| API/Discord client disconnect | Synthetic: durable job continues independently |
| Ops restart with queued/running job | Synthetic: interrupted record, false intent and explicit recovery; no blind replay |

Crash/power-loss behavior was not physically induced on the host. Linux file and
directory fsync, completion-last publication and permanent locks are implemented
and tested through controlled failures. Live occupied-player and Discord-network
tests require a human/credentials and were not claimed complete.

## Security and handoff

Resolved Compose has only the two loopback-bound game UDP publications. RCON/API
and the typed socket are private. Runtime services use UID/GID 1000 with dropped
capabilities and no-new-privileges. The initializer/tools are networkless; tools
drop root before data operations. No Docker socket or privileged service exists.
Discord has no world/control mount or RCON credential. Build contexts are code
whitelists and contain no downloaded game or private runtime data.

The optional Discord image built with pinned dependencies and synthetic command,
role/restart and information-safety checks passed. The six commands are implemented;
live guild registration/login was not attempted without supplied credentials.

At handoff, the imported project's agent and ops containers were healthy and idle
with desired=false, no game child and OFFLINE_EXPECTED. The independent restore
and disposable projects' control services were stopped. Discord stayed disabled.

The private handoff consists of the public code repository plus separately held
verified archive/manifest, deployment .env and secret files. Named-volume internals
are not a transfer format. Private integration evidence, jobs, logs, archives and
original discovery evidence remain local. See LINUX-HANDOFF.md for transfer and
acceptance.

## Outstanding acceptance

1. Free comfortable host memory for the configured 6 GiB imported heap and remeasure
   host/Docker resources before starting the imported instance.
2. Reach imported READY, inspect fresh Linux mod/media/Lua logs against the prior
   baseline, then test connect, authentication, spawn, world/account/player state,
   representative mods, save/quit and disconnect/rejoin with a PZ 42.21.0 client.
3. Repeat representative persistence checks on the restored imported copy.
4. Supply a private Discord token/guild/role and perform the six live command and
   authorized zero-player restart checks if Discord is wanted.
5. Install/authenticate GitHub CLI or provide another authenticated publication
   route, then publish only the audited code repository as pz-docker-server.
