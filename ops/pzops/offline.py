"""One-shot tools: only explicit offline targets, never launch Java."""
import argparse
import json
import sys
import uuid
from pathlib import Path
from pzops import backups, migration
from pzops.mods import Lifecycle, validate_legacy
from pzops.ini import Ini
from pzops.util import FileLock, Layout, PZError, confined, read_json, write_json


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("empty")
    sub.add_parser("import")
    p = sub.add_parser("import-archive")
    p.add_argument("--archive", required=True)
    p = sub.add_parser("backup")
    p.add_argument("--type", default="manual")
    p = sub.add_parser("restore")
    p.add_argument("--archive", required=True)
    p.add_argument("--confirm-replace", action="store_true")
    p = sub.add_parser("export")
    p.add_argument("--backup", required=True)
    p.add_argument("--output", required=True)
    p = sub.add_parser("legacy-import")
    p.add_argument("--record", required=True)
    p.add_argument("--plan", required=True)
    p.add_argument("--before", required=True)
    p.add_argument("--activate", action="store_true")
    args = parser.parse_args(argv)
    layout = Layout.environment()
    try:
        with FileLock(layout.state / "lifecycle.guard"), FileLock(layout.data / ".game-runtime.guard"):
            desired = read_json(layout.state / "intent.json", {}).get("desired", False)
            if desired:
                raise PZError("TOOLS_REQUIRE_DESIRED_FALSE")
            if args.action == "empty":
                result = migration.init_empty(layout)
            elif args.action == "import":
                result = migration.import_instance(layout, Path("/source"))
            elif args.action == "import-archive":
                result = migration.import_archive(layout, confined("/source", args.archive))
            elif args.action == "backup":
                result = backups.create(layout, args.type, _locked=True)
            elif args.action == "restore":
                archive = confined("/source", args.archive)
                stage = layout.backups / (".archive-" + uuid.uuid4().hex)
                backups.extract_archive(archive, stage)
                try:
                    result = backups.restore(layout, stage, args.confirm_replace, desired=desired, _locked=True)
                finally:
                    import shutil
                    shutil.rmtree(stage)
            elif args.action == "export":
                result = backups.export_archive(layout, args.backup, confined("/exports", args.output))
            else:
                record = read_json(confined("/source", args.record))
                planbytes = confined("/source", args.plan).read_bytes()
                before = confined("/source", args.before).read_bytes()
                plan = validate_legacy(record, planbytes, before, Ini.read(layout.ini).mod_state())
                result = {"valid": True, "activated": False}
                if args.activate:
                    if layout.pending.exists():
                        raise PZError("PENDING_ALREADY_EXISTS")
                    ident = uuid.uuid4().hex
                    root = layout.state / "plans" / ident
                    root.mkdir(parents=True)
                    from pzops.util import atomic_bytes, file_hash, now
                    write_json(root / "plan.json", plan)
                    atomic_bytes(root / "before.ini", before)
                    write_json(layout.pending, {"SchemaVersion": 2, "RecordId": ident, "CreatedAt": now(),
                               "Plan": "plans/" + ident + "/plan.json", "PlanHash": file_hash(root / "plan.json"),
                               "History": "plans/" + ident + "/before.ini", "BeforeIniHash": file_hash(root / "before.ini"),
                               "Expected": Ini.read(layout.ini).mod_state(), "Reason": "Explicit legacy import validated by saved-state replay"})
                    result["activated"] = True
        print(json.dumps(result))
    except PZError as exc:
        print(json.dumps({"error": exc.code}))
        sys.exit(1)


if __name__ == "__main__":
    main()
