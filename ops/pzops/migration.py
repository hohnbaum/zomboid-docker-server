import os
import secrets
import shutil
import tempfile
import tarfile
import uuid
from pathlib import Path
from pzops.ini import Ini
from pzops.util import PZError, atomic_bytes, confined, file_hash, manifest, now, read_json, sync_dir, tree_files, write_json
from pzops import backups


def disposition(key, server):
    if key in {"options.ini", *["Server/" + server + x for x in (".ini", "_SandboxVars.lua", "_spawnpoints.lua", "_spawnregions.lua")], "db/" + server + ".db"}:
        return "active"
    if key in {'db/' + server + '.db' + suffix for suffix in ('-wal', '-shm', '-journal')}:
        return 'active'
    if key.startswith("Saves/Multiplayer/" + server + "/") or (key.startswith('Lua/') and not key.lower().endswith('.log')):
        return "active"
    return "reference"


def import_archive(layout, archive):
    # Native source transfer and private file-drop reuse one bounded extractor.
    if any(p.name != '.game-runtime.guard' for p in layout.data.iterdir()):
        raise PZError('TARGET_NOT_EMPTY')
    stage = Path(tempfile.mkdtemp(prefix=".source-transfer-", dir=layout.backups))
    stage.rmdir()
    try:
        with tarfile.open(archive, "r:*") as stream:
            first = stream.next()
        if first is None:
            raise PZError('IMPORT_SOURCE_INCOMPLETE')
        top = first.name.rstrip('/').split('/')[0]
        kind = 'instance' if top in ('instance', 'source-manifest.json') else 'flat' if top in backups.DATA_ROOTS else 'backup'
        before = file_hash(archive)
        backups.extract_archive(archive, stage, kind=kind)
        if file_hash(archive) != before:
            raise PZError('ARCHIVE_CHANGED_DURING_IMPORT')
        if kind != 'backup':
            return import_instance(layout, stage / 'instance' if kind == 'instance' else stage)
        metadata = read_json(stage / '_backup.json')
        declared = metadata.get('Version')
        if isinstance(declared, dict):
            declared = declared.get('version')
        gate = read_json(stage / 'data/.migration-gate.json') or read_json(stage / 'data/.import-complete.json')
        if (declared is not None and declared != '42.21.0') or (gate and gate.get('required_version') != '42.21.0'):
            raise PZError('BLOCKED_VERSION')
        restored = backups.restore(layout, stage, _locked=True)
        write_json(layout.data / '.migration-gate.json', {'required_version': '42.21.0', 'server': layout.server})
        pristine = backups.create(layout, protected=True, _locked=True)
        write_json(layout.data / '.pristine-verified.json', {'backup': pristine['name'], 'manifest_hash': pristine['ManifestHash']})
        marker = {'server': layout.server, 'required_version': '42.21.0', 'created_at': now(),
                  'archive_sha256': before, 'pristine_backup': pristine['name'], 'desired': False}
        write_json(layout.data / '.import-complete.json', marker)
        return {**restored, **marker}
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def init_empty(layout):
    if any(p.name != ".game-runtime.guard" for p in layout.data.iterdir()):
        raise PZError("TARGET_NOT_EMPTY")
    for folder in ("Server", "Saves", "db", "Lua"):
        (layout.data / folder).mkdir()
    # Generated synthetic credentials are intentionally absent from repository fixtures.
    values = {"DefaultPort": "16261", "UDPPort": "16262", "RCONPort": "27015",
              "RCONPassword": secrets.token_urlsafe(32), "Password": "",
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
        expected_active = {k: before[k] for k, value in classified.items() if value['disposition'] == 'active'}
        published = {key: {'bytes': copied.stat().st_size, 'sha256': file_hash(copied)} for key, copied in tree_files(layout.data) if key != '.game-runtime.guard'}
        if published != expected_active:
            raise PZError('IMPORT_COPY_MISMATCH')
        for key, copied in tree_files(layout.data):
            if key != '.game-runtime.guard':
                with copied.open('r+b') as durable:
                    os.fsync(durable.fileno())
        if os.name != 'nt':
            for directory, _, _ in os.walk(layout.data, topdown=False):
                sync_dir(directory)
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
