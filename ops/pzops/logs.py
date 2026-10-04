"""Local private log tail; module invocation avoids host shell string quoting."""
import json
import re
import sys
from pathlib import Path
from pzops.util import Layout


def tail(path, lines=100, limit=4 * 1024 * 1024):
    with Path(path).open('rb') as stream:
        stream.seek(0, 2)
        offset = max(0, stream.tell() - limit)
        stream.seek(offset)
        data = stream.read(limit)
    parts = data.decode('utf-8', errors='replace').splitlines()
    if offset:
        parts = parts[1:]
    return '\n'.join(parts[-lines:])


def startup_issue(path, offset):
    if offset is None:
        return None
    try:
        with Path(path).open('rb') as stream:
            stream.seek(offset)
            data = stream.read(8 * 1024 * 1024).decode('utf-8', errors='replace')
    except OSError:
        return None
    if re.search(r'\*{3,}\s*SERVER STARTED\s*\*{3,}', data):
        return None
    if re.search(r'(?im)^.*\bWorkshop\b[^\r\n]*(?:Download\w*[^\r\n]*(?:Fail|Error)|Fail\w*[^\r\n]*Download|state[^\r\n]*\bFail\b)', data):
        return 'WORKSHOP_DOWNLOAD_FAILED'
    return None


def main():
    try:
        print(tail(Layout.environment().logs / 'game-console.log'))
    except OSError:
        print(json.dumps({'error': 'GAME_LOG_UNAVAILABLE'}))
        sys.exit(1)


if __name__ == '__main__':
    main()
