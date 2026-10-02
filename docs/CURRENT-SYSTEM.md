# Current Windows system: verified discovery

This is the historical snapshot audit. Current Linux implementation and acceptance
are documented in ARCHITECTURE.md and TEST-REPORT.md.

Discovery date: 2026-10-02 (Europe/Berlin). Scope: the local, read-only `source-snapshot`, not the live production host. This document describes observed code and copied evidence; a logged READY state is not a current production health check. No source operations scripts were executed.

## Evidence and inventory

The snapshot contains 140,619 files, 1,309 directories including its root, and 7,727,061,335 bytes (about 7.20 GiB). A recursive inventory found no symbolic links. The workspace also contains `pz-handoff-current.tar.gz`; it was not extracted over the verified snapshot. No application installation, SteamCMD directory, or top-level secrets directory is included.

| Snapshot section | Files | Bytes | Contents |
| --- | ---: | ---: | --- |
| `ops` | 1,952 | 36,109,846 | Scripts, Git, Windows tools, Python environment, generated metadata |
| `instances` | 138,549 | 7,688,133,573 | Only the `szs` instance; world, databases, configs, mod data, logs, built-in backups |
| `backups` | 111 | 2,580,166 | Config history only; no `backups/szs` operational snapshots |
| `logs` | 1 | 231,873 | Monthly health CSV only |
| `handoff` | 6 | 5,877 | Commit, remote metadata, four exported task XML files |

All 11 operations PowerShell scripts, both launchers, the complete Discord bot, README, both mod plans, state helpers, task exports and config-history structure were inspected. Instance files were inventoried recursively; world binaries were not decoded wholesale. SQLite account databases were opened with `mode=ro&immutable=1` to inspect table names only. Built-in ZIP central directories were inspected without extracting or changing them. Config values were read through allowlists; credential values are omitted here.

### Operations source inventory

Paths below are relative to `source-snapshot/ops`.

| File | Actual responsibility |
| --- | --- |
| `Manage-PZ.ps1` | Main interface: status, players, save, start, stop, restart, backup, update; locking, intent, pending validation, fresh-start acknowledgement |
| `PZ-Lock.ps1` | Exclusive guard handle, maintenance sentinel, owner-token/PID/start-time validation and conservative stale recovery |
| `PZ-State.ps1` | Timestamps, config/pending fingerprints, ordered mod-state parsing, schema v1/v2 validation, legacy plan replay, atomic writes |
| `Apply-PZModPlan.ps1` | Preview/apply JSON deltas, Before/After positioning, config history, atomic INI replacement, schema v2 pending record |
| `Config-State-PZ.ps1` | Check/commit whole config and Workshop/Mods baselines, copy config history, refuse unguarded manual commit during pending |
| `Workshop-State-PZ.ps1` | Compare configured items with local Workshop manifest/folders and Steam metadata; report/state/JSON; no download |
| `Backup-PZ.ps1` | Copy `Server`, `Saves`, `db`; publish completed directory snapshots; retain recent and weekly backups |
| `Backup-Catalog-PZ.ps1` | Shared completion/age/validity rules for rotating operational backups, including legacy markers |
| `Maintain-PZ.ps1` | Hourly automation: six-hour build checks, pending restart at zero players, backup if latest valid backup is at least 24 hours old |
| `Watch-PZ.ps1` | Restart an absent process only when desired-running is present and maintenance absent; leave degraded live process alone |
| `Log-PZHealth.ps1` | Process/host/network/backup/config telemetry to monthly CSV; twelve-month cleanup |
| `Start-SZSServer.cmd` | Launch production `szs` Java process |
| `Start-TestServer.cmd` | Launch `pztest` from `instances/test`, using the same game ports as production |
| `PZ-DiscordBot.py` | Six guild slash commands; public information and role-gated safe restart |
| `discord-bot.json` | Guild, role, port, public-access and direct-host configuration; not the bot token |
| `mod-plans/26-10-01-QOL.json` | Reviewed additions: three Workshop IDs/mods, including BeyondTen before SkillRecoveryJournal |
| `mod-plans/mod-plan.example.json` | Placeholder example; not a deployable production plan |
| `mod-order.txt`, `mod-metadata.csv`, `mod-load-constraints.csv` | Ignored audit output: 259, 371 and 296 lines respectively; no generator in this snapshot and no runtime consumer in the inspected scripts |
| `.gitignore`, `.gitattributes` | Ignore runtime/tools/tests/venv/generated metadata; normalize PS1/CMD to CRLF |
| `README.md` | Windows operating instructions and previous audit notes; historical claims distinguished from present snapshot contents |

### Git and handoff

`ops/.git` is present. HEAD and `handoff/current-meta/git-commit.txt` agree at `<private-source-commit>`, on `main`. Working tree is clean for tracked files. Local HEAD and the copied `origin/main` have zero ahead/behind commits; this does not prove the current remote state. No fetch, push, checkout, config write or index refresh was performed. Read-only commands used `--no-optional-locks` and a command-scoped `safe.directory` exception because the copied repository has different Windows ownership.

Recent commits include Discord restart progress changes, operations hardening, and the mod pipeline. There are 20 tracked files; `.venv`, `tools`, state JSON, guard, Python caches and mod audit output are ignored. Remote metadata contains GitHub fetch/push entries; remote addresses and account information are intentionally not reproduced. `.git/config` has no credential-named fields in the inspected text. This workspace has no top-level Git repository and no Docker repository was initialized during discovery.

## Game configuration and runtime

Historical production root is `C:\PZ`; instance is `C:\PZ\instances\szs`. Active files include `Server/szs.ini`, `szs_SandboxVars.lua`, `szs_spawnpoints.lua`, `szs_spawnregions.lua`, `Saves/Multiplayer/szs`, and `db/szs.db`.

The current INI derives **111 distinct WorkshopItems, 137 distinct Mods, and one Map (`Muldraugh, KY`)**. These are snapshot observations, not implementation constants. Preserve exact order and case. The actual INI key is singular **`Map=`**; plan/pending JSON calls the array **`Maps`**.

Configured ports are UDP 16261/16262 and RCON TCP 27015. MaxPlayers is 8; Public=false, Open=true, UPnP=false, SteamVAC=true. A nonempty game password and RCON password exist. The INI's DiscordToken field is empty; the separate Python bot uses a different token file. SaveWorldEveryMinutes=0; game-native backups are enabled at startup and version changes, count 5, periodic backup interval 0.

`szs.ini` is 21,552 bytes, UTF-8 without BOM with 420 CRLF line endings. `szs_SandboxVars.lua` is 63,304 bytes, UTF-8 without BOM with 1,322 CRLF endings. Migration must initially copy both byte-for-byte. Spawn-region paths reference eleven `media/maps/.../spawnpoints.lua` files with exact spelling, commas and spaces; no Windows drive paths were found in the active spawn files or root `options.ini`.

Launchers use the bundled `jre64/bin/java.exe`, `zombie.network.GameServer`, Steam enabled, ZGC, `-Xms6g -Xmx6g`, `java/;java/projectzomboid.jar`, `natives/`, servername/cachedir and port 16261. `pztest` uses the same port; its cachedir is not included. Test and production launchers cannot safely run together on the original host.

The latest console and DebugLog both report **42.21.0**, one `SERVER STARTED` marker and one shutdown marker. Built-in backup version marker says 42.21. Health CSV records Steam build ID 25485538, but the app manifest itself is absent. Do not infer an immutable depot or Steam branch solely from the build string. [The developer announced 42.21 Stable on September 28](https://projectzomboid.com/blog/news/2026/09/42-21-stable-released/), consistent with the source scripts' public-branch policy as of discovery. Linux app availability and downloaded build still require phase-2 verification.

## Manager lifecycle

### RCON and readiness

RCON uses `ops/tools/rcon-cli/rcon-0.10.3-win64/rcon.exe`, reads `RCONPassword=` from the active INI, and passes it as a process argument. Endpoint is fixed at `127.0.0.1:27015`; it does not derive the endpoint from RCONPort. Commands found are **`players`, `save`, `quit`**. Player count must match `Players connected (N):`.

Process detection uses CIM `Win32_Process`, `java.exe`, `zombie.network.GameServer`, and `-servername szs`. Readiness requires that process, a Windows adapter named `Ethernet` with Status=Up, both UDP ports, and parseable RCON players. UDP checks do not verify socket ownership. Readiness waits up to 1,200 seconds, polls every two seconds, prints progress every 30 seconds, and fails early if a previously observed Java process disappears. A timeout leaves a still-running process untouched.

`status` returns process/network/player details and codes 0=healthy, 1=no process, 2=degraded/RCON unavailable. It does not itself expose the richer five-state health model or all intent fields. `players` and `save` directly use RCON and do not acquire the lifecycle lock.

### Start, stop and restart

`start` validates pending state, sets desired-running, and launches hidden `cmd.exe /c Start-SZSServer.cmd` if Java is absent. Starting an existing process only checks readiness and retains pending. A stopped server with pending gets a pre-workshop-update backup before fresh start.

`stop` clears desired-running before RCON/waits. It refuses shutdown when player count is unknown, including with `-Force`. It refuses connected players unless `-Force`; this switch permits a **graceful** occupied shutdown and never kills Java. It issues `save`, waits one second, sends `quit` (ignoring RCON disconnect/exit code), and waits 60 seconds for process disappearance. Timeout returns 4 and leaves the process alone. Intent is restored after pre-shutdown refusal codes 2/3 if previously desired. No in-game notification/countdown command exists in this path.

`restart` validates pending/config state and checks Workshop metadata before stopping. Backup type is pre-workshop-update for pending, Workshop/Mods changes, upstream updates, missing downloads, or unavailable Workshop status; otherwise pre-config-restart for config change/missing baseline; otherwise no safety backup. It sets desired-running, performs graceful stop, optionally backs up, then fresh-start/readiness/baseline acknowledgement.

Fresh-start acknowledgement validates pending before launch and after readiness, ensures the pending-record fingerprint did not change, computes the **post-start** config fingerprint, commits that baseline, checks pending/config stability again, then removes pending. An unrelated startup rewrite is allowed before the baseline is measured. Whole config stability is still required during final commit/removal, not against the old pre-start hash.

Manager exit codes: 0 success; 1 stopped status; 2 unknown players/degraded/readiness timeout; 3 connected-player refusal; 4 stop timeout; 5 newly started process disappeared; 6 caught operation failure; 10 lock unavailable. Some uncaught errors may use other codes. Errors in update, or selected actions when Java is absent, remove desired-running for safety; a nonzero readiness result without an exception is not the same path.

### Desired state and maintenance lock

Desired-running is presence of `ops/desired-running.flag`. `.maintenance` is an **operation lock sentinel**, not an independent user maintenance-mode switch. `.maintenance.guard` is permanent and held with an exclusive kernel file handle. `lock.json` holds owner token, PID, process start time/UTC ticks, CreatedAt and action. Release requires the matching owner. Recovery requires demonstrably dead/reused PID; unknown ownership is refused, and unrecognized contents/reparse points are not recursively removed.

Start/stop/restart/backup/update and apply use this lock. Config-State's direct commit is not independently locked. Automatic operations recheck intent under the lock via `-OnlyIfDesired`. Watchdog starts only an absent process, never an unhealthy present one. Snapshot has the permanent guard, config-state and maintenance-state, but **no desired-running flag, active maintenance directory or active pending record**. Treat that as copied state only. Last logged state is OFFLINE_EXPECTED.

## Server and Workshop updates

`update` validates pending, stops only if previously running, makes pre-server-update backup, runs SteamCMD, and restarts only if previously running. Previously stopped remains stopped, including its pending record. SteamCMD command is `+force_install_dir C:\PZ\app +login anonymous +app_info_update 1 +app_update 380870 +quit`; there is no explicit beta flag or routine `validate`. Success requires both zero exit code and expected installed/up-to-date text. Output goes to `logs/steam-update-<timestamp>.log`.

Maintenance queries app 380870's `public` build via `app_info_print`, compares local appmanifest buildid, and checks roughly every six hours. A failed/deferred update is retried on later hourly runs; it does not immediately run a second lifecycle action in that same pass. No fixed daily restart exists.

Workshop belongs to game app **108600**, distinct from server app 380870. The state script reads `C:\PZ\app\steamapps\workshop/appworkshop_108600.acf` (`WorkshopItemsInstalled`, manifest, timeupdated) and content folders. Configured numeric IDs are deduplicated in order. Remote item details come from Steam `GetPublishedFileDetails` POST, batches of 50, 30-second timeout. Status is Missing, Unknown, Update or Current; aggregate is update if missing/newer, unavailable if unresolved/API failure, otherwise none. A timestamp comparison is a heuristic, not content verification.

No explicit SteamCMD Workshop-download loop or independent `workshop-update` command exists. PZ startup handles configured Workshop content; the console records Workshop download transitions and 111 distinct IDs. No automatic restart occurs solely for arbitrary upstream Workshop changes. Restart uses Workshop state to choose a safety backup. The actual manifest/content trees are not included, so current downloaded contents cannot be audited from this snapshot. SteamCMD calls in Discord and maintenance are not centrally serialized.

## Backups, restore and history

Normal `Manage-PZ backup`: lock, validate pending, remember running state, player check, save/quit and verified termination, copy, retention, restore previous running state with readiness/baseline handling. Failed backup normally attempts to restart a previously running server; with pending and a failed safety backup it remains stopped and intent is cleared. `Backup-PZ.ps1` called directly does **not** stop or lock the server.

The copy helper uses robocopy `/E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /XJ`, treating exit codes >=8 as failure. It copies **only Server, Saves, db** into its own `.inprogress-<GUID>`, calculates bytes, writes `_backup.json` schema 2/Status=complete/Created/CompletedAt/Type/ServerName/BuildId/SizeBytes/Source, and publishes by same-volume directory rename. Collisions add GUIDs rather than overwrite; transient rename failures have five exponential retries. Only its own unpublished temporary directory is cleaned up after failure.

The catalog recognizes five rotating backup types with timestamp and optional GUID, real component directories and valid metadata. It uses CompletedAt for v2, Created for old markers, and directory time only for legacy records without Created. It excludes incomplete/unrecognized/protected backups. Retention keeps four latest valid backups across all types plus up to four older ISO-week anchors not covered by recent ones, preferring non-daily anchors. It does not delete `known-good-*`. Completion markers do not prove file integrity or successful restore.

Hourly maintenance considers **any** valid completed rotating backup younger than 24 hours sufficient. Pending restart takes precedence over daily backup once no build update was attempted; connected/unknown players defer. Maintenance does not acknowledge pending itself.

No restore command/script or proven restore smoke test exists. Historical README mentions four operational snapshots and protected migration backups, but these are **absent from this copy**. Do not describe them as available recovery material.

There are twelve ordinary config-history directories, each with nine INI/Lua files; one pre-mod-plan directory with original INI and plan; and one archived resolved **schema v1** pending JSON. Counts progress from 117 Workshop/135 Mods, to 108/134, to current 111/137. The v1 plan's decoded-text hash matches the current reviewed plan. Its Plan and History references are absolute Windows paths and need explicit relocation to copied artifacts for legacy validation. It is an archive, not an active pending record. No proof of resolution method is inferred from its filename.

Config fingerprint hashes sorted names plus SHA256 of **all** direct `.ini`/`.lua` files in Server, including servertest configs and `szs_SandboxVars1.lua`. WorkshopHash hashes only literal WorkshopItems/Mods lines, **not Map**. State check yields baseline-missing/workshop/config/none; Map-only changes classify as config, while pending validation does include Maps. Current whole-config and Workshop baselines both match using the source PowerShell sort order; the latest history's nine files also match byte-for-byte. Porting must define a stable cross-platform sort and avoid pretending Python ordinal sorting reproduces Windows culture sorting.

## Instance persistence and generated files

Complete disposition is in [DATA-MIGRATION.md](DATA-MIGRATION.md). Critical findings:

| Instance entry | Files / bytes | Classification |
| --- | --- | --- |
| `Saves/Multiplayer/szs` | 138,406 / 1,071,060,774 | Required entire world; includes players.db, vehicles.db, zero-byte journals, global/mod data, map/chunk data and nested ZIPs |
| `Server` | 12 / 339,317 | Required configs/spawn scripts; extra test/old configs retained as reference, not blindly activated |
| `db` | 2 / 172,032 | Required szs account DB; separate servertest DB also present |
| `Lua` | 5 / 39,698 | SkillRecoveryJournal per-world JSON and ttf_stats_mp records/index are persistent mod data; one diagnostic log |
| `options.ini` | 1 / 3,586 | Instance settings; preserve |
| `backups` | 7 / 6,553,666,568 | Five startup ZIPs, one version ZIP, version marker; archive separately rather than recursively back up backups |
| `Logs` | 112 / 59,823,185 | Historical game logs; sensitive diagnostics, not required world state |
| `Crafting/AllRecipes.txt` | 1 / 86,564 | Generated recipe listing; preserve as reference, regenerate for Linux |
| `messaging/DebugOptions_list.xml` | 1 / 39,383 | Generated debug option listing; preserve as reference |
| `ItemTracker.log`, `server-console.txt` | 2 / 2,902,466 | Diagnostics, exclude from live import |
| `mods`, `Workshop`, `Recording` | empty | No local mod binaries/content/recordings found; do not confuse empty Workshop with the external app cache |

Account DBs contain whitelist, ban, role/capabilities, Steam allowlist, userlog and ticket tables. Rows, password hashes and identities were not printed. World player/vehicle databases must be preserved in addition to the account DB.

Built-in backup ZIP listings include options.ini, db, Server and Saves; four newer startup ZIPs also include Lua. They are separate from operations snapshots. ZIP listings alone are not an integrity/restore proof.

Ops durable records: config baseline/history, mod-plan provenance, maintenance check timestamp, bot configuration and desired state. Ops transient records: owned lock/sentinel/socket equivalents, temporary writes, in-progress backup directories and caches. Pending records are generated **but operationally durable until acknowledgement**, not disposable temp files. Existing baseline hashes and Windows PID ownership should not be adopted as Linux runtime state.

## Health telemetry and source log baseline

Logger runs every two minutes, appends `logs/health/pz-health-YYYY-MM.csv` using `Export-Csv -UseCulture` (this file uses semicolons), and removes files older than twelve months. Columns: Timestamp, HealthState, DesiredRunning, Maintenance, Players, RCON_OK, UDP_16261, UDP_16262, PZ_PID, PZ_Uptime_min, PZ_WorkingSet_GB, PZ_Private_GB, PZ_CPU_Total_s, PZ_Threads, PZ_Handles, System_CPU_pct, RAM_Total_GB, RAM_Used_GB, RAM_Free_GB, RAM_Used_pct, C_Free_GB, C_Used_pct, Backup_Age_h, Backup_Name, Steam_Build, Workshop_Count, Mod_Count, Console_Log_MB. Errors go to health-logger-errors.log.

State priority: maintenance sentinel -> MAINTENANCE; process + RCON + both UDP -> READY; process -> STARTING_OR_DEGRADED; desired -> DOWN_UNEXPECTED; otherwise OFFLINE_EXPECTED. **Unlike manager readiness, logger READY does not test Ethernet.** Its backup-age logic still uses bare timestamp names/directory mtime, not the newer catalog/GUID/CompletedAt rules; Discord and maintenance use the catalog. This is a real inconsistency to fix explicitly.

Copied CSV: 947 rows, 2026-10-01 09:26:22 through 2026-10-02 17:05:01; 909 READY, 24 MAINTENANCE, 14 OFFLINE_EXPECTED. Last sample is desired=false, no RCON/UDP, 111 Workshop/137 Mods. CPU/RAM/disk fields describe the original Windows host, not this computer.

Latest console and DebugLog duplicate the same startup evidence. The console contains 2,707 ERROR and 6,775 WARN keyword occurrences, including 499 `java.nio.file.NoSuchFileException` occurrences associated with Workshop/media paths and one Lua-subsystem error line. These are text counts, not independently diagnosed failures; the same log reached SERVER STARTED and subsequent telemetry recorded READY. There are no matched explicit Workshop-failure phrases in the limited pattern scan. Future Linux logs need comparison against this noisy baseline; READY alone does not prove all mods work. No raw logs or exception paths are reproduced here.

## Discord behavior

The bot uses discord.py, guild-only command sync, minimal guild intents, and an asyncio restart lock. Token comes from `C:\PZ\secrets\discord-bot.token`. `discord-bot.json` has GuildId, RestartRole, Port, PublicAccess and DirectHost; PublicAccess=true. This is separate from PZ INI Public=false.

| Existing command | Behavior |
| --- | --- |
| `/pzstatus` | Fast local manager status, maintenance, player count/names, process uptime, pending note; no Steam/update query |
| `/pzinfo` | Three paginated German-language pages of allowlisted numeric/bool INI/Lua settings; never evaluates Lua or returns full config/strings |
| `/pzmods` | Paginated configured Workshop order (25/page), Steam links/titles/status, five-minute view timeout |
| `/pzip` | ZeroTier, public/direct host if enabled, and Ethernet LAN addresses; optional ipify lookup |
| `/pzhealth` | Steam build comparison, config and Workshop state, pending, catalog backup age, disk, latest monthly health row; missing data shown unavailable |
| `/pzrestart` | Case-insensitive configured role name, one restart at a time, known zero players required; chooses update+restart if build differs, otherwise restart, including when update query unavailable |

No `/pzstats`, `/pzplayers`, central events thread or background event-publishing scheduler exists. Read commands are public; restart denial for unauthorized role is ephemeral. Restart streams verified manager milestones into one public message, falls back to a regular channel message if needed, and reports startup progress once a minute. It never sends `-Force`. Manager rechecks players before shutdown. The streaming subprocess has a 1,800-second timeout; on timeout/cancellation the bot kills the **manager subprocess**, not Java, potentially interrupting an operation. Port to durable jobs independent of Discord interaction lifetime. Failure tails currently display raw manager output, so the replacement must sanitize structured errors.

## Exported Windows Scheduled Tasks

All exports request HighestAvailable and IgnoreNew (no overlapping instance of that task). Principal identity details are not reproduced.

| Task export | Trigger/action | Other observed settings |
| --- | --- | --- |
| `Project_Zomboid_Watchdog.xml` | Boot + every 5 min; PowerShell 7 Watch-PZ | PT25M limit, StartWhenAvailable |
| `Project_Zomboid_Maintenance.xml` | Every hour; PowerShell 7 Maintain-PZ | PT1H limit, StartWhenAvailable |
| `Project_Zomboid_Health_Logger.xml` | Every 2 min; pwsh Log-PZHealth | Disallow start on battery / stop on battery; no explicit execution limit in export |
| `Project_Zomboid_Discord_Bot.xml` | Boot; Windows venv Python PZ-DiscordBot; working dir ops | PT0S limit, three failure restarts one minute apart, StartWhenAvailable |

Watchdog/maintenance repetitions have P3650D duration and StopAtDurationEnd. Host idle/battery/task paths are Windows implementation details, not Docker requirements. Scheduling will be portable service loops.

## Credentials and Linux blockers

Credential **locations only**:

- RCONPassword and game Password in current/old INIs and their history/ZIP copies. Treat copied world/config archives as private.
- INI DiscordToken key exists but is empty in current config.
- Referenced Discord token file under `C:\PZ\secrets` is absent from snapshot.
- RCON tool YAML has a nonempty password setting (not reproduced); manager supplies INI password explicitly. Tool config must also be excluded from the new project.
- Account and world DBs hold account/player information; whitelist may contain password material. No database row inspection was performed.
- Git remote/config/handoff task principals can contain account/host metadata; not carried into the new runtime. SSH keys/config are not included and were not accessed.

Hardcoded Windows paths cover C:\PZ app/steamcmd/instances/ops/backups/logs/secrets; exact fixed szs names; Windows launchers, rcon.exe and robocopy; PowerShell executable paths in bot/tasks; C: drive disk statistics; .venv/Scripts/python.exe. Windows-specific APIs: CIM Win32_Process/OperatingSystem/Processor, Get-NetAdapter/Get-NetUDPEndpoint/Get-NetIPAddress/Get-NetIPConfiguration, process handle/private memory fields, cmd shell, hidden-window flags, Windows PID/start ticks, culture CSV/hash ordering and NTFS rename/sharing semantics. `/pzip` discovers host Ethernet/ZeroTier; container bridge addresses would be wrong player endpoints.

Dependencies: PowerShell 7/.NET APIs (no imported third-party PS module found; Windows networking/CIM commands are required), bundled Windows Java/native libraries, SteamCMD, robocopy, rcon-cli 0.10.3. mcrcon.exe and an RCON archive/checksum/license are included but not used by current manager. Snapshot Windows venv includes discord.py 2.7.1, aiohttp 3.13.5, aiohappyeyeballs, aiosignal, attrs, frozenlist, multidict, yarl, propcache, idna, typing_extensions and async_timeout; no requirements/lock file is provided. Rebuild the Linux environment rather than copy the venv. Python bot uses stdlib plus discord imports. External services: Steam/Workshop metadata and content, Discord gateway/API, optionally ipify.

## Local test prerequisites and discrepancies

Docker CLI 29.8.0 and Compose v5.5.1 are installed. A read-only check outside the sandbox selected `desktop-linux`, but `dockerDesktopLinuxEngine` named pipe was absent; Docker server version and OSType could not be read. Docker Desktop's Linux engine must be running before phase 2. WSL executable is present; WSL2 backend health/distribution status is not verified. Nothing was installed or started. Earlier sandbox-only Docker checks also lacked access to user Docker config; the outside-sandbox check establishes that the Linux engine itself is currently unreachable.

Key deviations from orientation: mod fingerprint fix already exists; exact INI key is Map; no force-kill/countdown/restore; maintenance is a lock rather than operator mode; six actual bot commands without stats/events; extra Lua/options persistence outside backup coverage; historical operational backups absent; logger and manager disagree about Ethernet and backup-age rules; no current desired/pending flag; no independent Workshop updater. Proposed changes and unresolved proof points are explicit in [ARCHITECTURE.md](ARCHITECTURE.md), [MOD-PLAN-LIFECYCLE.md](MOD-PLAN-LIFECYCLE.md), and [../PLAN.md](../PLAN.md).
