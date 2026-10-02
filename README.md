# pz-docker-server

Portable Linux Project Zomboid dedicated server using Docker Compose, a restricted
Unix socket agent, file-based operations and optional Discord commands.

This project is not affiliated with The Indie Stone. It does not distribute
Project Zomboid binaries or Workshop content. SteamCMD downloads them into private
named volumes on the deployment host.

## Requirements

Use an x86-64 Linux Docker engine with Compose v2 or later and Python 3.12+ on the
operator host. On Windows 11, use Docker Desktop with its WSL2 Linux backend and
PowerShell. Live data, app and Workshop storage use Linux named volumes.
Allow enough memory for the configured heap plus JVM native memory and the host OS.
The default heap is 6 GiB; a 2 GiB heap is suitable only for a disposable empty test.

## Quick start

Clone this code repository, enter its directory, then on Windows:

```powershell
Copy-Item .env.example .env
.\pz.ps1 init-secrets
docker compose build pz-server pz-ops
.\pz.ps1 init-empty
docker compose up -d pz-server pz-ops
.\pz.ps1 install
.\pz.ps1 start
.\pz.ps1 status
```

On Linux replace `Copy-Item` with `cp` and `.\pz.ps1` with `./pz`.
The initial game ports bind to `127.0.0.1`, 16261/UDP and 16262/UDP. A real client
needs the private generated game password from the named-volume INI. Read it only
in a private local terminal; never paste it into an issue or public log.

Container startup starts the control services. Installation and Java start are
explicit actions. An intentional stop survives service restarts. A degraded live
game is reported and is never automatically restarted by reconciliation.

## Operator commands

```powershell
.\pz.ps1 health
.\pz.ps1 players
.\pz.ps1 save
.\pz.ps1 stop
.\pz.ps1 restart
.\pz.ps1 update
.\pz.ps1 workshop-status
.\pz.ps1 workshop-update
.\pz.ps1 backup
.\pz.ps1 config-state
.\pz.ps1 apply-mod-plan private-plan.json        # preview
.\pz.ps1 apply-mod-plan private-plan.json --apply
.\pz.ps1 maintenance on --reason 'Operator work'
.\pz.ps1 maintenance off
.\pz.ps1 jobs
.\pz.ps1 job JOB_ID
.\pz.ps1 logs
```

`--force` permits graceful save/quit with known connected players; it never permits
unknown player state or kills Java. Jobs persist independently of CLI/Discord
connections. Use `--detach` to submit without waiting.

## Private world migration and restore

Supply a separately held stopped instance directory. Configure `PZ_SERVER_NAME`
to match its four active configuration files and account database. Stop both
Compose control services before using offline tools:

```powershell
docker compose stop pz-ops pz-server
.\pz.ps1 import --source /path/to/private/stopped-instance
docker compose up -d pz-server pz-ops
.\pz.ps1 version
.\pz.ps1 start
```

Import requires an empty target data volume, validates copies and SQLite data,
keeps historical files in a protected reference archive and creates a pristine
backup. It leaves `desired=false`. Imported instances initially require verified
Linux version **42.21.0**. A mismatch returns `BLOCKED_VERSION`; use an empty world
to establish build-specific Linux version evidence first. Do not weaken this gate.

Export a completed stopped-state backup, then restore its private archive into a
new Compose project with the same server name:

```powershell
.\pz.ps1 export --backup BACKUP_NAME --output exports/private-handoff.tar.gz
.\pz.ps1 restore --archive /path/to/private-handoff.tar.gz
```

Export uses offline tooling, so stop Compose services first. An online named-backup
restore uses `.\pz.ps1 restore --backup BACKUP_NAME`; the game and desired intent
must already be stopped. Replacing data requires `--confirm-replace` and creates a
protected pre-restore backup. Restore never starts Java.

## Discord

Discord is disabled by default. Supply the token in ignored `secrets/discord.token`
and the nonsecret guild/role settings in private `.env`, then use
`docker compose --profile discord up -d pz-discord`. The six commands are
`/pzstatus`, `/pzinfo`, `/pzmods`, `/pzip`, `/pzhealth`, `/pzrestart`.
Restart requires the configured role and known zero players. The bot accesses only
the authenticated private ops API; it has no world data, RCON credential or socket.

## Validation and documentation

The 96 synthetic tests pass on Linux, including optional Discord dependencies.
Windows passes with five platform/dependency skips. The downloaded Linux server
is **42.21.0 / Steam build 25485538**. Empty-world READY, graceful stop, persisted
intent, an explicit offline update, and a new-volume restore followed by READY
have passed with a disposable 2 GiB heap.

The private imported world was copied and hashed, its three SQLite databases
checked, and a protected pristine backup created. All 111 configured Workshop
items downloaded and report Current; all 137 configured mod IDs have exact
mod.info definitions. **Imported-world runtime integration is not yet completed:**
the host has insufficient comfortable headroom for its required 6 GiB heap.
Mod loading, case-sensitive media/Lua behavior, and human client/account/world
acceptance remain unproven. Live Discord acceptance also requires private
credentials. See [TEST-REPORT.md](docs/TEST-REPORT.md) for evidence and limitations.

Read [architecture](docs/ARCHITECTURE.md), [migration](docs/DATA-MIGRATION.md),
[mod lifecycle](docs/MOD-PLAN-LIFECYCLE.md), [Linux handoff](docs/LINUX-HANDOFF.md)
and [troubleshooting](docs/TROUBLESHOOTING.md). The five discovery documents retain
the technical baseline; original private copies are outside this repository.

Run `python -m unittest discover -s tests -v` and
`python scripts/audit-public-tree.py --history` before publishing. Git contains
code and synthetic tests only. World data, configuration credentials, tokens,
logs, backup archives and deployment `.env` stay private.

When using multiple private deployments, put `--env-file DEPLOYMENT.env` before
the wrapper command, and pass the same file to Compose:
`docker compose --env-file DEPLOYMENT.env up -d pz-server pz-ops`.
