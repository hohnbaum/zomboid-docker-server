import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_ops import BASE, ROOT, Fixture
from pzops import backups, migration
from pzops.ini import Ini
from pzops.mods import Lifecycle
from pzops.service import Jobs
from pzops.util import FileLock, PZError, atomic_bytes, digest, file_hash, manifest, read_json, write_json


class FailureTests(Fixture):
    def test_corrupt_intent_cannot_resurrect_game(self):
        write_json(self.layout.state / 'intent.json', {'desired': 'false'})
        self.error('INVALID_STATE', self.ops.intent)

    def test_malformed_pending_fixed_error(self):
        write_json(self.layout.pending, [])
        self.error('PENDING_INCOMPLETE', self.life.validate)

    def test_backup_failure_does_not_publish(self):
        with patch('pzops.backups.shutil.copyfile', side_effect=OSError('synthetic failure')):
            with self.assertRaises(OSError):
                backups.create(self.layout)
        self.assertFalse(any(p.name.startswith('.inprogress-') for p in self.layout.backups.iterdir()))
        self.assertEqual(backups.catalog(self.layout), [])

    def test_restore_hash_failure_leaves_target_untouched(self):
        item = backups.create(self.layout)
        snap = self.layout.backups / item['name']
        atomic_bytes(snap / 'data/options.ini', b'tampered')
        before = manifest(self.layout.data)
        self.error('BACKUP_HASH_MISMATCH', backups.restore, self.layout, snap, True)
        self.assertEqual(manifest(self.layout.data), before)

    def test_backup_and_restore_refuse_live_kernel_guard(self):
        item = backups.create(self.layout)
        with FileLock(self.layout.data / '.game-runtime.guard'):
            self.error('BUSY', backups.create, self.layout)
            self.error('BUSY', backups.restore, self.layout, self.layout.backups / item['name'], True)

    def test_pending_expected_tamper_even_with_matching_ini(self):
        self.life.apply({'AddMods': ['Third']})
        record = read_json(self.layout.pending)
        record['Expected']['Mods'].append('Tampered')
        write_json(self.layout.pending, record)
        atomic_bytes(self.layout.ini, Ini.read(self.layout.ini).with_state(record['Expected']))
        self.error('PENDING_REPLAY_MISMATCH', self.life.validate)

    def test_pending_before_history_tamper(self):
        self.life.apply({'AddMods': ['Third']})
        record = read_json(self.layout.pending)
        atomic_bytes(self.layout.state / record['History'], BASE + b'# changed\n')
        self.error('PENDING_HISTORY_TAMPERED', self.life.validate)

    def test_pending_plan_path_cannot_escape(self):
        self.life.apply({'AddMods': ['Third']})
        record = read_json(self.layout.pending)
        record['Plan'] = '../private.json'
        write_json(self.layout.pending, record)
        self.error('PENDING_PLAN_PATH_INVALID', self.life.validate)

    def test_startup_timeout_does_not_kill(self):
        self.ops.set_intent(True)
        self.proc['udp'] = []
        with patch.dict(os.environ, {'PZ_READY_TIMEOUT': '0'}):
            self.error('READINESS_TIMEOUT', self.ops.wait_ready, self.proc['generation'])
        self.assertTrue(self.proc['running'])
        self.assertFalse(any(x[0] == 'quit' for x in self.calls))

    def test_update_failure_stays_stopped(self):
        original = self.ops.agent
        def fail(action, **kwargs):
            if action == 'install':
                raise PZError('STEAM_INSTALL_FAILED')
            return original(action, **kwargs)
        self.ops.agent = fail
        self.ops.set_intent(True)
        self.error('STEAM_INSTALL_FAILED', self.ops.execute, self.job('update'))
        self.assertFalse(self.ops.intent())
        self.assertFalse(self.proc['running'])

    def test_refused_restart_preserves_false_intent(self):
        self.ops.workshop = lambda: {'State': 'none'}
        self.ops.rcon_call = lambda *a: 'Players connected (1):\n-player'
        self.error('PLAYERS_CONNECTED', self.ops.execute, self.job('restart'))
        self.assertFalse(self.ops.intent())

    def test_remote_build_failure_is_unknown(self):
        original = self.ops.agent
        self.ops.agent = lambda action, **kw: (_ for _ in ()).throw(PZError('STEAM_UNAVAILABLE')) if action == 'build-query' else original(action, **kw)
        self.assertIsNone(self.ops.build_status()['available'])
        self.assertTrue(self.ops.status()['ready'])

    def test_jobs_redact_raw_exception(self):
        self.ops.execute = lambda job: (_ for _ in ()).throw(RuntimeError('synthetic private detail'))
        jobs = Jobs(self.ops)
        job = jobs.submit('save', {})
        jobs.queue.join()
        result = jobs.get(job['id'])
        self.assertEqual(result['error'], 'OPERATION_FAILED')
        self.assertNotIn('private detail', json.dumps(result))
        self.assertTrue(self.ops.recovery_required())

    def test_restore_forbids_stale_control_files(self):
        item = backups.create(self.layout)
        snap = self.layout.backups / item['name']
        atomic_bytes(snap / 'state/lifecycle.guard', b'fake')
        expected = read_json(snap / 'manifest.json')
        expected['state/lifecycle.guard'] = {'bytes': 4, 'sha256': digest(b'fake')}
        write_json(snap / 'manifest.json', expected)
        meta = read_json(snap / '_backup.json')
        meta.update(ManifestHash=file_hash(snap / 'manifest.json'), FileCount=len(expected), SizeBytes=sum(x['bytes'] for x in expected.values()))
        write_json(snap / '_backup.json', meta)
        self.error('BACKUP_PATH_INVALID', backups.verify, snap)

    def test_case_collision_rejected_on_linux(self):
        if os.name == 'nt':
            self.skipTest('NTFS case-insensitive; exercised on Linux CI')
        atomic_bytes(self.layout.data / 'Lua/Case.json', b'1')
        atomic_bytes(self.layout.data / 'Lua/case.json', b'2')
        self.error('CASE_COLLISION', backups.create, self.layout)

    def test_import_full_copy_pristine_and_source_unchanged(self):
        target = backups_test_target(self)
        source = self.layout.data
        atomic_bytes(source / 'backups/historical.zip', b'synthetic reference')
        before = manifest(source)
        with FileLock(target.data / '.game-runtime.guard'):
            result = migration.import_instance(target, source)
        self.assertEqual(manifest(source), before)
        self.assertFalse(read_json(target.state / 'intent.json')['desired'])
        self.assertEqual(read_json(target.data / '.import-complete.json')['required_version'], '42.21.0')
        self.assertTrue(read_json(target.data / '.pristine-verified.json'))
        self.assertFalse((target.data / 'backups').exists())
        self.assertEqual(Ini.read(target.ini).mod_state(), Ini(BASE).mod_state())
        self.assertTrue((target.backups / result['reference'] / 'backups/historical.zip').exists())

    def test_import_archive_transfer_and_hash_validation(self):
        spec = importlib.util.spec_from_file_location('source_transfer', ROOT / 'scripts/source-transfer.py')
        transfer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(transfer)
        archive = Path(self.temp.name) / 'private-transfer.tar'
        transfer.pack(self.layout.data, archive)
        target = backups_test_target(self)
        with FileLock(target.data / '.game-runtime.guard'):
            migration.import_archive(target, archive)
        transfer.verify(self.layout.data, archive)
        self.assertTrue((target.data / '.import-complete.json').exists())


def backups_test_target(fixture):
    from test_ops import BackupTests
    return BackupTests.new_target(fixture)


class AgentTests(Fixture):
    def setUp(self):
        super().setUp()
        spec = importlib.util.spec_from_file_location('linux_agent', ROOT / 'server/agent.py')
        self.module = importlib.util.module_from_spec(spec)
        if os.name == 'nt':
            import socketserver
            with patch.object(socketserver, 'ThreadingUnixStreamServer', socketserver.ThreadingTCPServer, create=True):
                spec.loader.exec_module(self.module)
        else:
            spec.loader.exec_module(self.module)
        app = Path(self.temp.name) / 'app'
        control = Path(self.temp.name) / 'control'
        app.mkdir()
        control.mkdir()
        self.module.APP, self.module.DATA, self.module.CONTROL, self.module.LOGS = app, self.layout.data, control, self.layout.logs
        atomic_bytes(app / 'start-server.sh', b'# synthetic launcher')
        atomic_bytes(app / 'steamapps/appmanifest_380870.acf', b'"buildid" "1000"')
        write_json(app / 'ProjectZomboid64.json', {'vmArgs': ['-Xmx8g', '-Dfake=true']})
        write_json(app / '.pz-install.json', {'version': '42.21.0', 'version_build': '1000'})
        with patch.dict(os.environ, {'PZ_SERVER_NAME': 'synthetic'}):
            self.agent = self.module.Agent()
        self.agent.process = lambda: None

    def tearDown(self):
        if self.agent.child:
            self.agent.child.exit = 0
            self.agent.status()
            self.agent.child.stdin.close()
        if self.agent.child_log:
            self.agent.child_log.close()
        super().tearDown()

    def test_import_mismatch_and_pristine_gate(self):
        write_json(self.layout.data / '.import-complete.json', {'required_version': '42.22.0'})
        self.error('BLOCKED_VERSION', self.agent.start, 'synthetic-job')
        write_json(self.layout.data / '.import-complete.json', {'required_version': '42.21.0'})
        self.error('PRISTINE_BACKUP_REQUIRED', self.agent.start, 'synthetic-job')

    def test_stale_log_cannot_prove_new_build(self):
        atomic_bytes(self.module.APP / 'steamapps/appmanifest_380870.acf', b'"buildid" "2000"')
        atomic_bytes(self.layout.data / 'server-console.txt', b'version=42.21.0')
        atomic_bytes(self.layout.logs / 'game-console.log', b'version=42.21.0')
        self.assertIsNone(self.agent.installed()['version'])

    def test_interrupted_install_blocks_start_and_version(self):
        write_json(self.module.APP / '.pz-installing.json', {'job': 'synthetic'})
        self.assertIsNone(self.agent.installed()['version'])
        self.error('APP_INSTALL_INCOMPLETE', self.agent.start, 'synthetic-job')

    def test_current_generation_proves_build_version(self):
        write_json(self.module.APP / '.pz-install.json', {})
        atomic_bytes(self.layout.logs / 'game-console.log', b'stale version=42.99.0\n')
        self.agent.log_offset = (self.layout.logs / 'game-console.log').stat().st_size
        with (self.layout.logs / 'game-console.log').open('ab') as stream:
            stream.write(b'version=42.21.0\nmod version=99.0.0\n')
        self.assertEqual(self.agent.installed()['version'], '42.21.0')
        self.assertEqual(read_json(self.module.APP / '.pz-install.json')['version_build'], '1000')

    def test_start_is_idempotent_and_heap_uses_package(self):
        class Child:
            def __init__(self):
                self.stdin, self.stdout, self.pid, self.exit = io.BytesIO(), io.BytesIO(), 99999, None
            def poll(self):
                return self.exit
        with patch.object(self.module.subprocess, 'Popen', return_value=Child()) as spawn, patch.dict(os.environ, {'PZ_HEAP': '2g'}):
            first = self.agent.start('synthetic-job')
            second = self.agent.start('synthetic-job')
        self.assertEqual(spawn.call_count, 1)
        self.assertEqual(first['generation'], second['generation'])
        self.assertEqual(read_json(self.module.APP / 'ProjectZomboid64.json')['vmArgs'], ['-Dfake=true', '-Xms2g', '-Xmx2g'])
        self.assertFalse(any('-Xmx' in x for x in spawn.call_args.args[0]))

    def test_agent_action_allowlist(self):
        for request in ({'action': 'shell'}, {'action': 'start', 'job': 'x', 'path': '/arbitrary'}, {'action': 'install', 'job': '../escape'}):
            with self.assertRaises(PZError):
                self.agent.dispatch(request)

    def test_workshop_remote_failure_stays_unknown(self):
        root = self.module.APP / 'steamapps/workshop'
        (root / 'content/108600/100').mkdir(parents=True)
        atomic_bytes(root / 'appworkshop_108600.acf', b'"WorkshopItemsInstalled" { "100" { "timeupdated" "7" "manifest" "9" } } "WorkshopItemDetails" {}')
        with patch.object(self.module.urllib.request, 'urlopen', side_effect=OSError('synthetic offline')):
            result = self.agent.workshop(['100'])
        self.assertEqual(result['Items'][0]['Status'], 'Unknown')
        self.assertEqual(result['State'], 'unavailable')


if __name__ == '__main__':
    unittest.main()
