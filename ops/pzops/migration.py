import os
import secrets
import shutil
import tempfile
import tarfile
import uuid
from pathlib import Path
from pzops.ini import Ini
from pzops.util import PZError, atomic_bytes, confined, file_hash, manifest, now, read_json, tree_files, write_json
from pzops import backups


def disposition(key, server):
    if key in {"options.ini", *["Server/" + server + x for x in (".ini", "_SandboxVars.lua", "_spawnpoints.lua", "_spawnregions.lua")], "db/" + server + ".db"}:
        return "active"
    if key.startswith("Saves/Multiplayer/" + server + "/") or key.startswith("Lua/SkillRecoveryJournal/Multiplayer/" + server + "/") or key.startswith("Lua/ttf_stats_mp/"):
        return "active"
    return "reference"


def import_archive(layout, archive):
    stage = Path(tempfile.mkdtemp(prefix=".source-transfer-", dir=layout.backups))
    seen, total = set(), 0
    try:
        with tarfile.open(archive, "r:*") as stream:
            for member in stream:
                path = confined(stage, member.name)
                if not (member.isfile() or member.isdir()) or member.name.casefold() in seen or not (member.name == "source-manifest.json" or member.name.startswith("instance/")):
                    raise PZError("UNSAFE_ARCHIVE_MEMBER")
                seen.add(member.name.casefold())
                total += member.size
                if member.size < 0 or total > 100 * 1024**3 or len(seen) > 2000000:
                    raise PZError("ARCHIVE_LIMIT_EXCEEDED")
                if member.isdir():
                    if not member.name.startswith("instance/"):
                        raise PZError("UNSAFE_ARCHIVE_MEMBER")
                    path.mkdir(parents=True, exist_ok=True)
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                with stream.extractfile(member) as inp, path.open("xb") as out:
                    shutil.copyfileobj(inp, out)
        if manifest(stage / "instance") != read_json(stage / "source-manifest.json"):
            raise PZError("SOURCE_TRANSFER_HASH_MISMATCH")
        return import_instance(layout, stage / "instance")
    finally:
        shutil.rmtree(stage)


def init_empty(layout):
    if any(p.name != ".game-runtime.guard" for p in layout.data.iterdir()):
        raise PZError("TARGET_NOT_EMPTY")
    for folder in ("Server", "Saves", "db", "Lua"):
        (layout.data / folder).mkdir()
    # Generated synthetic credentials are intentionally absent from repository fixtures.
    values = {"DefaultPort": "16261", "UDPPort": "16262", "RCONPort": "27015",
              "RCONPassword": secrets.token_urlsafe(32), "Password": secrets.token_urlsafe(24),
              "WorkshopItems": "", "Mods": "", "Map": "Muldraugh, KY", "Public": "false",
              "Open": "true", "UPnP": "false", "MaxPlayers": "4", "PauseEmpty": "true"}
    atomic_bytes(layout.ini, "".join(k + "=" + v + "\n" for k, v in values.items()).encode())
    atomic_bytes(layout.data / ".bootstrap-admin.secret", (secrets.token_urlsafe(24) + "\n").encode())
    write_json(layout.data / ".runtime-ready.json", {"synthetic": True, "server": layout.server, "created_at": now()})
    write_json(layout.state / "intent.json", {"desired": False, "updated_at": now()})
    return {"initialized": True, "server": layout.server, "desired": False}


def import_instance(layout, source):
    source = Path(source).resolve()
    target = layout.data.resolve()
    if target == source or target.is_relative_to(source) or source.is_relative_to(target) or "source-snapshot" in target.parts:
        raise PZError("SOURCE_TARGET_OVERLAP")
    if any(p.name != ".game-runtime.guard" for p in layout.data.iterdir()):
        raise PZError("TARGET_NOT_EMPTY")
    if (layout.state / "intent.json").exists() and read_json(layout.state / "intent.json").get("desired"):
        raise PZError("IMPORT_REQUIRES_OFFLINE")
    required = ["Server/" + layout.server + x for x in (".ini", "_SandboxVars.lua", "_spawnpoints.lua", "_spawnregions.lua")]
    required += ["db/" + layout.server + ".db", "options.ini"]
    if any(not (source / x).is_file() for x in required) or not (source / "Saves/Multiplayer" / layout.server).is_dir():
        raise PZError("IMPORT_SOURCE_INCOMPLETE")
    state = Ini.read(source / "Server" / (layout.server + ".ini")).mod_state()
    before = manifest(source)
    layout.backups.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".import-", dir=layout.backups))
    reference = stage / "reference"
    active = stage / "data"
    active.mkdir()
    reference.mkdir()
    try:
        classified = {}
        for key, p in tree_files(source):
            action = disposition(key, layout.server)
            destination = (active if action == "active" else reference) / key
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, destination)
            if file_hash(destination) != before[key]["sha256"]:
                raise PZError("IMPORT_COPY_MISMATCH")
            classified[key] = {**before[key], "disposition": action}
        for dirname in ("Lua", "db", "Saves"):
            (active / dirname).mkdir(exist_ok=True)
        if Ini.read(active / "Server" / (layout.server + ".ini")).mod_state() != state:
            raise PZError("IMPORT_MOD_ORDER_MISMATCH")
        databases = backups.database_check(active)
        if manifest(source) != before:
            raise PZError("SOURCE_CHANGED_DURING_IMPORT")
        ident = "import-reference-" + uuid.uuid4().hex
        reference_target = layout.backups / ident
        os.rename(reference, reference_target)
        write_json(reference_target / "import-manifest.json", classified)
        for p in active.iterdir():
            shutil.move(str(p), layout.data / p.name)
        marker = {"server": layout.server, "required_version": "42.21.0", "created_at": now(),
                  "reference": ident, "source_files": len(before), "source_bytes": sum(x["bytes"] for x in before.values()),
                  "active_files": sum(x["disposition"] == "active" for x in classified.values()), "databases_checked": databases}
        write_json(layout.state / "intent.json", {"desired": False, "updated_at": now()})
        write_json(layout.data / ".migration-gate.json", {"required_version": "42.21.0", "server": layout.server})
        pristine = backups.create(layout, protected=True, version={"version": "42.21.0", "source_evidence": True}, _locked=True)
        write_json(layout.data / ".pristine-verified.json", {"backup": pristine["name"], "manifest_hash": pristine["ManifestHash"]})
        write_json(layout.data / ".import-complete.json", marker)
        return {**marker, "desired": False, "pristine_backup": pristine["name"]}
    finally:
        if stage.exists():
            shutil.rmtree(stage)
