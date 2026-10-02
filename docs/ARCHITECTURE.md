# Implemented architecture

The stack uses Docker Compose and three small Python services. It has no Docker
socket, privileged service, arbitrary shell endpoint or external database.
Historical Windows behavior is in CURRENT-SYSTEM.md; current test evidence is
recorded separately in TEST-REPORT.md.

~~~mermaid
flowchart LR
  CLI[Host pz wrapper] -->|Compose exec| OPS[pz-ops]
  BOT[pz-discord optional] -->|Private authenticated HTTP| OPS
  OPS -->|Typed Unix socket| AGENT[pz-server agent]
  OPS -->|Private RCON| GAME[PZ native JVM process]
  AGENT -->|Packaged Linux launcher| GAME
  CLIENT[PZ client] -->|Published game UDP| GAME
~~~

## Services and ownership

pz-server owns the packaged Linux native launcher and its embedded JVM. Fixed
socket operations are ping, status, start, install, build-query and Workshop report.
Requests reject extra fields, arbitrary paths and shell commands. A child has a
generation identity; repeated start returns that existing child. Ownership checks
use the process group/executable and socket inodes rather than a saved PID.
Kernel locks guard the agent, app installation and live data; Steam mutations
are serialized. Explicitly shared app volumes permit one runtime/update at a time.

pz-ops owns policy: desired state, operator maintenance, lifecycle lock, durable
jobs, RCON, health, mod/config state, backups, restore and scheduling. The host
wrapper uses Compose exec, so Docker access stays on the host. Its authenticated
HTTP API listens on private port 8080 with no published host port. Reads and jobs
have fixed allowlists; errors use fixed codes and never return raw tracebacks.

pz-discord is disabled unless the discord profile is selected. It receives token
files and nonsecret guild/role settings, has no data/control volume, RCON password
or Docker access, and uses private HTTP jobs. The six German commands retain role
gating, pagination and restart progress. A client disconnect never cancels a job.

Runtime services use UID/GID 1000, dropped capabilities and no-new-privileges.
The networkless one-shot root initializer owns only mounted project volume roots,
including steamapps and the nested Workshop mount. Networkless tools initialize
roots then drop UID/GID/groups before handling private data.

## Storage and network

| Named volume | Mount | Consumers |
| --- | --- | --- |
| app | /pz/app | server, initializer |
| workshop | /pz/app/steamapps/workshop | server, initializer |
| data | /pz/data | server, ops, initializer, tools |
| state | /pz/state | ops, initializer, tools |
| control | /pz/control | server, ops, initializer |
| backups | /pz/backups | ops, initializer, tools |
| logs | /pz/logs | server, ops, initializer |

Live app, Workshop and world files use Linux named volumes even on Windows.
Only explicit source/export transfer folders use host binds.
PZ_APP_VOLUME and PZ_WORKSHOP_VOLUME can select existing named volumes for
sequential tests; independent deployments should use separate app volumes.

The control network is internal; ops has only this network. The server also has
game/Steam egress and Discord has its own egress. Only game UDP 16261/16262 is
published, initially to 127.0.0.1 with configurable host ports. RCON, the ops API
and the Unix socket are unpublished. Advertised endpoints are configured in
private deployment settings; no container-IP or host discovery is shown to players.

## Installation and health

Installation explicitly runs Linux SteamCMD with force_install_dir, anonymous
login, app_info_update, app_update 380870 and quit. Container restart never invokes
app_update. Installed files persist in the app volume. start-server.sh loads
ProjectZomboid64.json; the agent sets Xms/Xmx in that file and passes server name
and Linux cachedir to the launcher. It uses the packaged Java runtime.

Steam build comes from appmanifest_380870.acf. Version evidence is taken only
from the current agent launch-log offset and tied to that build. Copied console
logs and previous-build evidence cannot satisfy the imported-world gate.
Imported data initially requires exactly 42.21.0 and pristine verification.

READY requires the current owned game process, configured owned UDP listeners,
authenticated RCON and a parseable player count. Internet/Steam availability is
reported separately and never required for READY. Health returns running,
launching, ready, desired, maintenance, player-known state, RCON/UDP, generation,
version/build, backup age, pending validity, UTC reasons and resource metrics.
RSS is process memory; cgroup memory is container memory, not host RAM.
Filesystem free space is the container filesystem, not Windows free disk space.

States are MAINTENANCE, READY, STARTING_OR_DEGRADED, DOWN_UNEXPECTED and
OFFLINE_EXPECTED. Maintenance takes display priority; ready remains a separate
flag. Existing degraded children are never automatically restarted.

## Lifecycle and scheduling

Save/quit refuses unknown players. Known occupied state requires explicit force,
which never permits killing Java. Ops waits up to 60 seconds for graceful exit;
Docker grants 90 seconds to the server container. Agent SIGTERM attempts save/quit.
An outer Docker timeout is not recorded as a verified clean shutdown.

Intentional stop persists desired=false across service restarts. Boot and
five-minute reconciliation may start an absent child when desired=true, maintenance
and recovery are clear. Automatic intent is rechecked after the lifecycle lock.
Hourly maintenance checks the app build roughly every six hours, handles validated
pending restarts with known zero players and creates backups after 24 hours without
a completed catalog entry. No fixed daily restart or upstream-only Workshop restart
is added. Health JSONL uses UTC monthly files, two-minute samples and roughly
12-month retention. All backup-age readers share the completed schema-3 catalog.

Each job is written before submission, has a request ID, phases and final result,
and runs independently of clients. A repeated ID/arguments returns the saved job.
On ops restart, queued/running records become interrupted, desired is cleared and
recovery is required; crashed mutations are not blindly replayed.

Workshop reports derive exact configured ID order, read manifest/content evidence,
and compare advisory remote timestamps. API failure remains Unknown. An explicit
Workshop job backs up, stops and performs a fresh PZ startup/download, collecting
before/after evidence and unresolved items. READY does not prove mod compatibility.
