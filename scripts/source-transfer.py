"""Native host hashing avoids per-file NTFS/WSL crossings. Private output only."""
import argparse
import json
import os
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ops"))
from pzops.util import PZError, atomic_bytes, manifest, tree_files


def pack(source, output):
    source, output = Path(source).resolve(strict=True), Path(output).resolve()
    if output.is_relative_to(source) or output.exists():
        raise PZError("UNSAFE_TRANSFER_TARGET")
    before = manifest(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, 'x') as archive:
        for base, dirs, files in os.walk(source):
            if not dirs and not files and Path(base) != source:
                archive.add(base, arcname='instance/' + Path(base).relative_to(source).as_posix(), recursive=False)
        for key, path in tree_files(source):
            archive.add(path, arcname='instance/' + key, recursive=False)
        import io
        data = json.dumps(before, sort_keys=True).encode()
        member = tarfile.TarInfo('source-manifest.json')
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
    if manifest(source) != before:
        raise PZError("SOURCE_CHANGED_DURING_TRANSFER")
    atomic_bytes(output.with_suffix('.manifest.json'), (json.dumps(before) + '\n').encode())
    print(json.dumps({'packed_files': len(before), 'packed_bytes': sum(v['bytes'] for v in before.values())}), flush=True)


def verify(source, output):
    expected = json.loads(Path(output).with_suffix('.manifest.json').read_text())
    if manifest(source) != expected:
        raise PZError("SOURCE_CHANGED_DURING_IMPORT")
    print('Original source SHA256 inventory unchanged.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    try:
        (verify if args.verify else pack)(args.source, args.output)
    except (OSError, ValueError, PZError) as exc:
        print(exc.code if isinstance(exc, PZError) else 'SOURCE_TRANSFER_FAILED')
        sys.exit(1)
