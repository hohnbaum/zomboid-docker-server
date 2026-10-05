"""Synthetic fixtures only. No game downloads or operator credentials."""
import copy
from contextlib import closing
import importlib.util
import io
import json
import os
import socket
import sqlite3
import struct
import sys
import tarfile
import tempfile
import threading
import time
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops"))
from pzops import backups, migration, rcon
from pzops.core import Operations, validate_job
from pzops.ini import Ini
from pzops.info import literal, sandbox, settings
from pzops.mods import Lifecycle, config_check, counts, planned, validate_legacy, validate_plan
from pzops.service import Handler, Jobs, authorized
from pzops.util import FileLock, Layout, PZError, atomic_bytes, digest, file_hash, manifest, read_json, write_json

BASE = b'# synthetic\r\nWorkshopItems=100;200\r\nMods=First;second\r\nMap=Muldraugh, KY;Custom\r\nRCONPassword=unit-test-placeholder\r\nPassword=unit-test-placeholder\r\nDefaultPort=16261\r\nUDPPort=16262\r\nRCONPort=27015\r\nMaxPlayers=4\r\n'


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.layout = Layout(*(root / x for x in ("data", "state", "backups", "logs")), "synthetic")
        for p in (self.layout.data, self.layout.state, self.layout.backups, self.layout.logs):
            p.mkdir()
        atomic_bytes(self.layout.ini, BASE)
        for suffix in ("_SandboxVars.lua", "_spawnpoints.lua", "_spawnregions.lua"):
            atomic_bytes(self.layout.ini.with_name(self.layout.server + suffix), b'-- synthetic\nreturn {}\n')
        for name in ("Saves/Multiplayer/synthetic", "db", "Lua/SkillRecoveryJournal/Multiplayer/synthetic"):
            (self.layout.data / name).mkdir(parents=True)
        with closing(sqlite3.connect(self.layout.data / "db/synthetic.db")) as db, db:
            db.execute("create table fake (id integer)")
            db.execute("insert into fake values (7)")
        atomic_bytes(self.layout.data / "options.ini", b'fake-option=1\n')
        atomic_bytes(self.layout.data / "Lua/SkillRecoveryJournal/Multiplayer/synthetic/fake.json", b'{"fake":1}')
        self.life = Lifecycle(self.layout)
        self.proc = {"running": True, "launching": True, "udp": [16261, 16262], "generation": "synthetic-generation", "version": "42.21.0", "build": "synthetic-build"}
        self.calls = []
        def agent(action, **kwargs):
            self.calls.append((action, kwargs))
            if action == "start":
                self.proc.update(running=True, launching=True, generation=uuid.uuid4().hex)
            return copy.deepcopy(self.proc)
        def remote(host, port, password, action):
            self.calls.append((action, {}))
            if action == "players":
                return 'Players connected (0):'
            if action == "quit":
                self.proc.update(running=False, launching=False)
            return 'ok'
        self.ops = Operations(self.layout, agent=agent, rcon_call=remote, sleep=lambda _: None)
        write_json(self.layout.data / ".runtime-ready.json", {"synthetic": True})

    def tearDown(self):
        self.temp.cleanup()

    def error(self, code, call, *args, **kwargs):
        with self.assertRaises(PZError) as raised:
            call(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)

    def job(self, action, **args):
        return {"id": uuid.uuid4().hex, "action": action, "args": args}


class IniTests(Fixture):
    def test_exact_order_and_map_property(self):
        self.assertEqual(Ini(BASE).mod_state(), {"WorkshopItems": ["100", "200"], "Mods": ["First", "second"], "Maps": ["Muldraugh, KY", "Custom"]})

    def test_bom_crlf_preserve_unmanaged_bytes(self):
        data = b'\xef\xbb\xbf' + BASE
        new = Ini(data).replace({"Mods": "second;First"})
        self.assertEqual(new, data.replace(b'Mods=First;second', b'Mods=second;First'))

    def test_lf_no_final_newline(self):
        data = BASE.replace(b'\r\n', b'\n').rstrip(b'\n')
        self.assertEqual(Ini(data).replace({"Map": "X"}), data.replace(b'Map=Muldraugh, KY;Custom', b'Map=X'))

    def test_duplicate_managed_items(self):
        for key, value in ((b'Mods=First;second', b'Mods=First;First'), (b'WorkshopItems=100;200', b'WorkshopItems=100;100'), (b'Map=Muldraugh, KY;Custom', b'Map=Custom;Custom')):
            self.error("DUPLICATE_MOD_ENTRY", Ini(BASE.replace(key, value)).mod_state)

    def test_case_is_distinct(self):
        self.assertEqual(Ini(BASE.replace(b'First;second', b'First;first')).mod_state()["Mods"], ["First", "first"])

    def test_missing_managed_keys(self):
        for prefix in (b'WorkshopItems=', b'Mods=', b'Map='):
            data = b'\r\n'.join(x for x in BASE.split(b'\r\n') if not x.startswith(prefix))
            self.error("INI_KEY_MISSING", Ini(data).mod_state)

    def test_duplicate_key(self):
        self.error("DUPLICATE_INI_KEY", Ini, BASE + b'Mods=Other\r\n')

    def test_empty_map(self):
        self.error("EMPTY_MAPS", Ini(BASE.replace(b'Muldraugh, KY;Custom', b'')).mod_state)

    def test_invalid_workshop_and_encoding(self):
        self.error("INVALID_WORKSHOP_ID", Ini(BASE.replace(b'100;200', b'100;bad')).mod_state)
        self.error("INI_ENCODING", Ini, b'\xff')

    def test_comments_whitespace_and_empty_segments(self):
        state = Ini(b'# Mods=bad\n; Map=bad\n WorkshopItems = 100 ;; 200 ;\nMods= First ; second \nMap= Muldraugh, KY\n').mod_state()
        self.assertEqual(state["WorkshopItems"], ["100", "200"])


class PlanTests(Fixture):
    def test_remove_before_add_and_anchors(self):
        state = planned(Ini(BASE).mod_state(), {"RemoveMods": ["First"], "AddMods": [{"Id": "First", "After": "second"}], "RemoveWorkshopItems": ["100"], "AddWorkshopItems": ["100"]})
        self.assertEqual(state["Mods"], ["second", "First"])
        self.assertEqual(state["WorkshopItems"], ["200", "100"])

    def test_existing_anchor_moves_without_duplicate(self):
        self.assertEqual(planned(Ini(BASE).mod_state(), {"AddMods": [{"Id": "second", "Before": "First"}]})["Mods"], ["second", "First"])

    def test_missing_anchor(self):
        self.error("ANCHOR_MISSING", planned, Ini(BASE).mod_state(), {"AddMaps": [{"Id": "X", "Before": "Absent"}]})

    def test_invalid_plan_matrix(self):
        values = [None, [], {"Arbitrary": []}, {"AddMods": "X"}, {"AddMods": [4]}, {"AddMods": ["X;Y"]}, {"AddMods": [{"Id": "X", "Before": "Y", "After": "Z"}]}, {"AddWorkshopItems": ["bad"]}, {"AddWorkshopItems": [{"Id": "100", "Before": "200"}]}]
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(PZError):
                    validate_plan(value)

    def test_removing_all_maps_refused(self):
        self.error("EMPTY_MAPS", planned, Ini(BASE).mod_state(), {"RemoveMaps": ["Muldraugh, KY", "Custom"]})

    def test_noop_emits_no_pending(self):
        self.assertFalse(self.life.apply({"AddMods": ["First"]})["changed"])
        self.assertFalse(self.layout.pending.exists())

    def test_schema2_exact_and_frozen_authority(self):
        self.life.apply({"AddMods": [{"Id": "Third", "Before": "second"}]})
        record = self.life.validate()
        self.assertEqual(record["SchemaVersion"], 2)
        self.assertEqual(record["Expected"]["Mods"], ["First", "Third", "second"])
        self.error("PENDING_COMMIT_REFUSED", self.life.commit)

    def test_plan_tamper(self):
        self.life.apply({"AddMods": ["Third"]})
        rec = read_json(self.layout.pending)
        write_json(self.layout.state / rec["Plan"], {})
        self.error("PENDING_PLAN_TAMPERED", self.life.validate)

    def test_unrelated_startup_rewrite_allowed(self):
        self.life.apply({"AddMods": ["Third"]})
        atomic_bytes(self.layout.ini, self.layout.ini.read_bytes().replace(b'MaxPlayers=4', b'MaxPlayers=8'))
        self.life.validate()
        rec = read_json(self.layout.pending)
        self.life.acknowledge("fresh", rec["RecordId"], True)
        self.assertFalse(self.layout.pending.exists())
        self.assertEqual(config_check(self.layout)["state"], "none")

    def test_managed_rewrite_and_reorder_refused(self):
        self.life.apply({"AddMods": ["Third"]})
        atomic_bytes(self.layout.ini, self.layout.ini.read_bytes().replace(b'First;second;Third', b'second;First;Third'))
        self.error("PENDING_MOD_STATE_MISMATCH", self.life.validate)

    def test_fresh_start_required(self):
        self.life.apply({"AddMaps": ["X"]})
        self.error("FRESH_START_REQUIRED", self.life.acknowledge, "old", read_json(self.layout.pending)["RecordId"], False)

    def test_second_apply_supersedes_coherently(self):
        self.life.apply({"AddMods": ["Third"]})
        old = read_json(self.layout.pending)
        self.life.apply({"AddMods": ["Fourth"]})
        rec = self.life.validate()
        self.assertNotEqual(rec["RecordId"], old["RecordId"])
        self.assertEqual(rec["Expected"]["Mods"], ["First", "second", "Third", "Fourth"])

    def test_map_fingerprint(self):
        self.life.commit()
        atomic_bytes(self.layout.ini, Ini.read(self.layout.ini).replace({"Map": "Custom;Muldraugh, KY"}))
        self.assertEqual(config_check(self.layout)["state"], "workshop")

    def test_apply_crash_boundaries(self):
        for phase in ("prepared", "ini-written", "pending-written"):
            with self.subTest(phase=phase):
                atomic_bytes(self.layout.ini, BASE)
                self.layout.pending.unlink(missing_ok=True)
                def fault(value):
                    if value == phase:
                        raise RuntimeError("synthetic crash")
                with self.assertRaises(RuntimeError):
                    Lifecycle(self.layout, fault).apply({"AddMods": ["Third"]})
                self.error("RECOVERY_REQUIRED", self.life.apply, {})
                self.life.recover_apply()
                self.assertEqual(bool(self.life.validate()), phase != "prepared")

    def test_ambiguous_apply_refused(self):
        def fault(_):
            raise RuntimeError("synthetic crash")
        with self.assertRaises(RuntimeError):
            Lifecycle(self.layout, fault).apply({"AddMods": ["Third"]})
        atomic_bytes(self.layout.ini, BASE + b'# external edit\n')
        self.error("RECOVERY_AMBIGUOUS", self.life.recover_apply)

    def test_ack_crash_boundaries(self):
        for phase in ("ack-prepared", "baseline-written", "pending-removed"):
            with self.subTest(phase=phase):
                self.life.apply({"AddMods": [phase]})
                rec = self.life.validate()
                def fault(value):
                    if value == phase:
                        raise RuntimeError("synthetic crash")
                with self.assertRaises(RuntimeError):
                    Lifecycle(self.layout, fault).acknowledge("fresh", rec["RecordId"], True)
                self.error("RECOVERY_FRESH_GENERATION_UNPROVEN", self.life.recover_ack, "other")
                self.life.recover_ack("fresh")
                self.assertFalse(self.layout.pending.exists())

    def test_legacy_explicit_replay(self):
        plan = {"AddMods": ["Third"]}
        raw = json.dumps(plan).encode()
        before = Ini(BASE).mod_state()
        current = planned(before, plan)
        record = {"SchemaVersion": 1, "PlanHash": digest(raw).upper(), "Before": counts(before), "After": counts(current)}
        self.assertEqual(validate_legacy(record, b'\xef\xbb\xbf' + raw, BASE, current), plan)
        current["Mods"].reverse()
        self.error("LEGACY_REPLAY_MISMATCH", validate_legacy, record, raw, BASE, current)

    def test_legacy_never_implicitly_active(self):
        write_json(self.layout.pending, {"SchemaVersion": 1})
        self.error("LEGACY_PENDING_IMPORT_REQUIRED", self.life.validate)


class BackupTests(Fixture):
    def test_full_persistence_and_exclusions(self):
        atomic_bytes(self.layout.data / "backups/old.zip", b'private excluded')
        atomic_bytes(self.layout.data / "console.log", b'private excluded')
        atomic_bytes(self.layout.state / "operation.json", b'{}')
        item = backups.create(self.layout)
        snap = self.layout.backups / item["name"]
        files = read_json(snap / "manifest.json")
        self.assertIn("data/options.ini", files)
        self.assertIn("data/Lua/SkillRecoveryJournal/Multiplayer/synthetic/fake.json", files)
        self.assertFalse(any("old.zip" in x or "operation.json" in x for x in files))
        self.assertEqual(backups.verify(snap)["FileCount"], len(files))
        self.assertEqual(len(backups.catalog(self.layout)), 1)

    def test_pending_provenance_roundtrip(self):
        self.life.apply({"AddMods": ["Third"]})
        item = backups.create(self.layout)
        target = self.new_target()
        backups.restore(target, self.layout.backups / item["name"])
        self.assertEqual(Lifecycle(target).validate()["Expected"]["Mods"], ["First", "second", "Third"])

    def new_target(self):
        root = Path(self.temp.name) / uuid.uuid4().hex
        root.mkdir()
        out = Layout(*(root / x for x in ("data", "state", "backups", "logs")), self.layout.server)
        for p in (out.data, out.state, out.backups, out.logs):
            p.mkdir()
        return out

    def test_restore_new_marker_absent_and_false_intent(self):
        item = backups.create(self.layout)
        atomic_bytes(self.layout.data / "Lua/marker.txt", b'after backup')
        target = self.new_target()
        backups.restore(target, self.layout.backups / item["name"])
        self.assertFalse((target.data / "Lua/marker.txt").exists())
        self.assertFalse(read_json(target.state / "intent.json")["desired"])
        self.assertEqual({k:v for k,v in manifest(target.data).items() if k != '.game-runtime.guard'}, manifest(self.layout.backups / item["name"] / "data"))

    def test_restore_replace_requires_confirmation_and_offline(self):
        item = backups.create(self.layout)
        snap = self.layout.backups / item["name"]
        self.error("RESTORE_CONFIRM_REQUIRED", backups.restore, self.layout, snap)
        self.error("RESTORE_REQUIRES_OFFLINE", backups.restore, self.layout, snap, True, desired=True)
        self.error("RESTORE_REQUIRES_OFFLINE", backups.restore, self.layout, snap, True, running=True)
        backups.restore(self.layout, snap, True)
        self.assertTrue(any(x.name.startswith("known-good-") for x in self.layout.backups.iterdir()))

    def test_tampered_manifest_and_data(self):
        item = backups.create(self.layout)
        snap = self.layout.backups / item["name"]
        atomic_bytes(snap / "data/options.ini", b'tampered')
        self.error("BACKUP_HASH_MISMATCH", backups.verify, snap)
        atomic_bytes(snap / "manifest.json", b'{}')
        self.error("BACKUP_MANIFEST_TAMPERED", backups.verify, snap)

    def test_incomplete_not_catalogued(self):
        item = backups.create(self.layout)
        (self.layout.backups / item["name"] / "_backup.json").unlink()
        self.assertEqual(backups.catalog(self.layout), [])

    def test_database_integrity(self):
        atomic_bytes(self.layout.data / "db/broken.db", b'not sqlite')
        self.error("DATABASE_INTEGRITY_FAILED", backups.create, self.layout)
        self.assertFalse(any(x.name.startswith('.inprogress-') for x in self.layout.backups.iterdir()))

    def test_retention_recent_weekly_and_protected(self):
        entries = []
        for i in range(20):
            entries.append({"name": str(i), "CompletedAt": (datetime.now(timezone.utc) - timedelta(days=i*4)).isoformat(), "Type": "daily" if i % 2 else "manual"})
        keep = backups.retained(entries)
        self.assertTrue({"0", "1", "2", "3"} <= keep)
        self.assertEqual(len(keep), 8)
        protected = backups.create(self.layout, protected=True)
        backups.retention(self.layout)
        self.assertTrue((self.layout.backups / protected["name"]).exists())

    def test_tar_roundtrip(self):
        item = backups.create(self.layout)
        output = Path(self.temp.name) / 'synthetic.tar.gz'
        backups.export_archive(self.layout, item["name"], output)
        extracted = Path(self.temp.name) / 'unpacked'
        backups.extract_archive(output, extracted)
        self.assertEqual(backups.verify(extracted)["ManifestHash"], item["ManifestHash"])
        self.error("EXPORT_TARGET_EXISTS", backups.export_archive, self.layout, item["name"], output)

    def test_tar_unsafe_members(self):
        for key, kind in (("../escape", tarfile.REGTYPE), ("/absolute", tarfile.REGTYPE), ("C:/drive", tarfile.REGTYPE), ("data/link", tarfile.SYMTYPE), ("data/hard", tarfile.LNKTYPE), ("data/pipe", tarfile.FIFOTYPE)):
            with self.subTest(key=key):
                archive = Path(self.temp.name) / 'unsafe.tar'
                with tarfile.open(archive, 'w') as out:
                    member = tarfile.TarInfo(key)
                    member.type = kind
                    member.linkname = '../escape'
                    out.addfile(member)
                with self.assertRaises(PZError):
                    backups.extract_archive(archive, Path(self.temp.name) / 'reject')
                self.assertFalse((Path(self.temp.name) / 'reject').exists())

    def test_source_link_rejected(self):
        link = self.layout.data / "Lua/linked"
        try:
            link.symlink_to(self.layout.ini)
        except OSError:
            self.skipTest("Windows symlink privilege unavailable; exercised on Linux CI")
        self.error("UNSAFE_LINK", backups.create, self.layout)


class PolicyTests(Fixture):
    def test_readiness_requires_observed_version_but_accepts_future_versions(self):
        self.proc['version'] = None
        state = self.ops.status()
        self.assertFalse(state['ready'])
        self.assertIn('VERSION_UNVERIFIED', state['detail'])
        for version in ('42.22.0', '43.0.0'):
            self.proc['version'] = version
            self.assertTrue(self.ops.status()['ready'])

    def test_running_update_backs_up_old_version_then_restarts_new_build(self):
        write_json(self.layout.data / '.import-complete.json', {'required_version': '42.21.0'})
        self.ops.set_intent(True)
        original = self.ops.agent
        def upgraded(action, **kwargs):
            if action == 'install':
                self.assertFalse(self.proc['launching'])
                entries = backups.catalog(self.layout)
                self.assertEqual(entries[0]['Type'], 'pre-server-update')
                self.assertEqual(entries[0]['Version'], '42.21.0')
                self.proc.update(version=None, build='synthetic-new-build')
            if action == 'start':
                self.assertIsNone(self.proc['version'])
                self.proc['version'] = '42.22.0'
            return original(action, **kwargs)
        self.ops.agent = upgraded
        old_generation = self.proc['generation']
        result = self.ops.execute(self.job('update'))
        self.assertTrue(result['ready'])
        self.assertTrue(self.ops.intent())
        self.assertNotEqual(result['generation'], old_generation)
        self.assertEqual(self.ops.status()['version'], '42.22.0')
        backup = self.layout.backups / result['backup']
        self.assertEqual(backups.verify(backup)['Version'], '42.21.0')
        self.assertEqual(read_json(backup / 'data/.import-complete.json')['required_version'], '42.21.0')

    def test_failed_update_preserves_backup_and_false_intent(self):
        self.ops.set_intent(True)
        original = self.ops.agent
        def failed(action, **kwargs):
            if action == 'install':
                raise PZError('STEAM_INSTALL_FAILED')
            return original(action, **kwargs)
        self.ops.agent = failed
        self.error('STEAM_INSTALL_FAILED', self.ops.execute, self.job('update'))
        self.assertFalse(self.ops.intent())
        self.assertFalse(self.proc['launching'])
        self.assertEqual(backups.catalog(self.layout)[0]['Version'], '42.21.0')
        self.assertFalse(any(action == 'start' for action, _ in self.calls))

    def test_ready_and_maintenance(self):
        self.ops.set_intent(True)
        self.assertEqual(self.ops.status()["state"], "READY")
        write_json(self.layout.state / "maintenance.json", {"enabled": True})
        self.assertEqual(self.ops.status()["state"], "MAINTENANCE")

    def test_missing_udp_degraded_no_auto_restart(self):
        self.ops.set_intent(True)
        self.proc["udp"] = [16261]
        self.assertEqual(self.ops.status()["state"], "STARTING_OR_DEGRADED")
        submits = []
        self.ops.automatic(lambda *a, **k: submits.append(a))
        self.assertFalse(submits)

    def test_rcon_unavailable_degraded(self):
        self.ops.rcon_call = lambda *a: (_ for _ in ()).throw(PZError("RCON_UNAVAILABLE"))
        self.assertFalse(self.ops.status()["ready"])
        self.assertFalse(self.ops.status()["players_known"])
        self.error("RCON_UNAVAILABLE", self.ops.stop_game, True)

    def test_players_force_is_only_occupied_permission(self):
        self.ops.rcon_call = lambda *a: 'Players connected (1):\n-player' if a[-1] == 'players' else 'ok'
        self.error("PLAYERS_CONNECTED", self.ops.stop_game)
        self.ops.rcon_call = lambda *a: 'unparseable'
        self.error("PLAYERS_UNKNOWN", self.ops.stop_game, True)

    def test_offline_and_unexpected(self):
        self.proc.update(running=False, launching=False)
        self.assertEqual(self.ops.status()["state"], "OFFLINE_EXPECTED")
        self.ops.set_intent(True)
        self.assertEqual(self.ops.status()["state"], "DOWN_UNEXPECTED")
        submits = []
        self.ops.automatic(lambda *a, **k: submits.append((a, k)))
        self.assertEqual(submits[0][0][0], 'start')

    def test_false_intent_and_maintenance_prevent_reconcile(self):
        self.proc.update(running=False, launching=False)
        submits = []
        self.ops.automatic(lambda *a, **k: submits.append(a))
        self.ops.set_intent(True)
        write_json(self.layout.state / "maintenance.json", {"enabled": True})
        self.ops.automatic(lambda *a, **k: submits.append(a))
        self.assertFalse(submits)

    def test_automatic_intent_rechecked_inside_lock(self):
        job = self.job('start')
        job['automatic'] = True
        self.assertEqual(self.ops.execute(job)["skipped"], 'AUTOMATIC_STATE_CHANGED')
        self.assertFalse(self.calls)

    def test_intentional_stop(self):
        self.ops.set_intent(True)
        self.ops.execute(self.job('stop'))
        self.assertFalse(self.ops.intent())
        self.assertFalse(self.proc["running"])

    def test_no_pending_ack_for_already_running(self):
        self.life.apply({"AddMods": ["Third"]})
        self.ops.execute(self.job('start'))
        self.assertTrue(self.layout.pending.exists())

    def test_start_new_acknowledges_fresh_generation(self):
        self.proc.update(running=False, launching=False)
        self.life.apply({"AddMods": ["Third"]})
        self.ops.execute(self.job('start'))
        self.assertFalse(self.layout.pending.exists())
        self.assertTrue(self.ops.intent())

    def test_update_offline_stays_offline(self):
        self.proc.update(running=False, launching=False)
        self.ops.execute(self.job('update'))
        self.assertFalse(self.ops.intent())
        self.assertFalse(any(x[0] == 'start' for x in self.calls))

    def test_install_refuses_live(self):
        self.error("GAME_LIVE", self.ops.execute, self.job('install'))

    def test_operator_maintenance_blocks_start(self):
        write_json(self.layout.state / "maintenance.json", {"enabled": True})
        self.error("OPERATOR_MAINTENANCE", self.ops.execute, self.job('start'))

    def test_lifecycle_guard_permanent(self):
        guard = self.layout.state / 'lifecycle.guard'
        with FileLock(guard):
            self.error("BUSY", self.ops.execute, self.job('save'))
        self.assertTrue(guard.exists())
        with FileLock(guard):
            pass

    def test_action_allowlist_and_types(self):
        for action, args in (('shell', {}), ('stop', {'force': 'yes'}), ('start', {'command': 'fake'}), ('restore', {'backup': '../escape'}), ('maintenance', {})):
            with self.assertRaises(PZError):
                validate_job(action, args)

    def test_backup_age_common_catalog(self):
        item = backups.create(self.layout)
        self.assertEqual(self.ops.status()["backup"], item["name"])
        self.assertLess(self.ops.status()["backup_age_hours"], 1)

    def test_safe_info_never_evaluates_or_returns_passwords(self):
        value = settings(self.layout)
        self.assertNotIn('Password', value['settings'])
        self.assertIsNone(literal('os.execute("bad")'))
        self.assertIsNone(literal('"secret string"'))
        self.assertEqual(sandbox('    DayLength = 3,\n    ZombieLore = {\n        Speed = 2,\n    },\n    Arbitrary = 4,\n'), {'DayLength': 3, 'ZombieLore.Speed': 2})


class ApiTests(Fixture):
    def test_auth_constant_time_shape(self):
        self.assertTrue(authorized('Bearer unit-test-placeholder', 'unit-test-placeholder'))
        for header in (None, '', 'unit-test-placeholder', 'Bearer wrong'):
            self.assertFalse(authorized(header, 'unit-test-placeholder'))

    def test_job_recovery_never_replays(self):
        directory = self.layout.state / 'jobs'
        directory.mkdir()
        ident = uuid.uuid4().hex
        write_json(directory / (ident + '.json'), {'id': ident, 'state': 'running', 'action': 'restart', 'args': {}})
        self.ops.set_intent(True)
        jobs = Jobs(self.ops)
        self.assertEqual(jobs.get(ident)['state'], 'interrupted')
        self.assertFalse(self.ops.intent())
        self.assertTrue(self.ops.recovery_required())

    def test_idempotent_submit_and_private_args_redacted(self):
        self.ops.execute = lambda job: {'fake': True}
        jobs = Jobs(self.ops)
        ident = uuid.uuid4().hex
        first = jobs.submit('maintenance', {'enabled': True, 'reason': 'private'}, request_id=ident)
        again = jobs.submit('maintenance', {'enabled': True, 'reason': 'private'}, request_id=ident)
        self.assertEqual(first['id'], again['id'])
        self.assertNotIn('args', again)
        self.error("JOB_ID_CONFLICT", jobs.submit, 'start', {}, request_id=ident)
        jobs.queue.join()

    def test_api_auth_allowlist_and_disconnect(self):
        import urllib.request
        import urllib.error
        self.ops.execute = lambda job: (time.sleep(.1) or {'finished': True})
        jobs = Jobs(self.ops)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.ops, server.jobs, server.token = self.ops, jobs, 'unit-test-placeholder'
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = 'http://127.0.0.1:' + str(server.server_port)
        try:
            with self.assertRaises(urllib.error.HTTPError) as denied:
                urllib.request.urlopen(url + '/status')
            self.assertEqual(denied.exception.code, 401)
            headers = {'Authorization': 'Bearer unit-test-placeholder', 'Content-Type': 'application/json'}
            # Healthchecks use the authenticated API client without loading the CLI.
            from pzops.api_client import Client
            token = self.layout.state / 'api.token'
            token.write_text('unit-test-placeholder')
            client = Client(url=url, token_file=token)
            self.assertIs(client.request('ping').get('ok'), True)
            token.write_text('FAKE')
            rejected = Client(url=url, token_file=token)
            self.error('UNAUTHORIZED', rejected.request, 'ping')
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(urllib.request.Request(url + '/shell', headers=headers))
            req = urllib.request.Request(url + '/jobs', data=json.dumps({'action': 'save'}).encode(), headers=headers)
            with urllib.request.urlopen(req) as response:
                ident = json.load(response)['id']
            # The client has closed; independent durable work must still finish.
            jobs.queue.join()
            self.assertEqual(jobs.get(ident)['state'], 'complete')
        finally:
            server.shutdown()
            server.server_close()


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('public_audit', ROOT / 'scripts/audit-public-tree.py')
        cls.audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.audit)

    def test_forbidden_paths(self):
        for path in ('source-snapshot/file.txt', 'secrets/fake.token', 'Saves/world/file.txt', '.env', 'exports/fake.tar.gz', 'fake.db', 'runtime/file.json'):
            self.assertTrue(self.audit.inspect_blob(path, b'fake'))

    def test_secret_patterns_without_real_secrets(self):
        # Construct synthetic signatures, keeping literal credentials out of fixtures.
        inputs = [b'RCONPassword=' + b'fake-value', b'Password=' + b'fake-value', b'PZ_API_TOKEN=' + b'fake-value', ('ghp_' + 'x'*40).encode(), ('-----BEGIN ' + 'PRIVATE KEY-----').encode(), b'SQLite format 3\0']
        for value in inputs:
            self.assertTrue(self.audit.inspect_blob('example.txt', value))

    def test_placeholders_and_documentation_allowed(self):
        self.assertFalse(self.audit.inspect_blob('.env.example', b'RCONPassword=CHANGEME\nPassword=\nPZ_ADVERTISE_LAN=\n'))
        self.assertFalse(self.audit.inspect_blob('README.md', b'Keep RCONPassword private.'))


class RconTests(unittest.TestCase):
    def test_players(self):
        self.assertEqual(rcon.parse_players('Players connected (2):\n-Alice\n-Bob')['count'], 2)
        with self.assertRaises(PZError):
            rcon.parse_players('offline')

    def test_no_arbitrary_commands(self):
        with self.assertRaises(PZError):
            rcon.command('127.0.0.1', 1, 'unit-test-placeholder', 'arbitrary')


if __name__ == '__main__':
    unittest.main()
