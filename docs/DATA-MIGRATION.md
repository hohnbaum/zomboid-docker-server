# Data migration and recovery design

Status: discovery/design only, 2026-10-02. No data has been copied, launched, deleted or restored. Source is the read-only `source-snapshot/instances/szs`. Targets must be newly created staging areas/volumes under the separate Docker project. Preserve the verified snapshot and original handoff archive.

## Preserve the full persistence contract

The world is more than one DB or three directories. The complete `Saves/Multiplayer/szs` tree has 138,406 files and 1,071,060,774 bytes, including players.db, vehicles.db, their zero-byte journal companions, global_mod_data.bin, WorldDictionary files, entity/id/global-object data, maps/chunks, Lua and embedded ZIP files. Do not filter save contents by guessed filename patterns. Account/whitelist state in `db/szs.db` is separate from world player state.

| Source relative path | Proposed treatment | Reason |
| --- | --- | --- |
| `Server/szs.ini` | Active `/pz/data/Server/szs.ini`, exact initial bytes | Ports, ordered Workshop/Mods/Map, gameplay and private credentials |
| `Server/szs_SandboxVars.lua` | Active exact initial bytes | Sandbox and mod settings; preserve CRLF/UTF-8, do not evaluate Lua |
| `Server/szs_spawnpoints.lua`, `szs_spawnregions.lua` | Active exact bytes | Spawn configuration; validate Linux media-path spelling |
| `Saves/Multiplayer/szs/**` | Entire active world, exact files/case | World, mod/global/player/vehicle state; no selective chunk rewrite |
| `db/szs.db` | Active exact bytes | Accounts, bans, roles/capabilities, whitelist |
| `Lua/SkillRecoveryJournal/Multiplayer/szs/**` | Active persistent mod data | Existing per-world journal JSON outside saves |
| `Lua/ttf_stats_mp/**` | Active persistent mod data | Mod index and player/stat records; names/contents remain private |
| `Lua/that_damn_item_spawn.log` | Private reference archive by default | Diagnostic log; archive retains evidence if later needed |
| `options.ini` | Active exact bytes initially | Instance settings; retain unless tested Linux behavior warrants a narrowly documented adjustment |
| `Server/servertest*`, `db/servertest.db` | Private import reference archive | Other instance metadata, not szs runtime; do not activate/drop silently |
| `Server/szs_SandboxVars1.lua`, `*.bak`, `szs.ini.before-mod-cleanup-*` | Private reference archive | Old alternatives; active file selection must be explicit |
| `Crafting/AllRecipes.txt`, `messaging/DebugOptions_list.xml` | Reference archive, regenerate on Linux | Generated recipe/debug listings, not primary world state |
| `Logs/**`, `server-console.txt`, `ItemTracker.log` | Optional private diagnostic archive | Historical Windows paths/player/admin/chat content; not needed for world load |
| `backups/**` | Separate private historical-backups archive | Six ZIPs totaling about 6.10 GiB, plus version marker; avoid recursive live backup growth |
| Empty `mods`, `Workshop`, `Recording` | Recreate directories if needed | No local runtime content found; unexpected future contents require reclassification |

Import is conservative: every source path is assigned either active target or private reference/archive disposition in a manifest. Unknown future paths stop automatic classification or are retained in the private reference archive, never silently dropped. Do not assume Lua files are expendable because they were omitted by the old ops backup.

Never migrate Windows app/JVM/natives, SteamCMD, ops `.venv`, rcon tools, Workshop installation/cache or `.git` into the runtime. They are absent from the instance or replaceable Windows artifacts. Fresh Linux app installation uses dedicated app 380870; configured Workshop items use namespace 108600. Do not copy the Windows Workshop cache even if provided later.

Ops plans and config history are separate private provenance: copy selected validated plan artifacts/history to `/pz/backups/import-reference/ops` and retain archived v1 pending there. No active pending exists in this snapshot. Do not restore Windows lock handles/PID records, desired flag, maintenance sentinel or old baseline/check timestamps as active Linux state. Initialize imported target as desired=false, no operation ownership, baseline not-yet-acknowledged. An archive of old state is useful; adopting it as live Linux state is unsafe. Legacy active-pending import, if later required, needs explicit path relocation/hash/replay validation described in [MOD-PLAN-LIFECYCLE.md](MOD-PLAN-LIFECYCLE.md).

## Proposed import tool contract

Future `pz import --source <snapshot> --target <new-instance-volume>` must:

1. Resolve source/target and reject equality, containment in either direction, snapshot targets, traversal and unsafe links/reparse points. Validate servername and required source files. Never infer production SSH access.
2. Mount snapshot input read-only into a one-shot Linux helper; check destination is explicitly named and empty. Verify target belongs to this Compose project, child absent, intent false, and no unresolved operation. Do not reuse a random existing volume.
3. Inventory names, bytes, hashes and source metadata into a **private runtime manifest**, with active/archive disposition and source version evidence. Check case collisions and invalid names without normalizing filenames. Linux content downloads later provide the real case-sensitive mod test.
4. Copy all approved active data into a staging directory on the target Linux filesystem and create private reference archives separately. Preserve file bytes; permissions become restricted Linux UID/GID. Copy complete databases and journals together. No SQLite recovery or VACUUM is run against source. If database checking is needed, use a temporary target copy.
5. Compare source/staged file counts, sizes and SHA256. Check INI managed keys for missing/duplicate entries, exact ordered arrays and encoding; preserve unrelated lines/comments. Do not log password fields or account/player filenames publicly. Verify source hashes again after copying.
6. Atomically publish on the target filesystem and write an import-complete manifest **last**. Interrupted import leaves only a clearly named incomplete target and cannot trigger Java startup. Initialize Linux ops state, keep desired=false, and report the chosen target.
7. Run only a later explicit test start against the imported copy, after vanilla phase-2 proof and version/Workshop readiness gates. Preserve a pristine imported snapshot before first PZ write or save upgrade.

Named volumes are preferred even for live instance data so Windows NTFS does not hide Linux case errors. The source read-only Windows bind mount is merely an input. Backup export uses a tar/archive and private manifest, retaining case/bytes when moved to Linux; avoid extracting runtime mods onto NTFS as the portability test.

## Version and source-consistency limits

Console evidence is 42.21.0 and CSV build 25485538. App manifest is not included; public branch is the source update policy, not an immutable build pin. Before touching the imported copy, verify the freshly downloaded Linux version matches the world/client version. Do not start a lower build or silently upgrade to a newer one. Public Workshop downloads may have changed since snapshot; original item contents are not recoverable from this snapshot alone.

The last health sample is expected offline and console includes shutdown evidence. That supports a stopped snapshot but does **not** establish the export method's atomic consistency. World DB journals present are zero bytes. Immutable read-only account table inspection is not SQLite integrity validation and not a restore proof. Later validation must operate on a copy and include player/vehicle/account DB checks and client gameplay. If copy consistency cannot be proven, retain the source and compare with the included game-native backup ZIPs or request a later explicitly authorized consistent export.

## Backups in the new system

Use stop-the-world backups: hold operation lock, validate pending, check players, save/quit, wait for confirmed process exit, then copy all active persistence. Include active Server files, complete Saves, db, Lua persistence and options.ini; include approved future mod-persistent additions. Capture operational baseline, pending record and its immutable plan/pre-apply evidence coherently with the data so a restored pending lifecycle is still provable. Do not capture active locks, transient job ownership, secrets token files, app binaries, external Workshop cache or nested game-generated backups as ordinary snapshot content.

Metadata should include schema/status, UTC completion time, servername, build/version/branch evidence, file count/size/hash manifest, persistence inventory, pending provenance and operation ID. Publish marker last then same-volume rename; failed/in-progress directories never count as valid backups. Retain the existing five types and four recent/four older weekly anchors. No automatic deletion of import-reference or known-good archives. Backup-age telemetry and scheduling use the same catalog.

Backups are private: config passwords, account material and player state remain in them. Export `.env`/Discord/internal API tokens separately by secure operator arrangement, never embed real values into the project or handoff docs. Re-downloading app/Workshop does not guarantee an identical historical build/mod version; document that limitation in the backup manifest and handoff instructions.

Game-native startup/version backups may continue inside cachedir, but track their disk cost separately. Current six historical ZIPs are archived rather than imported into the live backup recursion. Preserve nested ZIPs **inside Saves** as world content; these are distinct from the top-level game backup archive directory.

## Restore and smoke-test acceptance

Prefer restore to an explicitly named new empty volume. Archive extraction must reject traversal, absolute paths, links escaping target and malformed/duplicate manifest entries. Verify all data before publication. Replacing a current target additionally requires explicit target selection plus confirmation/`--confirm-replace`, child stopped and desired=false, operation lock, and successful pre-restore backup. Never offer source-snapshot as a writable target. Restore does not resurrect stale owner PIDs or automatically start the world; reconstitute pending only when full provenance validates, then run the normal fresh-start path.

Planned isolated restore smoke test (not run during discovery):

1. On a unique test Compose project, import/start a copy, wait for READY and graceful stop, then create a full complete backup with manifest.
2. Record state hashes and stage a harmless marker/change in the **test target only** while stopped; retain the pristine archive. Do not alter passwords or world chunks merely to prove overwrite.
3. Restore the backup into another new named target. Verify marker/change is absent and all manifest hashes match. If testing replacement semantics, use a third disposable target and explicit replacement confirmation.
4. Start that restored target against the verified Linux version and freshly downloaded configured Workshop content; reach READY. Inspect logs for missing mods/case errors/Lua or script failures/save changes against the Windows baseline.
5. Verify account/player/vehicle databases on copies, expected mod persistence, and an actual client join/load/save/rejoin. Gracefully stop, report state and archive results. No production/snapshot destruction; no removal of test volumes without naming the exact project/targets.

A unit-test tar round trip alone does not satisfy restore acceptance. Until actual restored PZ reaches READY and a client verifies relevant state, migration/restore remains unproven.

## Capacity and Linux transfer

Active world/config/mod state is roughly 1 GiB today; whole instance is about 7.16 GiB primarily because historical game ZIPs occupy 6.10 GiB. Snapshot total is about 7.20 GiB. Budget additional fresh Linux app/Workshop storage, staging/pristine copies, rotating backups and game-native backups; app/Workshop size cannot be determined from this snapshot. Check free space before each large operation.

Future Linux handoff should contain the Docker source project, a verified stopped-state world archive with private manifest/provenance, and operator-created `.env` plus secret files. Named volumes are recreated/imported through tooling, not copied via Windows Docker internals. Preserve the same servername, container paths and verified build; change only host binding/advertised endpoints and resource/ownership configuration as necessary. A detailed README and LINUX-HANDOFF.md belong to later implementation phases.
