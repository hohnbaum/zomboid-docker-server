"""Initialize only explicitly mounted project volumes; never the import source."""
import os
import sys
from pathlib import Path


def volumes():
    os.umask(0o077)
    for name in ("data", "state", "control", "backups", "logs", "app"):
        path = Path("/pz") / name
        path.mkdir(parents=True, exist_ok=True)
        os.chown(path, 1000, 1000)
        os.chmod(path, 0o770)
    parent = Path("/pz/app/steamapps")
    parent.mkdir(parents=True, exist_ok=True)
    os.chown(parent, 1000, 1000)
    os.chmod(parent, 0o770)
    path = parent / "workshop"
    path.mkdir(parents=True, exist_ok=True)
    os.chown(path, 1000, 1000)
    os.chmod(path, 0o770)


if __name__ == "__main__":
    volumes()
    if len(sys.argv) > 1 and sys.argv[1] == "tool":
        os.setgroups([])
        os.setgid(1000)
        os.setuid(1000)
        from pzops.offline import main
        main(sys.argv[2:])
