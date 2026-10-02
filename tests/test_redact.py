import io
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ops'))
from pzops.redact import pump


class Sink(io.BytesIO):
    def close(self):
        self.result = self.getvalue()
        super().close()


class RedactionTests(unittest.TestCase):
    def test_admin_game_rcon_filtered(self):
        sink = Sink()
        secret = b'unit-test-placeholder'
        pump(io.BytesIO(b'version=42.21.0\nadmin: ' + secret + b'\n'), sink, [secret])
        self.assertNotIn(secret, sink.result)
        self.assertIn(b'version=42.21.0', sink.result)

    def test_chunk_boundary_and_eof(self):
        sink = Sink()
        secret = b'unit-test-placeholder'
        raw = b'x' * (1024 * 1024 - 5) + secret + b'end'
        pump(io.BytesIO(raw), sink, [secret])
        self.assertNotIn(secret, sink.result)
        self.assertEqual(len(raw), len(sink.result))

    def test_empty_secrets_and_newline(self):
        sink = Sink()
        pump(io.BytesIO(b'ordinary\n'), sink, [b''])
        self.assertEqual(sink.result, b'ordinary\n')
