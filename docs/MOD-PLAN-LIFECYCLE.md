# Implemented mod and config lifecycle

The Windows source already had schema-v2 exact-array protection. This port preserves
it and adds byte-preserving edits, frozen relative provenance and recoverable
apply/acknowledgement journals. Archived resolved schema-v1 records never activate
automatically. Historical evidence is retained in CURRENT-SYSTEM.md.

## Managed arrays and plans

INI WorkshopItems, Mods and singular Map map to JSON WorkshopItems, Mods and Maps.
Entries are trimmed, empty segments omitted, duplicates rejected, order/case
preserved. Workshop IDs are numeric ASCII strings. All keys are required; maps
cannot be empty.

Plans allow Description and Add/RemoveWorkshopItems, Add/RemoveMods, Add/RemoveMaps
arrays. Unknown fields, scalar arrays, invalid IDs/separators fail. Mods/Maps
additions accept strings or Id objects with optional Before OR After. Conflicting
or missing anchors fail. Remove precedes add. Existing unanchored additions do
nothing; anchored additions may move members; new unanchored members append.
No optional Workshop variant is auto-selected.

~~~json
{
  "Description": "Synthetic ordering example",
  "RemoveWorkshopItems": ["100"],
  "AddWorkshopItems": ["300"],
  "AddMods": [{"Id": "ExampleMod", "Before": "OtherExampleMod"}]
}
~~~

Use pz apply-mod-plan FILE for preview; add --apply to mutate. Both are serialized
ops jobs. A no-op creates no pending record. Only selected values change; UTF-8
BOM, per-line LF/CRLF and final-newline presence are preserved.

## Apply transaction

Apply validates existing pending and refuses unresolved journals. It saves
before.ini, immutable plan.json, after.ini, pending metadata and any superseded
provenance under state/plans/RecordId. It rechecks original bytes, writes an apply
journal, atomically publishes INI, publishes pending, then clears the journal.

New runtime emits schema 2 only. Authority includes RecordId/CreatedAt/Reason,
relative Plan/History, SHA256 of immutable plan and before-INI, and exact ordered
Expected.WorkshopItems/Mods/Maps. Counts and whole-config/INI hashes are diagnostic.
Validation checks paths/hashes, replays the plan from saved before-state and compares
exact Expected/current arrays. Counts or a caller-supplied hash cannot bypass this.
Unrelated startup configuration rewrites are allowed.

Apply recovery compares active INI with journal original/after hashes. Original
state restores prior pending disposition; applied state publishes/validates new
pending. A third byte state returns RECOVERY_AMBIGUOUS and retains evidence.
Permanent guards must never be deleted to bypass kernel ownership.

## Fresh healthy acknowledgement

A pre-existing READY child never acknowledges an applied plan. An actual fresh
start validates pending and requires a stopped safety backup. Ops records the new
generation and waits for owned process/UDP plus authenticated parseable RCON.
Failed/timeout startup retains pending and diagnostic evidence.

After fresh readiness, ops writes an acknowledgement journal, captures active
configuration history, atomically commits the portable baseline, revalidates
pending/provenance and unchanged configuration, records completed provenance,
removes pending and clears the journal. Tests inject failure before baseline,
after baseline and after pending removal.

Ack recovery requires the same proven healthy generation. A later child cannot
claim the original readiness barrier. If the generation is lost, preserve the
interrupted target and restore a coherent stopped backup into a new project for a
new normal fresh-start lifecycle.

## Config state

The active scope is the configured server's INI and three matching Lua config files.
Ordering uses Unicode code-point filename order, then SHA256 of filename|file-hash
rows. ManagedHash separately hashes exact ordered arrays, including Maps.
Old Windows culture-dependent baseline state is private provenance only.

config-state reports baseline-missing, workshop, config or none, plus pending.
Public config-commit refuses pending/apply/ack state. There is no expected-hash
escape. Only internal acknowledgement after healthy fresh start resolves pending.

## Explicit legacy importer

legacy-import requires supplied relocated record, plan and saved before-INI; it
never follows archived Windows absolute paths. Schema 1 uses decoded-text UTF-8
PlanHash, exact before/after counts and case/order-sensitive replay against current
INI. Ambiguous/missing evidence fails. Validation alone activates nothing.
Explicit --activate freezes the reviewed artifacts and emits coherent schema-2
pending. Archived resolved records are never selected automatically.

## Tests

Synthetic tests cover parsing/Map mapping/order/case, missing keys/duplicates,
BOM/newlines, plan validation/anchors/remove-add order, no-ops, schema-2 record/
plan/history tampering, legacy replay/isolation, successive applies, unrelated
versus managed startup rewrites, config-commit refusal, apply/ack crash phases
and generation ownership. Running PZ/client acceptance is separately reported.
