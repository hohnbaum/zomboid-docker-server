import contextlib
import hashlib
import json
import os
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


class PZError(Exception):
    """Public errors use fixed codes, never raw exception/config text."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sync_dir(path):
    if os.name != "nt":
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        sync_dir(path.parent)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def write_json(path, value):
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError):
        raise PZError("INVALID_STATE") from None


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value):
        raise PZError("INVALID_IDENTIFIER")
    return value


def relative(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "\x00" in value:
        raise PZError("UNSAFE_PATH")
    p = PurePosixPath(value)
    if p.is_absolute() or any(x in (".", "..", "") for x in value.split("/")):
        raise PZError("UNSAFE_PATH")
    return p


def confined(root, value):
    p = Path(root).joinpath(*relative(value).parts)
    if not p.resolve().is_relative_to(Path(root).resolve()):
        raise PZError("UNSAFE_PATH")
    return p


def unsafe_link(path):
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def tree_files(root):
    root = Path(root)
    if unsafe_link(root):
        raise PZError("UNSAFE_LINK")
    seen = set()
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in sorted(dirs + files):
            p = Path(base) / name
            if unsafe_link(p):
                raise PZError("UNSAFE_LINK")
            key = p.relative_to(root).as_posix()
            relative(key)
            if key.casefold() in seen:
                raise PZError("CASE_COLLISION")
            seen.add(key.casefold())
            if p.is_file():
                yield key, p


def manifest(root):
    return {key: {"bytes": p.stat().st_size, "sha256": file_hash(p)}
            for key, p in tree_files(root)}


@dataclass
class Layout:
    data: Path = Path("/pz/data")
    state: Path = Path("/pz/state")
    backups: Path = Path("/pz/backups")
    logs: Path = Path("/pz/logs")
    server: str = "pztest"

    @classmethod
    def environment(cls):
        return cls(server=identifier(os.getenv("PZ_SERVER_NAME", "pztest")))

    @property
    def ini(self):
        return self.data / "Server" / (self.server + ".ini")

    @property
    def pending(self):
        return self.state / "pending-mod-restart.json"


class FileLock:
    """Kernel lock; permanent file is never unlinked. Windows supports unit tests."""
    def __init__(self, path):
        self.path = Path(path)
        self.stream = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+b")
        self.stream.seek(0)
        if self.path.stat().st_size == 0:
            self.stream.write(b"0")
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            self.stream = None
            raise PZError("BUSY") from None
        return self

    def __exit__(self, *_):
        if self.stream:
            if os.name == "nt":
                import msvcrt
                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_UN)
            self.stream.close()
            self.stream = None
