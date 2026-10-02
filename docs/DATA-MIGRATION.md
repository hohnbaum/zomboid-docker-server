# Private migration, backup and restore

The source snapshot remains read-only evidence. Git contains code and synthetic
tests only. Original private discovery documents are preserved outside Git.
See CURRENT-SYSTEM.md for the Windows baseline and TEST-REPORT.md for acceptance.

## Source disposition and import

Import derives the configured server name and selects its four active Server
files: INI, SandboxVars, spawnpoints and spawnregions. It copies the entire
Saves/Multiplayer/server directory, matching account database, options.ini,
Lua/SkillRecoveryJournal/Multiplayer/server and the complete Lua/ttf_stats_mp tree.
SQLite and world journal files are copied rather than reconstructed.

Other source-instance files are preserved in a protected import-reference archive
with per-file hashes/disposition: old/test configurations, generated references,
console/diagnostic files, historical native ZIPs and unknown additions. Native ZIPs
never enter the live rotating backup set. Windows app files, Workshop and venv are
not copied. Exact WorkshopItems/Mods/Map order and case is read from the INI.

Configure a new explicit Compose project and matching PZ_SERVER_NAME. Build the
ops image, keep both control services stopped, then run:

~~~sh
./pz import --source /private/stopped-instance
~~~

The host wrapper creates an ignored private transfer archive and SHA inventory
using native host reads, avoiding repeated small-file NTFS/WSL crossings.
It rejects links/case collisions, fingerprints source before and after packing,
transfers one read-only archive and rechecks the original source after import.
Private transfer files remain under ignored tmp for operator provenance.

Networkless tools extract bounded regular files/safe directories into Linux staging.
Absolute paths, traversal, links, special members, duplicates and case collisions
fail. Extracted hashes must match the source manifest before normal import begins.

Normal import requires an empty target and desired=false, takes lifecycle/game
locks, stages all copies, validates hashes/counts, exact INI arrays and copied SQLite
PRAGMA quick_check, and checks source inventory again. It publishes reference
provenance, active data, an exact migration gate and a protected pristine backup.
import-complete is published LAST after pristine verification. Java never starts.

Interrupted/partial imports stay offline. Inspect staging/provenance or choose a
new empty project; directory presence alone is not completion. The initial version
gate is exactly 42.21.0. Only Linux startup evidence tied to the installed Steam
build can satisfy it; imported Windows console logs cannot.

## Full operational backups

Backups run after graceful game exit or on already stopped data. A permanent game
kernel lock independently prevents live copying. Persistence includes complete
Server/Saves/db/Lua, options.ini, approved migration markers and coherent pending
plan/config history. App/Workshop, logs, tokens, sockets, job/lock state and old
native ZIP collections are excluded. Lua diagnostic .log files are excluded.

Creation uses same-volume .inprogress staging, original/copy/rechecked-source SHA
and byte inventories, copied database checks, manifest.json and schema-3
_backup.json completion metadata written last. Verification precedes atomic
directory rename. Protected known-good and reference archives are never retained
through the rotating deletion policy.

The catalog checks strict name/schema/status/server, manifest checksum, counts,
bytes, UTC completion time and required structure. It avoids rehashing every
world file on each health read; full file verification occurs at creation, export
and restore. All backup-age readers use it. Retention keeps four newest plus up
to four older UTC ISO-week anchors, preferring non-daily entries within an older week.

A running backup action saves/stops, copies and freshly restarts; a deliberately
stopped deployment stays stopped. Pending is acknowledged only after a successful
fresh readiness barrier. Update/Workshop/config operations select their safety type.

## Archive and restore

With control services stopped, export a completed snapshot:

~~~sh
./pz export --backup BACKUP_NAME --output exports/private-handoff.tar.gz
~~~

Export verifies the snapshot and creates an exclusive tar.gz with SHA256 output.
This archive contains private credentials/player data; Git alone cannot restore it.

Restore to a new empty explicitly named Compose target is preferred:

~~~sh
./pz restore --archive /private/handoff.tar.gz
~~~

The project and server name select the target. Offline tools require stopped
control services/false intent. Online named-backup restore also verifies child
stopped and desired=false. Existing replacement additionally requires
--confirm-replace, locks and a protected pre-restore backup. No PID, socket,
job or stale lock is restored. Permanent guard inodes survive replacement.

Extraction rejects absolute/traversal/link/special/duplicate paths and enforces
size/entry limits. Restore verifies every file hash/size, manifest checksum,
actual inventory, counts, persistence scope, server name, database integrity and
complete pending plan/history replay. Stale control paths cannot be introduced
through an edited manifest. Imported restored backups keep the migration gate
and receive verified restored-pristine evidence.

Publication is staged and journaled, leaving desired=false. Multi-directory
replacement is not an atomic volume switch. Interrupted restore preserves its
journal/staging and blocks startup. Restoring the original verified archive into a
new empty project is the supported recovery; keep the interrupted target offline.

## Acceptance and handoff

An archive round trip alone is not running restore acceptance. The test must reach
READY, gracefully stop, create a full backup, introduce a harmless post-backup
marker, restore into a second empty target, prove hashes/marker absence, start the
restored game and reach READY. Human client checks cover account/character/vehicle/
world and mod persistence separately. See TEST-REPORT.md and LINUX-HANDOFF.md.
