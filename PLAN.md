# Migration implementation plan

Discovery and the three-service architecture were approved. Implementation is
authorized through all feasible local tests and public publication after audit.
The read-only snapshot is immutable; no production host is contacted.

## Baseline preserved

The Windows stack supplies safe player/RCON shutdown policy, persisted intent,
maintenance, watchdog/build/backup schedules, ordered mod plans and six Discord
commands. Its current schema-v2 arrays already solved the old startup fingerprint
problem. This port preserves exact order/case and fixes the operational backup
gap by including persistent Lua and options.ini. Historical native ZIPs and unknown
reference files are privately preserved, separate from rotating backups.

Public documentation omits operator credentials, user paths, network/guild IDs and
private Git account/remote identities. Original discovery copies remain outside
the new Git root. CURRENT-SYSTEM.md retains the detailed historical evidence.

## Implemented stages and gates

| Stage | Implementation | Acceptance |
| --- | --- | --- |
| Repository | Separate main Git, MIT original code, ignored private storage, staged/history audit | No runtime/secret/proprietary payload in public tree |
| Linux runtime | SteamCMD public app 380870, packaged native JVM launcher, UID 1000 agent | Actual installed build/version, empty READY, graceful stop/restart |
| Imported copy | Native transfer archive, Linux staging, hashes/databases, reference/pristine copies | Exact 42.21.0, resources, ordered Workshop evidence, READY/client checks |
| Ops | File jobs/locks/intent/maintenance, RCON, scheduling/telemetry, update and Workshop | Unknown-player refusal, stopped intent, no degraded autorestart |
| Persistence | Full schema-3 backup, protected/weekly retention, safe archive/restore | Verified stopped copy plus actual restored PZ READY |
| Mods/config | Schema-2 frozen replay, byte preservation, apply/ack journals, legacy importer | Synthetic tamper/crash/order tests; fresh-only pending acknowledgement |
| Discord | Disabled profile, six German commands, private API jobs | Offline framework tests; real token/guild test separately required |
| Handoff | Private stopped export, Linux setup/recovery/public boundary docs | Human join/rejoin and representative world state checks |

TEST-REPORT.md records actual outcomes; a unit/archive pass never substitutes for
a game READY or human-client acceptance. The initial import gate is exact 42.21.0.
A mismatch is BLOCKED_VERSION and must not be weakened. Insufficient measured
memory is a resource blocker, independent of code/data-copy acceptance.

## Operational requirements

Only game UDP is published, initially localhost. RCON/API/control are private.
No Docker socket, arbitrary shell endpoint, privileged service, copied Windows
binary/Workshop/venv, auto-update on container start or upstream Workshop autorestart
is introduced. Existing degraded children stay present for diagnosis.

Stop waits for authenticated, parseable players and uses save/quit only.
Force permits known occupied graceful shutdown; it never permits unknown state or
kill. Imported data and restored data start with desired=false and pristine evidence.

All live app/Workshop/data/state/control/backups/logs use Linux named volumes.
Backups include Server/Saves/db/Lua/options and coherent pending/config provenance.
Protected imports and references never enter retention deletion. Restore prefers a
new target; replacement requires false intent, stopped child, locks, pre-backup and
explicit confirmation.

Boot/five-minute reconciliation, hourly maintenance, roughly six-hour build query,
24-hour backup due and two-minute monthly UTC health JSONL replace Windows tasks.
No fixed daily restart is added. Durable jobs continue through client disconnect;
interrupted process jobs require explicit recovery rather than blind replay.

## Publication and remaining manual acceptance

Before any first push: run the synthetic Linux suite, resolved Compose boundary
checks, staged/tracked/history audit and credential keyword review; inspect status,
staged diff and tracked inventory. GitHub Actions uses synthetic fixtures only and
never downloads PZ or publishes private/game artifacts.

Authenticated installed GitHub CLI may create the approved public repository;
otherwise complete local Git and provide the exact publication command. No major
software is installed silently. Real Discord credentials, client actions and any
unresolved resource/version gate remain explicit operator steps.

See README.md, ARCHITECTURE.md, DATA-MIGRATION.md, MOD-PLAN-LIFECYCLE.md,
LINUX-HANDOFF.md, TROUBLESHOOTING.md and TEST-REPORT.md for usable commands/evidence.
