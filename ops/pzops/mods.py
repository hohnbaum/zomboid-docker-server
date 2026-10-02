"""Exact ordered mod authority, recoverable apply and fresh-start acknowledgement."""
import json
import uuid
from pathlib import Path
from pzops.ini import Ini
from pzops.util import PZError, atomic_bytes, confined, digest, file_hash, now, read_json, write_json, sync_dir

PROPS = ("WorkshopItems", "Mods", "Maps")
FIELDS = {"Description", *[prefix + prop for prefix in ("Add", "Remove") for prop in PROPS]}


def entry(value, ordered=False):
    if isinstance(value, str):
        value = {"Id": value}
    if not isinstance(value, dict) or set(value) - {"Id", "Before", "After"}:
        raise PZError("INVALID_PLAN_ENTRY")
    if not ordered and set(value) != {"Id"}:
        raise PZError("ANCHOR_NOT_ALLOWED")
    if value.get("Before") and value.get("After"):
        raise PZError("CONFLICTING_ANCHORS")
    for key, val in value.items():
        if not isinstance(val, str) or not val.strip() or any(x in val for x in (";", "\r", "\n")):
            raise PZError("INVALID_PLAN_ENTRY")
    if "Id" not in value:
        raise PZError("INVALID_PLAN_ENTRY")
    return {k: v.strip() for k, v in value.items()}


def validate_plan(plan):
    if not isinstance(plan, dict) or set(plan) - FIELDS:
        raise PZError("INVALID_PLAN")
    for key, values in plan.items():
        if key == "Description":
            if not isinstance(values, str):
                raise PZError("INVALID_PLAN")
            continue
        if not isinstance(values, list):
            raise PZError("PLAN_ARRAY_REQUIRED")
        for value in values:
            item = entry(value, key in ("AddMods", "AddMaps"))
            if key.endswith("WorkshopItems") and not item["Id"].isascii():
                raise PZError("INVALID_WORKSHOP_ID")
            if key.endswith("WorkshopItems") and not item["Id"].isdigit():
                raise PZError("INVALID_WORKSHOP_ID")
    return plan


def planned(before, plan):
    validate_plan(plan)
    result = {}
    for prop in PROPS:
        values = list(before[prop])
        for value in plan.get("Remove" + prop, []):
            ident = entry(value)["Id"]
            values = [x for x in values if x != ident]
        for value in plan.get("Add" + prop, []):
            item = entry(value, prop != "WorkshopItems")
            ident = item["Id"]
            anchored = "Before" in item or "After" in item
            if ident in values:
                if not anchored:
                    continue
                values.remove(ident)
            if anchored:
                key = "Before" if "Before" in item else "After"
                if item[key] not in values:
                    raise PZError("ANCHOR_MISSING")
                values.insert(values.index(item[key]) + (key == "After"), ident)
            else:
                values.append(ident)
        if len(values) != len(set(values)):
            raise PZError("DUPLICATE_MOD_ENTRY")
        result[prop] = values
    if not result["Maps"]:
        raise PZError("EMPTY_MAPS")
    return result


def counts(value):
    return {"Workshop": len(value["WorkshopItems"]), "Mods": len(value["Mods"]), "Maps": len(value["Maps"])}


def config_fingerprint(layout):
    files = [layout.data / "Server" / (layout.server + suffix)
             for suffix in (".ini", "_SandboxVars.lua", "_spawnpoints.lua", "_spawnregions.lua")]
    rows = [p.name + "|" + file_hash(p) for p in sorted(files, key=lambda p: p.name) if p.is_file()]
    return {"ConfigHash": digest("\n".join(rows).encode()),
            "ManagedHash": digest(json.dumps(Ini.read(layout.ini).mod_state(), separators=(",", ":")).encode()),
            "Timestamp": now(), "Scope": [p.name for p in sorted(files, key=lambda p: p.name) if p.is_file()]}


def config_check(layout):
    current = config_fingerprint(layout)
    old = read_json(layout.state / "config-state.json")
    state = "baseline-missing" if not old else "workshop" if old.get("ManagedHash") != current["ManagedHash"] else "config" if old.get("ConfigHash") != current["ConfigHash"] else "none"
    return {"state": state, "pending": layout.pending.exists(), "scope": current["Scope"]}


class Lifecycle:
    def __init__(self, layout, fault=lambda _: None):
        self.layout = layout
        self.fault = fault
        self.journal = layout.state / "apply-journal.json"
        self.ackjournal = layout.state / "ack-journal.json"

    def validate(self):
        pending = read_json(self.layout.pending)
        if pending is None:
            return None
        if pending.get("SchemaVersion") != 2:
            raise PZError("LEGACY_PENDING_IMPORT_REQUIRED")
        if not pending.get("RecordId") or not pending.get("CreatedAt") or not pending.get("Reason"):
            raise PZError("PENDING_INCOMPLETE")
        plan = confined(self.layout.state, pending.get("Plan"))
        if not plan.is_file() or file_hash(plan) != pending.get("PlanHash"):
            raise PZError("PENDING_PLAN_TAMPERED")
        validate_plan(read_json(plan))
        expected = pending.get("Expected")
        if not isinstance(expected, dict) or set(expected) != set(PROPS):
            raise PZError("PENDING_EXPECTED_MISSING")
        for prop in PROPS:
            if not isinstance(expected[prop], list):
                raise PZError("PENDING_EXPECTED_INVALID")
            for val in expected[prop]:
                entry(val)
        if expected != Ini.read(self.layout.ini).mod_state():
            raise PZError("PENDING_MOD_STATE_MISMATCH")
        return pending

    def preview(self, plan):
        before = Ini.read(self.layout.ini).mod_state()
        after = planned(before, plan)
        return {"changed": before != after, "Before": before, "Expected": after}

    def apply(self, plan):
        if self.journal.exists() or self.ackjournal.exists():
            raise PZError("RECOVERY_REQUIRED")
        previous = self.validate()
        diff = self.preview(plan)
        if not diff["changed"]:
            return {"changed": False}
        ident = uuid.uuid4().hex
        root = self.layout.state / "plans" / ident
        root.mkdir(parents=True)
        original = self.layout.ini.read_bytes()
        newbytes = Ini(original).with_state(diff["Expected"])
        atomic_bytes(root / "before.ini", original)
        write_json(root / "plan.json", plan)
        if previous:
            write_json(root / "superseded.json", previous)
        pending = {"SchemaVersion": 2, "RecordId": ident, "CreatedAt": now(),
                   "Plan": "plans/" + ident + "/plan.json", "PlanHash": file_hash(root / "plan.json"),
                   "History": "plans/" + ident + "/before.ini", "Reason": "Explicit plan awaits healthy fresh start",
                   "Expected": diff["Expected"], "Before": counts(diff["Before"]), "After": counts(diff["Expected"]),
                   "IniHash": digest(newbytes), "ConfigHash": config_fingerprint(self.layout)["ConfigHash"]}
        write_json(root / "pending.json", pending)
        atomic_bytes(root / "after.ini", newbytes)
        if self.layout.ini.read_bytes() != original:
            raise PZError("INI_CHANGED_DURING_APPLY")
        journal = {"record": ident, "original_hash": digest(original), "after_hash": digest(newbytes), "previous": previous}
        write_json(self.journal, journal)
        self.fault("prepared")
        atomic_bytes(self.layout.ini, newbytes)
        self.fault("ini-written")
        write_json(self.layout.pending, pending)
        self.fault("pending-written")
        self.journal.unlink()
        sync_dir(self.layout.state)
        return {"changed": True, "record": ident, "counts": pending["After"]}

    def recover_apply(self):
        journal = read_json(self.journal)
        if not journal:
            return {"recovered": False}
        root = confined(self.layout.state, "plans/" + journal["record"])
        current = file_hash(self.layout.ini)
        if current == journal["original_hash"]:
            if journal["previous"]:
                write_json(self.layout.pending, journal["previous"])
            elif self.layout.pending.exists():
                self.layout.pending.unlink()
        elif current == journal["after_hash"]:
            write_json(self.layout.pending, read_json(root / "pending.json"))
            self.validate()
        else:
            raise PZError("RECOVERY_AMBIGUOUS")
        self.journal.unlink()
        sync_dir(self.layout.state)
        return {"recovered": True, "pending": self.layout.pending.exists()}

    def commit(self):
        if self.layout.pending.exists() or self.journal.exists() or self.ackjournal.exists():
            raise PZError("PENDING_COMMIT_REFUSED")
        self._commit()
        return {"committed": True}

    def _commit(self, generation=None):
        state = config_fingerprint(self.layout)
        root = self.layout.state / "config-history" / uuid.uuid4().hex
        root.mkdir(parents=True)
        for name in state["Scope"]:
            atomic_bytes(root / name, (self.layout.data / "Server" / name).read_bytes())
        if config_fingerprint(self.layout)["ConfigHash"] != state["ConfigHash"]:
            raise PZError("CONFIG_CHANGED_DURING_COMMIT")
        write_json(self.layout.state / "config-state.json", {**state, "generation": generation})
        return state

    def acknowledge(self, generation, record, fresh):
        if not fresh or not generation:
            raise PZError("FRESH_START_REQUIRED")
        pending = self.validate()
        if (pending or {}).get("RecordId") != record:
            raise PZError("PENDING_CHANGED")
        fingerprint = digest(self.layout.pending.read_bytes()) if pending else None
        journal = {"generation": generation, "record": record, "fingerprint": fingerprint, "phase": "prepared"}
        write_json(self.ackjournal, journal)
        self.fault("ack-prepared")
        state = self._commit(generation)
        journal.update(phase="committed", baseline=state["ConfigHash"])
        write_json(self.ackjournal, journal)
        self.fault("baseline-written")
        if config_fingerprint(self.layout)["ConfigHash"] != state["ConfigHash"]:
            raise PZError("CONFIG_CHANGED_DURING_COMMIT")
        if pending:
            self.validate()
            if digest(self.layout.pending.read_bytes()) != fingerprint:
                raise PZError("PENDING_CHANGED")
            write_json(self.layout.state / "plans" / record / "completed.json", {**pending, "generation": generation, "CompletedAt": now()})
            self.layout.pending.unlink()
        self.fault("pending-removed")
        self.ackjournal.unlink()
        sync_dir(self.layout.state)

    def recover_ack(self, healthy_generation):
        journal = read_json(self.ackjournal)
        if not journal:
            return {"recovered": False}
        if healthy_generation != journal.get("generation"):
            raise PZError("RECOVERY_FRESH_GENERATION_UNPROVEN")
        record = journal.get("record")
        if not self.layout.pending.exists() and record:
            completed = read_json(self.layout.state / "plans" / record / "completed.json")
            if not completed or completed.get("generation") != healthy_generation:
                raise PZError("RECOVERY_AMBIGUOUS")
            self.ackjournal.unlink()
        else:
            if record and digest(self.layout.pending.read_bytes()) != journal.get("fingerprint"):
                raise PZError("PENDING_CHANGED")
            self.acknowledge(healthy_generation, record, True)
        return {"recovered": True}


def validate_legacy(record, plan_bytes, before_bytes, current):
    """Explicit importer only: supplied relocated artifacts, no Windows-path access."""
    if not isinstance(record, dict) or record.get("SchemaVersion") != 1:
        raise PZError("LEGACY_SCHEMA_INVALID")
    try:
        decoded = plan_bytes.decode("utf-8-sig")
        plan = json.loads(decoded)
        if digest(decoded.encode()).upper() != str(record["PlanHash"]).upper():
            raise PZError("PENDING_PLAN_TAMPERED")
        before = Ini(before_bytes).mod_state()
        if counts(before) != record["Before"] or counts(current) != record["After"]:
            raise PZError("LEGACY_COUNTS_MISMATCH")
        if planned(before, plan) != current:
            raise PZError("LEGACY_REPLAY_MISMATCH")
    except (KeyError, ValueError, UnicodeError):
        raise PZError("LEGACY_AMBIGUOUS") from None
    return plan
