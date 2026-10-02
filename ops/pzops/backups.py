import os
from contextlib import closing
import re
import shutil
import sqlite3
import tarfile
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from pzops.util import PZError, atomic_bytes, confined, file_hash, manifest, now, read_json, relative, sync_dir, tree_files, write_json
from pzops.ini import Ini
from pzops.mods import Lifecycle

TYPES = {"daily", "manual", "pre-server-update", "pre-workshop-update", "pre-config-restart"}
PATTERN = re.compile(r"^(daily|manual|pre-server-update|pre-workshop-update|pre-config-restart)-[0-9T-]+-[a-f0-9]{32}$")
DATA_ROOTS = {"Server", "Saves", "db", "Lua", "options.ini"}
DATA_MARKERS = {".import-complete.json", ".pristine-verified.json", ".migration-gate.json", ".runtime-ready.json"}
STATE_ROOTS = {"plans", "config-history", "config-state.json"}


def persistent_files(layout):
    for key, path in tree_files(layout.data):
        top = key.split("/", 1)[0]
        if top in DATA_ROOTS or key in DATA_MARKERS:
            if top == "Lua" and path.suffix.lower() == ".log":
                continue
            yield "data/" + key, path
    for key, path in tree_files(layout.state):
        if key.split("/", 1)[0] in STATE_ROOTS or key == "pending-mod-restart.json":
            yield "state/" + key, path


def database_check(root):
    checked = 0
    for p in Path(root).rglob("*.db"):
        # Only staging/copy data is passed by callers. No immutable mode hides journals.
        try:
            with closing(sqlite3.connect(p.resolve().as_uri() + "?mode=ro", uri=True)) as db:
                rows = list(db.execute("PRAGMA quick_check"))
            if rows != [("ok",)]:
                raise PZError("DATABASE_INTEGRITY_FAILED")
        except sqlite3.Error:
            raise PZError("DATABASE_INTEGRITY_FAILED") from None
        checked += 1
    return checked


def verify(snapshot, server=None):
    snapshot = Path(snapshot)
    metadata = read_json(snapshot / "_backup.json")
    expected = read_json(snapshot / "manifest.json")
    if not isinstance(metadata, dict) or metadata.get("SchemaVersion") != 3 or metadata.get("Status") != "complete" or not isinstance(expected, dict):
        raise PZError("BACKUP_INCOMPLETE")
    if file_hash(snapshot / "manifest.json") != metadata.get("ManifestHash"):
        raise PZError("BACKUP_MANIFEST_TAMPERED")
    for key, info in expected.items():
        path = confined(snapshot, key)
        parts = relative(key).parts
        allowed = len(parts) > 1 and ((parts[0] == "data" and (parts[1] in DATA_ROOTS or "/".join(parts[1:]) in DATA_MARKERS)) or (parts[0] == "state" and (parts[1] in STATE_ROOTS or parts[1:] == ("pending-mod-restart.json",))))
        if not allowed or not isinstance(info, dict):
            raise PZError("BACKUP_PATH_INVALID")
        if not path.is_file() or path.stat().st_size != info.get("bytes") or file_hash(path) != info.get("sha256"):
            raise PZError("BACKUP_HASH_MISMATCH")
    actual = {key for key, p in tree_files(snapshot) if key not in ("_backup.json", "manifest.json")}
    if actual != set(expected) or len(expected) != metadata.get("FileCount") or sum(x["bytes"] for x in expected.values()) != metadata.get("SizeBytes"):
        raise PZError("BACKUP_INVENTORY_MISMATCH")
    name = server or metadata.get("ServerName")
    if name != metadata.get("ServerName"):
        raise PZError("BACKUP_SERVER_MISMATCH")
    Ini.read(snapshot / "data/Server" / (name + ".ini")).mod_state()
    if not (snapshot / "data/Saves").is_dir() or not (snapshot / "data/db").is_dir():
        raise PZError("BACKUP_STRUCTURE_INVALID")
    return metadata


def create(layout, kind="manual", version=None, protected=False):
    if kind not in TYPES:
        raise PZError("BACKUP_TYPE_INVALID")
    if (layout.state / "apply-journal.json").exists() or (layout.state / "ack-journal.json").exists():
        raise PZError("RECOVERY_REQUIRED")
    Lifecycle(layout).validate()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    name = ("known-good" if protected else kind) + "-" + stamp + "-" + uuid.uuid4().hex
    layout.backups.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".inprogress-", dir=layout.backups))
    try:
        before = {}
        for key, source in persistent_files(layout):
            dst = confined(staging, key)
            dst.parent.mkdir(parents=True, exist_ok=True)
            before[key] = {"bytes": source.stat().st_size, "sha256": file_hash(source)}
            shutil.copyfile(source, dst)
        for dirname in ("Saves", "db", "Lua"):
            (staging / "data" / dirname).mkdir(parents=True, exist_ok=True)
        actual = manifest(staging)
        if actual != before:
            raise PZError("BACKUP_COPY_MISMATCH")
        if {k: {"bytes": p.stat().st_size, "sha256": file_hash(p)} for k, p in persistent_files(layout)} != before:
            raise PZError("BACKUP_SOURCE_CHANGED")
        databases = database_check(staging / "data")
        write_json(staging / "manifest.json", before)
        metadata = {"SchemaVersion": 3, "Status": "complete", "Type": kind, "ServerName": layout.server,
                    "CompletedAt": now(), "FileCount": len(before), "SizeBytes": sum(x["bytes"] for x in before.values()),
                    "ManifestHash": file_hash(staging / "manifest.json"), "Version": version,
                    "DatabasesChecked": databases, "Protected": protected}
        write_json(staging / "_backup.json", metadata)
        verify(staging, layout.server)
        target = layout.backups / name
        os.rename(staging, target)
        sync_dir(layout.backups)
        return {"name": name, **metadata}
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def catalog(layout):
    result = []
    if not layout.backups.exists():
        return result
    for p in layout.backups.iterdir():
        if not p.is_dir() or p.is_symlink() or not PATTERN.fullmatch(p.name):
            continue
        try:
            meta = read_json(p / "_backup.json")
            if not isinstance(meta, dict) or meta.get("SchemaVersion") != 3 or meta.get("Status") != "complete" or meta.get("Protected") or meta.get("ServerName") != layout.server:
                continue
            datetime.fromisoformat(meta["CompletedAt"])
            if not (p / "manifest.json").is_file() or file_hash(p / "manifest.json") != meta.get("ManifestHash"):
                continue
            if any(not (p / "data" / x).is_dir() for x in ("Server", "Saves", "db")):
                continue
            result.append({"name": p.name, **meta})
        except (PZError, OSError, ValueError, KeyError, TypeError):
            continue
    return sorted(result, key=lambda x: x["CompletedAt"], reverse=True)


def retained(entries, recent=4, weekly=4):
    if recent < 1 or weekly < 0:
        raise PZError("INVALID_RETENTION")
    entries = sorted(entries, key=lambda x: x["CompletedAt"], reverse=True)
    keep = {x["name"] for x in entries[:recent]}
    def week(x):
        t = datetime.fromisoformat(x["CompletedAt"]).astimezone(timezone.utc)
        iso = t.isocalendar()
        return (iso.year, iso.week)
    covered = {week(x) for x in entries[:recent]}
    groups = {}
    for item in entries[recent:]:
        if week(item) not in covered:
            groups.setdefault(week(item), []).append(item)
    for group in sorted(groups, reverse=True)[:weekly]:
        items = groups[group]
        keep.add(next((x for x in items if x["Type"] != "daily"), items[0])["name"])
    return keep


def retention(layout, recent=4, weekly=4):
    entries = catalog(layout)
    keep = retained(entries, recent, weekly)
    removed = 0
    for item in entries:
        if item["name"] not in keep:
            path = confined(layout.backups, item["name"])
            # Revalidate metadata immediately before deleting this known rotating snapshot.
            if read_json(path / "_backup.json").get("Protected"):
                continue
            shutil.rmtree(path)
            removed += 1
    return removed


def restore(layout, snapshot, confirm_replace=False, desired=False, running=False):
    meta = verify(snapshot, layout.server)
    if desired or running:
        raise PZError("RESTORE_REQUIRES_OFFLINE")
    existing = any(layout.data.iterdir()) if layout.data.exists() else False
    if existing and not confirm_replace:
        raise PZError("RESTORE_CONFIRM_REQUIRED")
    if existing:
        create(layout, "manual", protected=True)
    stage = Path(tempfile.mkdtemp(prefix=".restore-", dir=layout.backups))
    try:
        shutil.copytree(Path(snapshot) / "data", stage / "data")
        if (Path(snapshot) / "state").exists():
            shutil.copytree(Path(snapshot) / "state", stage / "state")
        else:
            (stage / "state").mkdir()
        database_check(stage / "data")
        from pzops.util import Layout
        candidate = Layout(stage / "data", stage / "state", layout.backups, layout.logs, layout.server)
        Lifecycle(candidate).validate()
        # Keep a recoverable publication journal; interrupted replacement never auto-starts.
        write_json(layout.state / "restore-journal.json", {"backup": meta["ManifestHash"], "stage": stage.name, "phase": "prepared"})
        for p in list(layout.data.iterdir()):
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
        for p in (stage / "data").iterdir():
            shutil.move(str(p), layout.data / p.name)
        for name in (*STATE_ROOTS, "pending-mod-restart.json"):
            p = layout.state / name
            if p.is_dir():
                shutil.rmtree(p)
            elif p.exists():
                p.unlink()
        for p in (stage / "state").iterdir():
            shutil.move(str(p), layout.state / p.name)
        if (layout.data / ".migration-gate.json").exists():
            write_json(layout.data / ".pristine-verified.json", {"backup": Path(snapshot).name, "manifest_hash": meta["ManifestHash"], "verified_restore": True})
        write_json(layout.state / "intent.json", {"desired": False, "updated_at": now()})
        (layout.state / "restore-journal.json").unlink()
        sync_dir(layout.state)
        return {"restored": True, "desired": False, "ServerName": meta["ServerName"], "FileCount": meta["FileCount"]}
    finally:
        # Preserve staged evidence on interrupted publication.
        if stage.exists() and not (layout.state / "restore-journal.json").exists():
            shutil.rmtree(stage)


def export_archive(layout, name, target):
    source = confined(layout.backups, name)
    verify(source, layout.server)
    target = Path(target)
    if target.exists():
        raise PZError("EXPORT_TARGET_EXISTS")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(".export-" + uuid.uuid4().hex)
    try:
        with tarfile.open(temp, "w:gz") as archive:
            for name in ("data/Server", "data/Saves", "data/db", "data/Lua"):
                directory = source / name
                if directory.is_dir():
                    archive.add(directory, arcname=name, recursive=False)
            for key, p in tree_files(source):
                archive.add(p, arcname=key, recursive=False)
        os.rename(temp, target)
        sync_dir(target.parent)
    finally:
        if temp.exists():
            temp.unlink()
    return {"exported": target.name, "bytes": target.stat().st_size, "sha256": file_hash(target)}


def extract_archive(archive_path, target):
    target = Path(target)
    target.mkdir(parents=True, exist_ok=False)
    seen = set()
    size = 0
    try:
        with tarfile.open(archive_path, "r:*") as archive:
            for member in archive:
                key = member.name
                path = confined(target, key)
                if key.casefold() in seen or not (member.isfile() or member.isdir()) or member.size < 0:
                    raise PZError("UNSAFE_ARCHIVE_MEMBER")
                seen.add(key.casefold())
                if member.isdir():
                    if key not in ("data/Server", "data/Saves", "data/db", "data/Lua"):
                        raise PZError("UNSAFE_ARCHIVE_MEMBER")
                    path.mkdir(parents=True, exist_ok=True)
                    continue
                size += member.size
                if size > 100 * 1024 ** 3 or len(seen) > 2000000:
                    raise PZError("ARCHIVE_LIMIT_EXCEEDED")
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as inp, path.open("xb") as out:
                    shutil.copyfileobj(inp, out)
        verify(target)
        return target
    except Exception:
        shutil.rmtree(target)
        raise
