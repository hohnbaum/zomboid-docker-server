# Security and private data

Only code, documentation and synthetic tests belong in this repository. Keep worlds,
databases, real INIs, archives, logs, .env and secret files outside Git. Backups contain
passwords and account/player data and require private storage and transfer.

RCON and the authenticated operations API have no host port mappings. Do not attach
untrusted containers to the project's networks. Never mount a Docker socket. The
server control socket permits fixed typed operations only. Docker administrator
access can read all runtime data; Compose file secrets are not encrypted at rest.

Run `python scripts/audit-public-tree.py` before committing and publishing. The
scanner is a useful guard, not a substitute for reviewing the staged diff and Git
history. It reports paths/rule names without printing matched secret values.

Report vulnerabilities privately to the repository maintainer through GitHub's
private vulnerability reporting when enabled. Do not open an issue containing a
token, password, database, world archive or unredacted server log.

Project Zomboid and Workshop content have their own terms and are downloaded
separately into private volumes. The MIT license applies to original project code.
