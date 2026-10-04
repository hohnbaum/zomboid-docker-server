"""Synthetic finalization checks: host transport, file-drop and empty bootstrap."""
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from test_ops import ROOT, Fixture
from test_failures import backups_test_target
from pzops import backups, migration
from pzops.ini import Ini
from pzops.logs import startup_issue, tail
from pzops.util import FileLock, atomic_bytes, file_hash, manifest, read_json


class HandoffTests(Fixture):
    def test_empty_no_player_password_but_random_private_secrets(self):
        target = backups_test_target(self)
        migration.init_empty(target)
        other = backups_test_target(self)
        migration.init_empty(other)
        ini = Ini.read(target.ini)
        self.assertEqual(ini.get('Password'), '')
        self.assertGreater(len(ini.get('RCONPassword')), 32)
        self.assertNotEqual(ini.get('RCONPassword'), Ini.read(other.ini).get('RCONPassword'))
        self.assertGreater(len((target.data / '.bootstrap-admin.secret').read_bytes()), 24)
        self.assertFalse(read_json(target.state / 'intent.json')['desired'])

    def flat_archive(self):
        archive = Path(self.temp.name) / 'szs-final.tar.gz'
        with tarfile.open(archive, 'w:gz') as stream:
            for name in ('Server', 'Saves', 'db', 'Lua', 'options.ini'):
                stream.add(self.layout.data / name, arcname=name)
        return archive

    def test_plain_persistence_file_drop_full_validation(self):
        atomic_bytes(self.layout.data / 'Lua/another-mod/data.json', b'{"synthetic":true}')
        before = manifest(self.layout.data)
        archive = self.flat_archive()
        target = backups_test_target(self)
        with FileLock(target.data / '.game-runtime.guard'):
            result = migration.import_archive(target, archive)
        self.assertEqual(manifest(self.layout.data), before)
        self.assertEqual((target.data / 'Lua/another-mod/data.json').read_bytes(), b'{"synthetic":true}')
        self.assertTrue(result['pristine_backup'])
        self.assertEqual(read_json(target.data / '.migration-gate.json')['required_version'], '42.21.0')
        self.assertFalse(read_json(target.state / 'intent.json')['desired'])

    def test_backup_format_file_drop_reuses_restore_and_pristine(self):
        item = backups.create(self.layout)
        archive = Path(self.temp.name) / 'portable.tar.gz'
        backups.export_archive(self.layout, item['name'], archive)
        target = backups_test_target(self)
        with FileLock(target.data / '.game-runtime.guard'):
            result = migration.import_archive(target, archive)
        self.assertTrue(result['restored'])
        self.assertTrue((target.data / '.import-complete.json').exists())
        self.assertFalse(read_json(target.state / 'intent.json')['desired'])
        self.assertEqual(Ini.read(target.ini).mod_state(), Ini.read(self.layout.ini).mod_state())

    def test_file_drop_refuses_existing_target(self):
        self.error('TARGET_NOT_EMPTY', migration.import_archive, self.layout, self.flat_archive())

    def test_import_cross_volume_publication_copy_damage_blocks_completion(self):
        target = backups_test_target(self)
        original = shutil.move
        def corrupt(source, destination, *args, **kwargs):
            result = original(source, destination, *args, **kwargs)
            if Path(destination) == target.data / 'options.ini':
                atomic_bytes(Path(destination), b'synthetic damaged publication')
            return result
        with FileLock(target.data / '.game-runtime.guard'), patch('pzops.migration.shutil.move', side_effect=corrupt):
            self.error('IMPORT_COPY_MISMATCH', migration.import_instance, target, self.layout.data)
        self.assertFalse((target.data / '.import-complete.json').exists())

    def test_restore_publication_damage_keeps_recovery_journal(self):
        item = backups.create(self.layout)
        target = backups_test_target(self)
        original = shutil.move
        def corrupt(source, destination, *args, **kwargs):
            result = original(source, destination, *args, **kwargs)
            if Path(destination) == target.data / 'options.ini':
                atomic_bytes(Path(destination), b'synthetic damaged publication')
            return result
        with patch('pzops.backups.shutil.move', side_effect=corrupt):
            self.error('RESTORE_PUBLICATION_MISMATCH', backups.restore, target, self.layout.backups / item['name'])
        self.assertTrue((target.state / 'restore-journal.json').exists())

    def test_backup_file_drop_cannot_weaken_another_version_gate(self):
        item = backups.create(self.layout, version='42.22.0')
        archive = Path(self.temp.name) / 'another-version.tar.gz'
        backups.export_archive(self.layout, item['name'], archive)
        target = backups_test_target(self)
        with FileLock(target.data / '.game-runtime.guard'):
            self.error('BLOCKED_VERSION', migration.import_archive, target, archive)
        self.assertFalse(target.ini.exists())

    def test_file_drop_rejects_cache_link_and_mixed_scope(self):
        for name, link in (('app/secret', False), ('Server/linked.ini', True), ('../escape', False), ('instance/Server/mixed.ini', False)):
            with self.subTest(name=name):
                archive = Path(self.temp.name) / 'unsafe.tar.gz'
                with tarfile.open(archive, 'w:gz') as stream:
                    member = tarfile.TarInfo('Server')
                    member.type = tarfile.DIRTYPE
                    stream.addfile(member)
                    member = tarfile.TarInfo(name)
                    member.type = tarfile.SYMTYPE if link else tarfile.REGTYPE
                    member.linkname = '/outside' if link else ''
                    member.size = 0
                    stream.addfile(member, io.BytesIO())
                target = backups_test_target(self)
                with FileLock(target.data / '.game-runtime.guard'):
                    with self.assertRaises(Exception):
                        migration.import_archive(target, archive)
                self.assertFalse(target.ini.exists())

    def test_checksum_sidecars_and_wrong_checksum(self):
        archive = self.flat_archive()
        sidecar = archive.with_name(archive.name + '.sha256')
        expected = file_hash(archive)
        for text in (expected.upper(), expected + '  ' + archive.name, expected + ' *' + archive.name):
            atomic_bytes(sidecar, text.encode())
            self.assertEqual(backups.verify_archive_checksum(archive, sidecar), expected)
        atomic_bytes(sidecar, ('0' * 64).encode())
        self.error('ARCHIVE_CHECKSUM_MISMATCH', backups.verify_archive_checksum, archive, sidecar)
        for text in (expected + '  another.tar.gz', expected + '\n' + expected, 'synthetic invalid'):
            atomic_bytes(sidecar, text.encode())
            self.error('ARCHIVE_CHECKSUM_INVALID', backups.verify_archive_checksum, archive, sidecar)

    def test_export_writes_matching_external_sidecar(self):
        item = backups.create(self.layout)
        archive = Path(self.temp.name) / 'export.tar.gz'
        result = backups.export_archive(self.layout, item['name'], archive)
        self.assertEqual(result['sha256'], backups.verify_archive_checksum(archive, archive.with_name(result['sidecar'])))

    def test_account_journals_and_full_lua_persistence(self):
        for suffix in ('-wal', '-shm', '-journal'):
            self.assertEqual(migration.disposition('db/synthetic.db' + suffix, 'synthetic'), 'active')
        self.assertEqual(migration.disposition('Lua/additional-mod/persistent.bin', 'synthetic'), 'active')
        self.assertEqual(migration.disposition('Lua/diagnostic.log', 'synthetic'), 'reference')

    def test_private_tail_bounds_and_missing_log(self):
        path = self.layout.logs / 'game-console.log'
        atomic_bytes(path, ''.join(f'line {i}\n' for i in range(150)).encode())
        self.assertEqual(tail(path).splitlines()[0], 'line 50')
        self.assertEqual(tail(path, lines=2), 'line 148\nline 149')
        self.assertEqual(tail(path, lines=2, limit=25), 'line 148\nline 149')

    def test_workshop_failure_is_current_generation_only(self):
        path = self.layout.logs / 'game-console.log'
        raw = b'Workshop: DownloadPending -> Fail\n'
        atomic_bytes(path, raw + b'version=42.21.0\n')
        self.assertEqual(startup_issue(path, 0), 'WORKSHOP_DOWNLOAD_FAILED')
        self.assertIsNone(startup_issue(path, len(raw)))
        self.assertIsNone(startup_issue(path, None))
        atomic_bytes(path, b'Workshop: DownloadPending -> Installed\nordinary media error\n')
        self.assertIsNone(startup_issue(path, 0))
        atomic_bytes(path, raw + b'LOG: *** SERVER STARTED ****\nnormal stop\n')
        self.assertIsNone(startup_issue(path, 0))

    def test_workshop_exit_fixed_code_without_raw_log(self):
        self.proc.update(running=False, launching=False, startup_issue='WORKSHOP_DOWNLOAD_FAILED')
        self.error('START_WORKSHOP_DOWNLOAD_FAILED', self.ops.wait_ready, self.proc['generation'])


class HostTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('host_wrapper', ROOT / 'scripts/host.py')
        self.host = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.host)

    def test_logs_transport_module_no_shell_or_python_c(self):
        with patch.object(sys, 'argv', ['pz', 'logs']), patch.object(self.host, 'compose') as compose:
            self.host.main()
        self.assertEqual(compose.call_args.args, ('exec', '-T', 'pz-ops', 'python', '-m', 'pzops.logs'))

    def test_archive_import_argument_boundaries_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='handoff with spaces ') as directory:
            archive = Path(directory) / 'private archive.tar.gz'
            archive.touch()
            archive.with_name(archive.name + '.sha256').touch()
            with patch.object(sys, 'argv', ['pz', 'import', '--archive', str(archive)]), patch.object(self.host, 'tool') as tool:
                self.host.main()
            self.assertEqual(tool.call_args.args, ('import-archive', ['--archive', archive.name, '--sha256-file', archive.name + '.sha256']))
            self.assertEqual(tool.call_args.kwargs['source'], archive.parent)

    def test_secret_paths_are_resolved_per_profile_and_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            api, discord = Path(directory) / 'test/api.token', Path(directory) / 'test/discord.token'
            resolved = json.dumps({'secrets': {'api_token': {'file': str(api)}, 'discord_token': {'file': str(discord)}}})
            with patch.object(sys, 'argv', ['pz', 'init-secrets']), patch.object(self.host, 'compose', return_value=resolved), redirect_stdout(io.StringIO()):
                self.host.main()
                before = api.read_bytes()
                self.host.main()
            self.assertGreater(len(before), 48)
            self.assertEqual(api.read_bytes(), before)
            self.assertEqual(discord.read_bytes(), b'')

    @unittest.skipUnless(os.name == 'nt', 'Native PowerShell regression runs on Windows')
    def test_real_powershell_wrapper_preserves_logs_and_env_arguments(self):
        with tempfile.TemporaryDirectory(prefix='wrapper space ') as directory:
            root = Path(directory)
            (root / 'scripts').mkdir()
            shutil.copyfile(ROOT / 'pz.ps1', root / 'pz.ps1')
            (root / 'scripts/host.py').write_text('import json,sys; print(json.dumps(sys.argv[1:]))')
            result = subprocess.run([shutil.which('pwsh') or 'powershell', '-NoProfile', '-File', str(root / 'pz.ps1'), '--env-file', 'profile with spaces.env', 'logs'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), ['--env-file', 'profile with spaces.env', 'logs'])

    @unittest.skipIf(os.name == 'nt', 'POSIX executable regression runs on Linux')
    def test_real_linux_wrapper_preserves_logs_and_env_arguments(self):
        with tempfile.TemporaryDirectory(prefix='wrapper space ') as directory:
            root = Path(directory)
            (root / 'scripts').mkdir()
            shutil.copyfile(ROOT / 'pz', root / 'pz')
            (root / 'pz').chmod(0o755)
            (root / 'scripts/host.py').write_text('import json,sys; print(json.dumps(sys.argv[1:]))')
            result = subprocess.run([str(root / 'pz'), '--env-file', 'profile with spaces.env', 'logs'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), ['--env-file', 'profile with spaces.env', 'logs'])
